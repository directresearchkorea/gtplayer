"""
generate_feedback.py — 섹션 3 / 화요일 미디어 슬롯 (글로벌 최신 게임 유저 반응 및 리뷰 분석) 자동 생성
GTcrawling(crawling_*.db) 및 GTanalysis(processed_*.db)와 직접 연동하여
2개 게임의 커뮤니티 여론(긍/부정 비율, 키워드, 유저 베스트 반응 3줄)을 생성합니다.
"""
import os
import sys
import json
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from llm_client import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TRACKED_GAMES_PATH = SCRIPT_DIR / "tracked_games.json"
_DEFAULT_DB_DIR = BASE_DIR / "GTcrawling" / "data" / "output"
_env_analysis_dir = Path(os.getenv("GTANALYSIS_TMP_DIR", str(_DEFAULT_DB_DIR)))
_env_crawling_dir = Path(os.getenv("GTCRAWLING_OUT_DIR", str(_DEFAULT_DB_DIR)))
GTANALYSIS_TMP_DIR = _env_analysis_dir if _env_analysis_dir.exists() else _DEFAULT_DB_DIR
GTCRAWLING_OUT_DIR = _env_crawling_dir if _env_crawling_dir.exists() else _DEFAULT_DB_DIR
OUTPUT_PATH = BASE_DIR / ".tmp" / "feedback_output.json"

CATEGORY_LABELS = {
    "GAMEPLAY": "🎮 게임플레이·전투",
    "STORY": "📖 스토리·연출",
    "OPTIMIZATION": "⚙️ 최적화·버그",
    "MONETIZATION": "💰 BM·과금 모델",
    "GRAPHIC": "🎨 그래픽·비주얼",
    "COMMUNITY": "💬 운영·커뮤니티",
    "SOUND": "🎧 사운드·OST",
    "BALANCE": "⚖️ 밸런스·메타",
}

