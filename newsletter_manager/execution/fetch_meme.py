"""
fetch_meme.py — 월요일 섹션: 주말 화제의 짤 / 영상
Reddit에서 지난 72시간 내 추천수 1위 게임 밈/영상 1개 선정 → Gemini 코멘트 생성
"""

import os
import sys
import json
import re
import logging
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from llm_client import genai

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "meme_output.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_meme")

# ── Reddit 서브레딧 목록 ────────────────────────────────────────
SUBREDDITS = [
    "gaming",
    "GameMemes",
    "pcmasterrace",
]


def _fetch_reddit_top(subreddit: str, limit: int = 25) -> list:
    """meme-api.com을 사용하여 지정된 서브레딧의 인기 밈 수집"""
    import requests
    posts = []
    url = f"https://meme-api.com/gimme/{subreddit}/{limit}"
    log.info(f"meme-api.com을 통해 r/{subreddit} 수집 시도: {url}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("memes", []):
                if m.get("nsfw") or m.get("spoiler"):
                    continue
                
                posts.append({
                    "title": m.get("title", ""),
                    "score": m.get("ups", 0),
                    "url": m.get("url", ""),
                    "preview_img": m.get("url", ""), # 원본 이미지 URL이 이메일 템플릿에 가장 잘 맞음
                    "permalink": m.get("postLink", ""),
                    "subreddit": m.get("subreddit", ""),
                    "author": m.get("author", ""),
                    "num_comments": 0
                })
            log.info(f"r/{subreddit}: meme-api.com을 통해 {len(posts)}개 게시물 수집 성공!")
        else:
            log.warning(f"meme-api.com 실패 (Status Code: {r.status_code})")
    except Exception as e:
        log.warning(f"meme-api.com 수집 예외 발생: {e}")
        
    return posts


def _pick_best_meme(all_posts: list) -> dict | None:
    """전체 게시물 중 추천수 최고 1개 선정"""
    seen = set()
    unique = []
    for p in all_posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique[0] if unique else None


def _gemini_comment(meme: dict, client) -> dict:
    """Gemini로 밈 소개 코멘트 생성 (무슨 일인가요 + 오늘의 한마디)"""
    prompt = f"""당신은 지난 주말 사이 Reddit에서 가장 반응이 뜨거웠던 게임 밈(Meme)이나 화제 영상 1개를 소개하는 큐레이터입니다.

아래 게시물이 선정되었습니다:
- 제목: {meme['title']}
- 추천수: {meme['score']}
- 서브레딧: r/{meme['subreddit']}

아래 두 항목을 한국어로 작성해주세요:
1. 무슨 일인가요?: 첨부된 이미지(있을 경우)와 제목을 보고 어떤 게임의 어떤 상황인지, 이 밈이 왜 이렇게 핫한지 2줄 이내로 간결하게 설명하세요. 사진을 보고 파악한 시각적 유머 코드를 반드시 포함하세요. 밈의 원본 제목을 자연스럽게 한국어로 의역할 것.
2. 오늘의 한마디: 이 밈을 본 당신의 짧은 감상이나 위트 있는 참견. 유쾌하고 공감가는 톤, 이모지 1~2개 포함. 전 세계 게이머라면 누구나 공감할 수 있는 보편적인 유머로 작성할 것.

반드시 아래 JSON 형태로만 출력하세요 (다른 말 절대 금지):
```json
{{
  "what_happened": "무슨 일인가요 내용",
  "one_liner": "오늘의 한마디 내용"
}}
```"""
    contents = [prompt]
    url = meme.get("url", "")
    if url.endswith((".jpg", ".jpeg", ".png", ".webp")):
        import urllib.request
        from google.genai import types
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    img_data = resp.read()
                    import mimetypes
                    mime, _ = mimetypes.guess_type(url)
                    if not mime: mime = "image/jpeg"
                    contents.append(types.Part.from_bytes(data=img_data, mime_type=mime))
                    log.info("🖼️ 밈 코멘트 분석을 위해 원본 이미지를 Gemini에 첨부했습니다.")
        except Exception as e:
            log.warning(f"이미지 다운로드 실패 (Vision 분석 불가): {e}")
            
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=contents,
        )
        text = response.text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        log.warning(f"Gemini comment generation failed: {e}")
        
    return {
        "what_happened": f"Reddit에서 추천수 {meme['score']}을 기록한 화제의 게임 밈입니다.",
        "one_liner": f"😂 {meme['title']}"
    }


