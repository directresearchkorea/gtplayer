"""
collect_news.py — 게임 뉴스 통합 수집 스크립트
RSS 피드와 웹 스크래핑으로 한국/인도/일본 게임 뉴스를 수집하고,
sent_log.db와 대조하여 중복을 제거한 후 통합 후보 리스트를 JSON으로 출력합니다.
"""

import os
import sys
import json
import hashlib
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "sent_log.db"
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "collected_news.json"

# How many hours back to look for news
TIME_WINDOW_HOURS = 48

# Title similarity threshold for deduplication
SIMILARITY_THRESHOLD = 0.80

# Browser-like User-Agent (needed for sites that block bots)
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# RSS feed sources
RSS_SOURCES = {
    # Korea
    "inven": {
        "url": "http://feeds.feedburner.com/inven",
        "country": "KR",
        "name": "인벤",
        "user_agent": "Mozilla/5.0",  # feedburner는 Chrome UA를 받으면 HTML을 반환함
    },
    "gamemeca": {
        "url": "https://www.gamemeca.com/rss.php",
        "country": "KR",
        "name": "게임메카",
    },
    # India
    "ign_india": {
        "url": "https://in.ign.com/feed.xml",
        "country": "IN",
        "name": "IGN India",
    },
    "gamer_tweak": {
        "url": "https://gamertweak.com/feed",
        "country": "IN",
        "name": "Gamer Tweak",
    },
    "afk_gaming": {
        "url": "https://afkgaming.com/feed",
        "country": "IN",
        "name": "AFK Gaming",
    },
    # Japan
    "4gamer": {
        "url": "https://www.4gamer.net/rss/index.xml",
        "country": "JP",
        "name": "4Gamer",
    },
    # Global (supplementary)
    "ign_global": {
        "url": "https://feeds.feedburner.com/ign/all",
        "country": "GLOBAL",
        "name": "IGN",
    },
    "pc_gamer": {
        "url": "https://www.pcgamer.com/rss/",
        "country": "GLOBAL",
        "name": "PC Gamer",
    },
    "gamesindustry": {
        "url": "https://www.gamesindustry.biz/feed",
        "country": "GLOBAL",
        "name": "GamesIndustry.biz",
    },
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("collect_news")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """URL에서 UTM 추적 파라미터만 제거하고, 기사 식별에 필요한 쿼리 파라미터는 보존합니다."""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    # UTM/tracking 파라미터만 제거
    tracking = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
                'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid'}
    cleaned = {k: v for k, v in params.items() if k.lower() not in tracking}
    new_query = urllib.parse.urlencode(cleaned, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def load_recent_editions_cache():
    """최근 발행된 10개의 에디션(JSON)을 파싱하여 이미 사용된 기사 URL 및 제목 목록을 추출합니다."""
    sent_urls = set()
    yesterday_sent = []
    
    try:
        import glob
        editions_dir = SCRIPT_DIR / ".." / ".." / "web" / "editions"
        files = sorted(glob.glob(str(editions_dir / "edition_*.json")))[-10:]
        
        for f in files:
            with open(f, "r", encoding="utf-8") as json_file:
                try:
                    data = json.load(json_file)
                    items = data.get("sections", {}).get("briefing", {}).get("items", [])
                    for item in items:
                        url = item.get("article_url")
                        if url:
                            sent_urls.add(url)
                            # UTM 파라미터만 제거한 정규화 URL도 등록 (gid= 같은 기사 식별 파라미터는 보존)
                            sent_urls.add(_normalize_url(url))
                        if item.get("title"):
                            yesterday_sent.append({
                                "title": item["title"],
                                "section": "briefing",
                                "category": item.get("category", "")
                            })
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"최근 에디션 캐시 로딩 실패: {e}")
        
    return sent_urls, yesterday_sent


# ---------------------------------------------------------------------------
# RSS collection
# ---------------------------------------------------------------------------

def fetch_rss(source_id: str, source_config: dict) -> list:
    """Fetch and parse a single RSS feed, returning news items."""
    url = source_config["url"]
    country = source_config["country"]
    source_name = source_config["name"]

    items = []
    try:
        ua = source_config.get("user_agent", BROWSER_UA)
        headers = {"User-Agent": ua}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)

        for entry in feed.entries[:30]:  # Limit to recent 30 entries per source
            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

            # Skip old articles (unless skip_time_filter is set)
            if not source_config.get("skip_time_filter") and published and published < cutoff:
                continue

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()

            # Clean HTML from summary
            if summary:
                soup = BeautifulSoup(summary, "html.parser")
                summary = soup.get_text(strip=True)[:200]

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "source_id": source_id,
                    "source_name": source_name,
                    "country": country,
                    "published": published.isoformat() if published else None,
                    "view_count": None,  # RSS doesn't provide this
                })

        log.info(f"[{source_name}] Collected {len(items)} items from RSS")

    except requests.RequestException as e:
        log.warning(f"[{source_name}] RSS fetch failed: {e}")
    except Exception as e:
        log.error(f"[{source_name}] Unexpected error: {e}")

    return items