SOURCE_LABELS = {
    "inven": "인벤",
    "dc": "디시인사이드",
    "dcinside": "디시인사이드",
    "ruliweb": "루리웹",
    "steam": "Steam",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("generate_feedback")


def get_sorted_active_games() -> tuple[dict, list]:
    """Return full tracked_games config and active games sorted by oldest last_featured date."""
    if not TRACKED_GAMES_PATH.exists():
        log.error("tracked_games.json not found")
        return {}, []

    with open(TRACKED_GAMES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    active_games = [g for g in data.get("tracked_games", []) if g.get("status") == "active"]
    active_games.sort(key=lambda x: x.get("last_featured", "1970-01-01"))
    return data, active_games


def mark_games_featured(data: dict, featured_names: list[str]):
    """Update last_featured in tracked_games.json only for games that succeeded."""
    if not data or not featured_names:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    for tg in data.get("tracked_games", []):
        if tg.get("name") in featured_names:
            tg["last_featured"] = today
    with open(TRACKED_GAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_int(val) -> int:
    try:
        clean = re.sub(r"[^\d-]", "", str(val or "0"))
        return int(clean) if clean else 0
    except Exception:
        return 0


def _connect_ro(db_path: Path):
    """Connect to SQLite in read-only mode with timeout to prevent lock issues."""
    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=15)
    except Exception:
        return sqlite3.connect(str(db_path), timeout=15)


def analyze_game(game_cfg: dict) -> dict | None:
    """Analyze one game using GTanalysis processed_*.db and GTcrawling crawling_*.db."""
    game_name = game_cfg.get("name", "")
    proc_db_name = game_cfg.get("processed_db", "")
    crawl_db_name = game_cfg.get("crawling_db", "")

    proc_db_path = GTANALYSIS_TMP_DIR / proc_db_name if proc_db_name else None
    crawl_db_path = GTCRAWLING_OUT_DIR / crawl_db_name if crawl_db_name else None

    pos_cnt = neu_cnt = neg_cnt = 0
    keywords = []
    sources_set = set()
    top_texts = []
    fallback_comments = []
    total_posts_count = 0

    # 1. Read sentiment & aspect breakdown from GTanalysis processed_*.db if available
    if proc_db_path and proc_db_path.exists():
        conn = None
        try:
            conn = _connect_ro(proc_db_path)
            cur = conn.cursor()
            tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

            if "analyzed_aspects" in tables:
                try:
                    rows = cur.execute(
                        "SELECT category, sentiment, source FROM ("
                        "  SELECT category, sentiment, source, rowid FROM analyzed_aspects ORDER BY rowid DESC LIMIT 2000"
                        ")"
                    ).fetchall()
                    total_posts_count = len(rows)
                    cat_sent = {}
                    for cat, sent, src in rows:
                        sent_u = (sent or "NEUTRAL").upper()
                        if "POS" in sent_u:
                            pos_cnt += 1
                        elif "NEG" in sent_u:
                            neg_cnt += 1
                        else:
                            neu_cnt += 1
                        if src:
                            sources_set.add(SOURCE_LABELS.get(str(src).lower(), str(src)))
                        if cat and cat != "OTHER":
                            entry = cat_sent.setdefault(cat, {"pos": 0, "neg": 0, "total": 0})
                            entry["total"] += 1
                            if "POS" in sent_u:
                                entry["pos"] += 1
                            elif "NEG" in sent_u:
                                entry["neg"] += 1

                    sorted_cats = sorted(cat_sent.items(), key=lambda kv: kv[1]["total"], reverse=True)
                    for cat, st in sorted_cats[:5]:
                        label = CATEGORY_LABELS.get(cat, cat)
                        is_pos = st["pos"] >= st["neg"]
                        keywords.append({"text": label, "positive": is_pos})
                except Exception as e:
                    log.warning(f"Failed querying analyzed_aspects for {game_name}: {e}")

            if "daily_popular_posts" in tables:
                try:
                    pop_rows = cur.execute(
                        "SELECT title, views, recommends, source FROM daily_popular_posts ORDER BY date DESC, views DESC LIMIT 15"
                    ).fetchall()
                    seen_titles = set()
                    for title, views, recs, src in pop_rows:
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            if src:
                                sources_set.add(SOURCE_LABELS.get(str(src).lower(), str(src)))
                            top_texts.append(f"[조회 {views}] {title}")
                            if len(top_texts) >= 10:
                                break
                except Exception as e:
                    log.warning(f"Failed querying daily_popular_posts for {game_name}: {e}")
        except Exception as e:
            log.warning(f"Failed reading processed DB for {game_name}: {e}")
        finally:
            if conn:
                conn.close()

    # 2. Read recent popular posts & body text from GTcrawling crawling_*.db
    if crawl_db_path and crawl_db_path.exists():
        conn = None
        try:
            conn = _connect_ro(crawl_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

            if "posts" in tables:
                rows = [dict(r) for r in cur.execute("SELECT * FROM posts ORDER BY rowid DESC LIMIT 500").fetchall()]
                if not total_posts_count:
                    total_posts_count = len(rows)
                for r in rows:
                    src = r.get("source", "")
                    if src:
                        sources_set.add(SOURCE_LABELS.get(str(src).lower(), str(src)))
                    r["_views"] = _parse_int(r.get("views", 0))

                sorted_posts = sorted(rows, key=lambda x: x["_views"], reverse=True)
                seen_titles = set()
                crawl_texts = []
                for p in sorted_posts:
                    title = (p.get("title") or "").strip()
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)
                    body = (p.get("content_text") or "")[:200].replace("\n", " ").strip()
                    crawl_texts.append(f"[조회 {p['_views']}] {title}: {body}")
                    if len(fallback_comments) < 3 and (body or title):
                        snippet = (body if len(body) > 15 else title)[:90]
                        fallback_comments.append({"text": snippet, "positive": True})
                    if len(crawl_texts) >= 10:
                        break
                if crawl_texts:
                    top_texts = crawl_texts
        except Exception as e:
            log.warning(f"Failed reading crawling DB for {game_name}: {e}")
        finally:
            if conn:
                conn.close()

    if not total_posts_count and not top_texts:
        log.warning(f"No data found for {game_name}")
        return None

    total_sent = pos_cnt + neu_cnt + neg_cnt
    if total_sent > 0:
        pos_p = round(pos_cnt / total_sent * 100)
        neg_p = round(neg_cnt / total_sent * 100)
        neu_p = max(0, 100 - pos_p - neg_p)
        score = round((pos_p * 5 + neu_p * 3 + neg_p * 1) / 100, 1)
    else:
        pos_p, neu_p, neg_p = 35, 45, 20
        score = 3.3

    if not keywords:
        keywords = [
            {"text": "🎮 인게임 플레이", "positive": True},
            {"text": "⚖️ 밸런스·패치", "positive": False},
            {"text": "💬 커뮤니티 화제", "positive": True},
        ]

    sources_str = " · ".join(sorted(sources_set)) if sources_set else "커뮤니티"

    return {
        "game": game_name,
        "period": "최근 커뮤니티 동향",
        "count": f"{total_posts_count:,}",
        "sources": sources_str,
        "score": str(score),
        "pos": pos_p,
        "neu": neu_p,
        "neg": neg_p,
        "keywords": keywords,
        "comments": fallback_comments,
        "_top_texts": top_texts,
        "_needs_sent_estimate": total_sent == 0,
    }


def run(count: int = 2):
    log.info("Starting Community User Feedback generation (GTcrawling + GTanalysis linked)")
    cfg_data, candidates = get_sorted_active_games()

    game_data = []
    featured_names = []
    for g in candidates:
        res = analyze_game(g)
        if res:
            game_data.append(res)
            featured_names.append(g["name"])
            if len(game_data) >= count:
                break

    mark_games_featured(cfg_data, featured_names)

    if GEMINI_API_KEY and game_data:
        all_texts = {}
        needs_est = {}
        for gd in game_data:
            all_texts[gd["game"]] = gd.pop("_top_texts", [])
            needs_est[gd["game"]] = gd.pop("_needs_sent_estimate", False)

        if any(all_texts.values()):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                game_sections = []
                for game_name, texts in all_texts.items():
                    if texts:
                        game_sections.append(f"[{game_name}]\n" + "\n".join(texts))

                batch_prompt = f"""아래는 한국 주요 게임 커뮤니티(인벤, 디시인사이드, 루리웹)의 최근 인기 게시글 목록입니다.
각 게임별로 커뮤니티 핵심 키워드(3~4개), 감성 비율(pos/neu/neg 합계 100), 그리고 유저 반응을 대변하는 **3줄 코멘트**를 정리해주세요.

규칙:
- comments: 실제 유저 입장에서 말하듯이 자연스러운 해요체로 작성 (예: "전투 타격감과 보스 연출은 확실히 기대 이상이에요", "최적화 패치가 빨리 이루어지면 좋겠어요")
- 평론가 톤(~합니다, ~입니다)이나 반말 금지. 각 코멘트는 한 문장, 45자 이내
- keywords: 이모지 1개 + 핵심 주제(예: "⚔️ 보스전 연출", "⚙️ 프레임 최적화", "💰 과금 피로도")와 긍정/부정(positive: true/false) 표시

{chr(10).join(game_sections)}

반드시 아래 JSON 형식으로만 출력하세요:
```json
{{
  "게임이름": {{
    "pos": 40,
    "neu": 40,
    "neg": 20,
    "keywords": [
      {{"text": "🎮 키워드1", "positive": true}},
      {{"text": "⚙️ 키워드2", "positive": false}},
      {{"text": "📖 키워드3", "positive": true}}
    ],
    "comments": [
      {{"text": "유저 반응 한 줄 1", "positive": true}},
      {{"text": "유저 반응 한 줄 2", "positive": false}},
      {{"text": "유저 반응 한 줄 3", "positive": true}}
    ]
  }}
}}
```"""
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=batch_prompt,
                )
                json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
                if json_match:
                    batch_result = json.loads(json_match.group(0))
                    for gd in game_data:
                        gname = gd["game"]
                        if gname in batch_result:
                            b = batch_result[gname]
                            if isinstance(b, dict):
                                if b.get("comments"):
                                    gd["comments"] = b["comments"]
                                if b.get("keywords"):
                                    gd["keywords"] = b["keywords"]
                                if needs_est.get(gname) and "pos" in b and "neg" in b:
                                    raw_pos = max(0, _parse_int(b.get("pos", 35)))
                                    raw_neu = max(0, _parse_int(b.get("neu", 45)))
                                    raw_neg = max(0, _parse_int(b.get("neg", 20)))
                                    tot = raw_pos + raw_neu + raw_neg
                                    if tot > 0:
                                        p_pos = round(raw_pos / tot * 100)
                                        p_neg = round(raw_neg / tot * 100)
                                        p_neu = max(0, 100 - p_pos - p_neg)
                                    else:
                                        p_pos, p_neu, p_neg = 35, 45, 20
                                    gd["pos"], gd["neu"], gd["neg"] = p_pos, p_neu, p_neg
                                    gd["score"] = str(round((p_pos * 5 + p_neu * 3 + p_neg * 1) / 100, 1))
                            elif isinstance(b, list):
                                gd["comments"] = b
                log.info(f"✅ Batch LLM: summarized {len(game_data)} games in 1 call")
            except Exception as e:
                log.warning(f"Batch LLM summarization failed: {e}")

    for gd in game_data:
        gd.pop("_top_texts", None)
        gd.pop("_needs_sent_estimate", None)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "section": "feedback",
        "items": game_data,
        "generation_time": datetime.now().isoformat(),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"✅ Feedback saved to {OUTPUT_PATH} ({len(game_data)} games)")
    return output


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    run()
