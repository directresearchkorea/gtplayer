"""
generate_rankings.py — 섹션 6 (게임 순위) 생성
PC: SteamCharts 크롤링 (실시간 동접 기반)
Console/Mobile: Gemini 트렌드 추정 (향후 크롤링 교체 가능)
"""
import os
import sys
import json
import re
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "ranking_output.json"
PREV_RANKING_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "ranking_prev.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_rankings")

# ---------------------------------------------------------------------------
# PC Rankings: SteamCharts Scraping
# ---------------------------------------------------------------------------

def fetch_steam_top(count=5) -> list:
    """Scrape top games from SteamCharts by current players."""
    url = "https://steamcharts.com/top"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        games = []
        # SteamCharts table rows
        rows = soup.select("table#top-games tbody tr")
        if not rows:
            # Fallback: try link-based parsing
            links = soup.select("a[href*='/app/']")
            seen = set()
            for link in links:
                name = link.get_text(strip=True)
                href = link.get("href", "")
                if name and "/app/" in href and name not in seen:
                    seen.add(name)
                    games.append({"game": name, "change": ""})
                    if len(games) >= count:
                        break
        else:
            for row in rows[:count]:
                cols = row.select("td")
                if len(cols) >= 2:
                    name_el = cols[1].select_one("a")
                    name = name_el.get_text(strip=True) if name_el else cols[1].get_text(strip=True)
                    games.append({"game": name, "change": ""})
        
        log.info(f"SteamCharts: fetched {len(games)} games")
        return games
    except Exception as e:
        log.warning(f"SteamCharts scraping failed: {e}")
        return []

# ---------------------------------------------------------------------------
# Change Tracking
# ---------------------------------------------------------------------------

def compute_changes(current: list, prev: list) -> list:
    """Compare current ranking with previous to compute change indicators."""
    prev_map = {item["game"]: idx for idx, item in enumerate(prev)}
    
    for idx, item in enumerate(current):
        game = item["game"]
        if game in prev_map:
            old_idx = prev_map[game]
            diff = old_idx - idx  # positive = moved up
            if diff > 0:
                item["change"] = f"▲{diff}"
            elif diff < 0:
                item["change"] = f"▼{abs(diff)}"
            else:
                item["change"] = "-"
        else:
            item["change"] = "NEW"
    
    return current

# ---------------------------------------------------------------------------
# Console Rankings: Scraping popular console game rankings
# ---------------------------------------------------------------------------

def fetch_console_top(count=3) -> list:
    """Scrape console game rankings from Metacritic or fallback to hardcoded trending."""
    url = "https://www.metacritic.com/browse/game/all/recent/date/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        games = []
        # Try to find game titles from Metacritic
        cards = soup.select("a[href*='/game/'] h3, .c-finderProductCard_title, td.clamp-summary-wrap a")
        seen = set()
        for card in cards:
            name = card.get_text(strip=True)
            if name and name not in seen and len(name) > 2:
                seen.add(name)
                games.append({"game": name, "change": ""})
                if len(games) >= count:
                    break
        
        if games:
            log.info(f"Console: scraped {len(games)} games from Metacritic")
            return games
    except Exception as e:
        log.warning(f"Console scraping failed: {e}")
    
    return []

# ---------------------------------------------------------------------------
# Mobile Rankings: Google Play Store Scraping
# ---------------------------------------------------------------------------

def fetch_mobile_top(count=3) -> list:
    """Scrape top free games from Google Play Store."""
    url = "https://play.google.com/store/games?hl=ko&gl=KR"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        games = []
        # Google Play game titles
        titles = soup.select("span.DdYX5, div.Epkrse, span.sT93pb")
        seen = set()
        for t in titles:
            name = t.get_text(strip=True)
            if name and name not in seen and len(name) > 1:
                seen.add(name)
                games.append({"game": name, "change": ""})
                if len(games) >= count:
                    break
        
        if games:
            log.info(f"Mobile: scraped {len(games)} games from Google Play")
            return games
    except Exception as e:
        log.warning(f"Mobile scraping failed: {e}")
    
    return []

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    # Load previous rankings for change tracking
    prev_pc = []
    prev_console = []
    prev_mobile = []
    if PREV_RANKING_PATH.exists():
        try:
            with open(PREV_RANKING_PATH, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                prev_pc = prev_data.get("pc", [])
                prev_console = prev_data.get("console", [])
                prev_mobile = prev_data.get("mobile", [])
        except:
            pass

    # 1. PC: Real data from SteamCharts
    pc_games = fetch_steam_top(5)
    if pc_games and prev_pc:
        pc_games = compute_changes(pc_games, prev_pc)
    elif pc_games:
        for g in pc_games:
            g["change"] = "-"

    # 2. Console: Web scraping (no LLM)
    console_data = fetch_console_top(3)
    if console_data and prev_console:
        console_data = compute_changes(console_data, prev_console)
    elif console_data:
        for g in console_data:
            g["change"] = "-"

    # 3. Mobile: Google Play scraping (no LLM)
    mobile_data = fetch_mobile_top(3)
    if mobile_data and prev_mobile:
        mobile_data = compute_changes(mobile_data, prev_mobile)
    elif mobile_data:
        for g in mobile_data:
            g["change"] = "-"

    ranking_data = {
        "pc": pc_games,
        "console": console_data,
        "mobile": mobile_data
    }

    # Save current as "previous" for next run
    with open(PREV_RANKING_PATH, "w", encoding="utf-8") as f:
        json.dump(ranking_data, f, ensure_ascii=False, indent=2)

    output = {
        "section": "chart",
        "content": ranking_data,
        "generation_time": datetime.now().isoformat()
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"Rankings saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    run()