def scrape_inven_news() -> list:
    """Scrape Inven's game news page for Korean gaming news."""
    items = []
    try:
        url = "https://www.inven.co.kr/webzine/news/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        # Try multiple selectors for robustness
        articles = soup.select("div.news_list a, ul.news_list a, div.webzine_news_list a, a.subject")
        if not articles:
            articles = soup.select("a[href*='/webzine/']")

        seen_urls = set()
        for article in articles[:25]:
            title = article.get_text(strip=True)
            link = article.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.inven.co.kr" + link

            # Filter out navigation/menu links 
            if title and link and len(title) > 5 and link not in seen_urls and "/webzine/" in link:
                seen_urls.add(link)
                items.append({
                    "title": title,
                    "url": link,
                    "summary": "",
                    "source_id": "inven",
                    "source_name": "인벤",
                    "country": "KR",
                    "published": None,
                    "view_count": None,
                })

        log.info(f"[인벤] Collected {len(items)} items")

    except requests.RequestException as e:
        log.warning(f"[인벤] Scraping failed: {e}")
    except Exception as e:
        log.error(f"[인벤] Unexpected error: {e}")

    return items


def scrape_gamemeca() -> list:
    """Scrape GameMeca for Korean gaming news."""
    items = []
    try:
        url = "https://www.gamemeca.com/news.php"
        headers = {"User-Agent": BROWSER_UA, "Accept-Language": "ko-KR,ko;q=0.9"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        # Use verified selector from browser research
        articles = soup.select("a[href*='view.php?gid=']")
        if not articles:
            articles = soup.select("strong.tit_thumb_h a")

        seen_urls = set()
        for article in articles[:25]:
            title = article.get_text(strip=True)
            link = article.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.gamemeca.com" + link

            if title and link and len(title) > 5 and link not in seen_urls:
                seen_urls.add(link)
                items.append({
                    "title": title,
                    "url": link,
                    "summary": "",
                    "source_id": "gamemeca",
                    "source_name": "게임메카",
                    "country": "KR",
                    "published": None,
                    "view_count": None,
                })

        log.info(f"[게임메카] Collected {len(items)} items")

    except requests.RequestException as e:
        log.warning(f"[게임메카] Scraping failed: {e}")
    except Exception as e:
        log.error(f"[게임메카] Unexpected error: {e}")

    return items


def scrape_famitsu() -> list:
    """Scrape Famitsu for Japanese gaming news (RSS no longer available)."""
    items = []
    try:
        url = "https://www.famitsu.com/category/news/page/1"
        headers = {"User-Agent": BROWSER_UA}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("a[href*='/article/']")

        seen_urls = set()
        for article in articles[:25]:
            title = article.get_text(strip=True)
            link = article.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.famitsu.com" + link

            if title and link and len(title) > 5 and link not in seen_urls and "/article/" in link:
                seen_urls.add(link)
                items.append({
                    "title": title,
                    "url": link,
                    "summary": "",
                    "source_id": "famitsu",
                    "source_name": "Famitsu",
                    "country": "JP",
                    "published": None,
                    "view_count": None,
                })

        log.info(f"[Famitsu] Collected {len(items)} items")

    except requests.RequestException as e:
        log.warning(f"[Famitsu] Scraping failed: {e}")
    except Exception as e:
        log.error(f"[Famitsu] Unexpected error: {e}")

    return items


def scrape_dengeki() -> list:
    """Scrape Dengeki Online for Japanese gaming news."""
    items = []
    try:
        url = "https://dengekionline.com/category/game/page/1"
        headers = {"User-Agent": BROWSER_UA}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        # Use verified selector from browser research
        articles = soup.select("a[href*='/article/']")

        seen_urls = set()
        for article in articles[:30]:
            title_el = article.select_one("p")
            title = title_el.get_text(strip=True) if title_el else article.get_text(strip=True)
            link = article.get("href", "")
            if link and not link.startswith("http"):
                link = "https://dengekionline.com" + link

            if title and link and link not in seen_urls and len(title) > 5:
                seen_urls.add(link)
                items.append({
                    "title": title,
                    "url": link,
                    "summary": "",
                    "source_id": "dengeki",
                    "source_name": "電撃オンライン",
                    "country": "JP",
                    "published": None,
                    "view_count": None,
                })

        log.info(f"[電撃オンライン] Collected {len(items)} items")

    except requests.RequestException as e:
        log.warning(f"[電撃オンライン] Scraping failed: {e}")
    except Exception as e:
        log.error(f"[電撃オンライン] Unexpected error: {e}")

    return items


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def title_similarity(t1: str, t2: str) -> float:
    """Calculate similarity between two titles."""
    return SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def deduplicate_items(items: list) -> list:
    """Remove duplicate items based on URL and title similarity."""
    seen_urls = set()
    unique_items = []

    for item in items:
        # Skip duplicate URLs
        if item["url"] in seen_urls:
            continue

        # Skip titles too similar to already accepted items
        is_duplicate = False
        for accepted in unique_items:
            if title_similarity(item["title"], accepted["title"]) >= SIMILARITY_THRESHOLD:
                # Keep the one with more information (longer summary or has view count)
                is_duplicate = True
                break

        if not is_duplicate:
            seen_urls.add(item["url"])
            unique_items.append(item)

    return unique_items


def add_cross_reference_scores(items: list) -> list:
    """
    Add cross-reference scores: if multiple sources mention similar topics,
    increase the importance score.
    """
    for i, item in enumerate(items):
        cross_count = 0
        for j, other in enumerate(items):
            if i != j and item["source_id"] != other["source_id"]:
                sim = title_similarity(item["title"], other["title"])
                if sim >= 0.5:  # Looser threshold for cross-reference
                    cross_count += 1
        item["cross_reference_count"] = cross_count

    return items


def scrape_steam_upcoming() -> list:
    """Scrape Steam's Popular Coming Soon page to find highly anticipated games."""
    items = []
    try:
        url = "https://store.steampowered.com/search/?filter=popularcomingsoon"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("a.search_result_row")
        
        for row in rows[:30]:  # Limit to top 30 popular coming soon games
            title_el = row.select_one("span.title")
            date_el = row.select_one("div.search_released")
            link = row.get("href", "")
            
            if title_el and date_el and link:
                title = title_el.get_text(strip=True)
                date_str = date_el.get_text(strip=True)
                
                items.append({
                    "title": f"[신작 출시] {title} - {date_str} 출시 예정",
                    "url": link.split("?")[0],
                    "summary": f"Steam Popular Coming Soon game. Scheduled Release Date: {date_str}.",
                    "source_id": "steam_upcoming",
                    "source_name": "Steam",
                    "country": "GLOBAL",
                    "published": None,
                    "view_count": None,
                })
        log.info(f"[Steam Upcoming] Collected {len(items)} items")
    except Exception as e:
        log.error(f"[Steam Upcoming] Scraping failed: {e}")
    return items


# ---------------------------------------------------------------------------
# Main collection pipeline
# ---------------------------------------------------------------------------

def collect_all() -> dict:
    """
    Main collection function. Returns a dict with:
    - candidates: list of news items
    - yesterday_sent: list of previously sent items
    - collection_stats: summary stats
    """
    log.info("=" * 60)
    log.info("Starting news collection pipeline")
    log.info("=" * 60)

    # Get yesterday's sent items for LLM context from existing editions
    sent_urls, yesterday_sent = load_recent_editions_cache()
    log.info(f"최근 발행 캐시 로딩: URL {len(sent_urls)}개, 기사 {len(yesterday_sent)}건")

    # ---- Collect from all sources ----
    all_items = []

    # RSS feeds
    for source_id, config in RSS_SOURCES.items():
        items = fetch_rss(source_id, config)
        all_items.extend(items)

    # Web scraping sources (RSS가 없는 사이트만)
    all_items.extend(scrape_famitsu())
    all_items.extend(scrape_dengeki())
    all_items.extend(scrape_steam_upcoming())

    log.info(f"Total raw items collected: {len(all_items)}")

    # ---- Filter already-sent URLs ----
    filtered = []
    for item in all_items:
        normalized = _normalize_url(item["url"])
        if normalized not in sent_urls and item["url"] not in sent_urls:
            filtered.append(item)
            
    log.info(f"After editions filter (중복방지): {len(filtered)} items (Removed {len(all_items) - len(filtered)})")

    # ---- Filter digest/compilation articles ----
    blacklist_words = ["브리핑", "모음", "위클리", "결산", "투데이", "간추린", "뉴스룸"]
    filtered = [item for item in filtered if not any(w in item["title"] for w in blacklist_words)]
    log.info(f"After digest filter: {len(filtered)} items")

    # ---- Deduplicate by title similarity ----
    deduplicated = deduplicate_items(filtered)
    log.info(f"After deduplication: {len(deduplicated)} items")

    # ---- Add cross-reference scores ----
    scored = add_cross_reference_scores(deduplicated)

    # ---- Build stats ----
    stats = {
        "total_raw": len(all_items),
        "after_sent_filter": len(filtered),
        "after_dedup": len(deduplicated),
        "by_country": {},
        "by_source": {},
        "collection_time": datetime.now().isoformat(),
    }
    for item in scored:
        country = item["country"]
        source = item["source_name"]
        stats["by_country"][country] = stats["by_country"].get(country, 0) + 1
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

    log.info(f"Country breakdown: {stats['by_country']}")
    log.info(f"Source breakdown: {stats['by_source']}")

    return {
        "candidates": scored,
        "yesterday_sent": yesterday_sent,
        "stats": stats,
    }


def save_results(results: dict):
    """Save collection results to JSON file."""
    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"Results saved to {output_path}")
    log.info(f"Total candidates: {len(results['candidates'])}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # Python < 3.7
    results = collect_all()
    save_results(results)
    print(f"\n✅ Collection complete: {len(results['candidates'])} candidates")
    print(f"   KR: {results['stats']['by_country'].get('KR', 0)}")
    print(f"   IN: {results['stats']['by_country'].get('IN', 0)}")
    print(f"   JP: {results['stats']['by_country'].get('JP', 0)}")
    print(f"   GLOBAL: {results['stats']['by_country'].get('GLOBAL', 0)}")
