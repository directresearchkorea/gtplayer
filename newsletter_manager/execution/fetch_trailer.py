"""
fetch_trailer.py — 카테고리 4 (목요일): 신작 게임 트레일러
Gemini로 화제 게임 선별 및 검색어 생성 -> YouTube Data API -> Gemini 코멘트
"""
import os
import sys
import json
import logging
import random
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "trailer_output.json"
TMP_DIR = SCRIPT_DIR / ".." / ".." / ".tmp"
EDITIONS_DIR = SCRIPT_DIR / ".." / ".." / "web" / "editions"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_trailer")

def _get_trending_games() -> list:
    games = []
    # calendar
    cal_file = TMP_DIR / "calendar_output.json"
    if cal_file.exists():
        try:
            with open(cal_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                for item in d.get("calendar_items", []):
                    games.append(f"[출시/업데이트] {item.get('game', '')}: {item.get('note', '')}")
        except: pass
    
    # briefing
    brf_file = TMP_DIR / "briefing_output.json"
    if brf_file.exists():
        try:
            with open(brf_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                for item in d.get("briefing_items", []):
                    games.append(f"[뉴스] {item.get('title', '')}")
        except: pass

    if not games:
        games = ["가장 기대받는 신작 게임", "최근 공개된 트리플A 게임", "대규모 업데이트 발표작"]
        
    return games

def _get_last_week_trailer() -> str:
    if not EDITIONS_DIR.exists(): return "없음"
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)
                tr = d.get("sections", {}).get("trailer", {})
                if tr.get("enabled", False) and tr.get("title"):
                    return f"제목: {tr.get('title')} (소개: {tr.get('comment', '')})"
        except: pass
    return "이전 트레일러 없음"

def _generate_search_query(client, trending_games, last_track) -> dict:
    prompt = f"""당신은 트렌디한 게임 공식 트레일러 큐레이터입니다.
아래의 이번 주 게임 트렌드(신작/뉴스)를 바탕으로, 유튜브에서 검색할 '단 1개의 흥미로운 게임 공식 트레일러 검색어'를 만들어주세요.

[이번 주 화제의 게임들]
{chr(10).join(trending_games[:10])}

[이전에 추천한 트레일러 (장르/게임 중복 방지 참고용)]
{last_track}

지시사항:
1. 주요 게임사의 신작이거나 사람들의 기대가 매우 큰 화제의 게임을 1개 우선적으로 선정하세요.
2. 유저 반응이 폭발적이거나 비주얼이 압도적인 '공식 트레일러(Official Trailer)' 혹은 '공식 게임플레이(Gameplay)' 영상이 타겟입니다.
3. '이전에 추천한 트레일러'와는 다른 게임, 다른 분위기의 게임을 골라주세요.
4. 유튜브에서 반드시 **개발사 또는 배급사의 공식 채널(official channel)** 영상이 잘 검색되도록 구체적인 영어 검색어 형태로 조합하세요. (예: "Monster Hunter Wilds Official Trailer", "GTA 6 Trailer 1", "Hollow Knight Silksong Gameplay Trailer")

반드시 아래 JSON 형태로만 출력하세요 (다른 말 절대 금지):
```json
{{
  "game_name": "선정된 게임 이름 (한국어)",
  "reason": "선정 이유 및 트레일러의 기대 포인트 (짧게)",
  "youtube_query": "유튜브 검색어"
}}
```"""
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        log.warning(f"Failed to generate query: {e}")
    
    return {
        "game_name": "기대작 트리플A 신작",
        "reason": "가장 기대받는 출시 예정작 공식 트레일러",
        "youtube_query": random.choice(["official game trailer 4k", "upcoming games 2026 trailer", "new RPG reveal trailer"])
    }

def _youtube_search(query: str, max_results: int = 5) -> list:
    import urllib.request
    import urllib.parse
    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "relevance",
        "videoCategoryId": "20", # Gaming category
        "key": YOUTUBE_API_KEY,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    results = []
    for item in data.get("items", []):
        vid_id = item["id"].get("videoId", "")
        snippet = item.get("snippet", {})
        title = snippet.get("title", "")
        
        # 필터링: 리뷰, 리액션, 뉴스 팟캐스트는 거름 (공식 트레일러 유도)
        title_lower = title.lower()
        if any(w in title_lower for w in ["review", "podcast", "reaction", "news", "let's play", "walkthrough"]):
            continue
            
        results.append({
            "videoId": vid_id,
            "title": title,
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "publishedAt": snippet.get("publishedAt", ""),
        })
    return results

def _pick_best_video(videos: list) -> dict | None:
    if not videos: return None
    # B안: 상위 N개(관련성 순으로 품질 검증됨) 중 "가장 최근에 업로드된" 영상을 픽
    sorted_videos = sorted(videos, key=lambda x: x.get("publishedAt", ""), reverse=True)
    return sorted_videos[0]

def _gemini_comment(video: dict, game_context: dict, client) -> str:
    prompt = f"""당신은 유저들에게 신작 게임 소식을 전하는 매거진 큐레이터입니다.
이번 주 화제작으로 '{game_context.get('game_name', '기대작')}'가 선정되었으며, 다음 공식 트레일러 영상이 선정되었습니다.

영상 정보:
- 영상 제목: {video['title']}
- 유튜브 채널: {video['channel']}

위 영상을 바탕으로 게임 뉴스레터 구독자에게 영상을 소개해주세요.

작성 규칙:
1. 밝지만 리뷰 형식이 아닌 간결한 소개 톤으로 작성.
2. 영상에 담긴 게임명을 자연스럽게 소개.
3. 다음 요소 중 정확히 **2가지**만 선택하여 포함할 것:
   [출시 일정, 왜 지금 이슈인지, 게임의 핵심 기대 포인트, 영상 내용 중 가장 독특/하이라이트인 부분, 스토리/장르/회사/플랫폼 정보]
4. 길게 쓰지 말고, 전체 길이를 **3문장 내외**로 제한할 것.
5. 문장 끝에 상황에 맞는 적절한 이모지 1~2개 포함.
6. 이 뉴스레터는 글로벌 번역 배포되므로, 한국 특유의 속어·관용구·밈은 절대 피하고 전 세계 게이머 누구나 공감할 수 있는 짧고 세련된 어휘로 작성.
7. 마지막 줄에 트레일러 감상을 유도하는 가벼운 권유/기대평 한 스푼 추가 가능.

출력: 오직 완성된 코멘트 텍스트만 (JSON 등 다른 포맷 금지)"""
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        log.warning(f"Comment generation failed: {e}")
        return f"🎬 놓치지 말아야 할 공식 트레일러: {video['title']}"

def run(test_mode: bool = False):
    if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
        log.error("API keys missing.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    if OUTPUT_PATH.exists() and not test_mode:
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("generation_time", "")[:10] == today_str:
                log.info("♻️ 오늘 이미 생성된 트레일러 데이터 재사용")
                return
        except: pass

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 1. 큐레이션: 트렌드 읽기
    trending_games = _get_trending_games()
    last_track = _get_last_week_trailer()
    
    # 2. AI 검색어 생성
    log.info("🤔 AI가 이번 주 공식 트레일러를 선정하고 검색어를 생성중입니다...")
    game_context = _generate_search_query(client, trending_games, last_track)
    query = game_context.get("youtube_query", "")
    log.info(f"🎯 AI 선정 게임: {game_context.get('game_name')} / 선정이유: {game_context.get('reason')}")
    log.info(f"🔍 유튜브 검색어: {query}")

    # 3. 유튜브 검색
    try:
        # B안: 고품질 공식 영상을 확보하기 위해 relevance 정렬 유지하되, 후보군을 10개로 늘림
        videos = _youtube_search(query, max_results=10)
    except Exception as e:
        log.error(f"YouTube search failed: {e}")
        return
        
    video = _pick_best_video(videos)
    if not video:
        log.warning("No videos found.")
        return
    log.info(f"🎬 선택된 트레일러: {video['title']} (채널: {video['channel']})")

    # 4. AI 코멘트 작성
    comment = _gemini_comment(video, game_context, client)
    log.info(f"💬 생성된 코멘트:\n{comment}")

    # 5. 결과 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "section": "trailer",
        "content": {
            "title": video["title"],
            "channel": video["channel"],
            "videoId": video["videoId"],
            "url": video["url"],
            "thumbnail": video["thumbnail"],
            "comment": comment,
            "search_query": query,
            "ai_game_name": game_context.get("game_name"),
            "ai_reason": game_context.get("reason"),
        },
        "generation_time": datetime.now().isoformat(),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"✅ 트레일러 데이터 저장 완료: {OUTPUT_PATH}")

    if test_mode:
        print("\n===== 테스트 결과 =====")
        print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    run(test_mode="--test" in sys.argv)