def _get_fallback_meme():
    """최근 에디션들 중 meme 섹션이 활성화된 가장 최근 에디션의 데이터를 가져옵니다."""
    try:
        import glob
        editions_dir = SCRIPT_DIR / ".." / ".." / "web" / "editions"
        files = sorted(glob.glob(str(editions_dir / "edition_*.json")), reverse=True)
        for f in files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                meme = data.get("sections", {}).get("meme", {})
                if meme.get("enabled") and (meme.get("url") or meme.get("title")):
                    log.info(f"♻️ 이전 에디션({Path(f).name})의 밈 데이터를 폴백으로 사용합니다.")
                    return meme
    except Exception as e:
        log.error(f"폴백 밈 데이터 로드 중 오류: {e}")
    return None


def run(test_mode: bool = False):
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not found in .env")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    if OUTPUT_PATH.exists() and not test_mode:
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("generation_time", "")[:10] == today_str:
                log.info("♻️ 오늘 이미 생성된 밈 데이터 재사용")
                return
        except: pass

    # Step 1: Reddit에서 밈 수집
    log.info("😆 Reddit에서 주말 인기 게임 밈 수집 중...")
    all_posts = []
    for sub in SUBREDDITS:
        try:
            posts = _fetch_reddit_top(sub, limit=25)
            log.info(f"r/{sub}: {len(posts)}개 이미지/영상 게시물 수집 완료")
            all_posts.extend(posts)
        except Exception as e:
            log.warning(f"r/{sub} 수집 실패: {e}")

    # Step 2: 추천수 1위 선정
    best = _pick_best_meme(all_posts)
    if not best:
        log.warning("적합한 밈/영상을 찾지 못했습니다. 이전 에디션에서 폴백합니다.")
        fallback = _get_fallback_meme()
        if fallback:
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            output = {
                "section": "meme",
                "content": {
                    "title": fallback.get("title", ""),
                    "score": fallback.get("score", 0),
                    "url": fallback.get("url", ""),
                    "preview_img": fallback.get("preview_img", ""),
                    "permalink": fallback.get("permalink", ""),
                    "subreddit": fallback.get("subreddit", ""),
                    "author": fallback.get("author", ""),
                    "num_comments": fallback.get("num_comments", 0),
                    "what_happened": fallback.get("what_happened", ""),
                    "one_liner": fallback.get("one_liner", ""),
                },
                "generation_time": datetime.now().isoformat(),
            }
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            log.info("폴백 밈 데이터 저장 완료")
        return

    log.info(f"🏆 선정된 밈: [{best['score']}점] {best['title'][:60]}")

    # Step 3: Gemini로 코멘트 생성
    client = genai.Client(api_key=GEMINI_API_KEY)
    comment_data = _gemini_comment(best, client)
    log.info(f"💬 무슨 일인가요: {comment_data.get('what_happened', '')}")
    log.info(f"💬 오늘의 한마디: {comment_data.get('one_liner', '')}")

    # Step 4: 결과 저장 (단일 밈 구조)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "section": "meme",
        "content": {
            "title": best["title"],
            "score": best["score"],
            "url": best["url"],
            "preview_img": best["preview_img"],
            "permalink": best["permalink"],
            "subreddit": best["subreddit"],
            "author": best["author"],
            "num_comments": best["num_comments"],
            "what_happened": comment_data.get("what_happened", ""),
            "one_liner": comment_data.get("one_liner", ""),
        },
        "generation_time": datetime.now().isoformat(),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 밈 데이터 저장 완료: {OUTPUT_PATH}")

    if test_mode:
        print("\n===== 테스트 결과 =====")
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    run(test_mode="--test" in sys.argv)
