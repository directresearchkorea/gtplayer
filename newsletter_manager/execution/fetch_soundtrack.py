"""
fetch_soundtrack.py — 카테고리 3: 게임 사운드트랙 / Lo-Fi 추천
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
from llm_client import genai

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "soundtrack_output.json"
TMP_DIR = SCRIPT_DIR / ".." / ".." / ".tmp"
EDITIONS_DIR = SCRIPT_DIR / ".." / ".." / "web" / "editions"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_soundtrack")

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

    # If empty, provide generic fallbacks
    if not games:
        games = ["현재 화제가 되고 있는 PC/콘솔 신작", "최근 인기 있는 스팀 인디 게임", "대규모 업데이트를 진행한 MMORPG"]
        
    return games

def _get_last_week_soundtrack() -> str:
    """Finds the most recent soundtrack featured to avoid genre collision."""
    if not EDITIONS_DIR.exists(): return "없음"
    
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)
                snd = d.get("sections", {}).get("soundtrack", {})
                if snd.get("enabled", False) and snd.get("title"):
                    return f"제목: {snd.get('title')} (소개: {snd.get('comment', '')})"
        except: pass
    return "이전 추천곡 없음"

def _generate_search_query(client, trending_games, last_track, skip_games=None) -> dict:
    if skip_games is None: skip_games = []
    prompt = f"""당신은 트렌디한 게임 음악 큐레이터입니다.
아래의 이번 주 게임 트렌드(신작/뉴스)를 바탕으로, 유튜브에서 검색할 '단 1개의 흥미로운 게임 사운드트랙 검색어'를 만들어주세요.

[이번 주 화제의 게임들]
{chr(10).join(trending_games[:10])}

[이전에 추천한 곡 (장르 중복 방지 참고용)]
{last_track}

{f"[검색 실패로 제외할 게임들 - 절대 이 게임들은 고르지 마세요]\n{', '.join(skip_games)}" if skip_games else ""}

지시사항:
1. 위 화제의 게임 중 가장 음악이 좋을 것 같은 게임 1개를 선정하거나, 최근 7일 내 대규모 화제가 된 다른 게임을 골라도 됩니다. (최근 핫한 게임 필수)
2. 유튜브에서 실제로 게임 OST 공식 음원이나 테마곡 검색 결과가 잘 나올 만한 영어 검색어 형태로 조합하세요. 
   **중요**: 만약 선정된 게임이 '확장팩', '시즌', 'DLC' 등 특정 업데이트 버전(예: "디아블로4: 증오의 그릇")이라면, 반드시 그 **전체 부제(Subtitle)를 검색어에 포함**시켜 예전 오리지널 버전의 과거 OST가 검색되는 것을 방지하세요. 
   **중요**: 가급적 공식 채널의 영상이 검색 결과 상단에 나오도록 "Official Soundtrack", "Official Theme", "Launch Trailer" 같은 공식 키워드를 추가하세요. (예: "Diablo 4 Vessel of Hatred Official Theme", "Stellar Blade Official OST")
반드시 아래 JSON 형태로만 출력하세요 (다른 말 절대 금지):
```json
{{
  "game_name": "선정된 게임 이름 (한국어)",
  "reason": "선정 이유 및 이번 주 대비 달라진 분위기 (짧게)",
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
    
    # Fallback
    return {
        "game_name": "화제의 신작 게임",
        "reason": "최근 핫한 게임 OST",
        "youtube_query": random.choice(["popular game OST 2026 relaxing", "trending video game soundtrack playlist", "new game lofi chill mix"])
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
        # "videoDuration": "long", # Removed so we can catch official 2-4 min OST tracks
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
        results.append({
            "videoId": vid_id,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
        })
    return results

def _pick_best_video(videos: list) -> dict | None:
    if not videos: return None
    return videos[0] # 가장 연관성 높은 첫 번째 영상 선택

def _verify_video_match(video: dict, game_context: dict, client) -> bool:
    prompt = f"""유튜브 검색 결과 검증
게임 의도: {game_context.get('game_name')}
검색된 유튜브 영상 제목: {video['title']}
채널명: {video['channel']}

이 영상이 원래 의도한 게임 '{game_context.get('game_name')}'과 연관된 영상(OST, 플레이, 트레일러 등)이 맞습니까? 
이름만 비슷하고 전혀 다른 게임이거나, 완전히 무관한 영상이라면 false를 반환하세요.

반드시 아래 JSON 형태로만 출력하세요 (다른 말 절대 금지):
```json
{{
  "match": true 혹은 false,
  "reason": "판단 이유 (아주 짧게)"
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
            data = json.loads(json_match.group(0))
            return data.get("match", True)
    except Exception as e:
        log.warning(f"Video match verification failed: {e}")
    return True # 에러 시 일단 통과

def _gemini_comment(video: dict, game_context: dict, client) -> str:
    from datetime import datetime
    weekday = datetime.now().weekday()  # 0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일
    weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    weekday_str = weekday_names[weekday]
    
    # 요일별 시간 표현 가이드
    if weekday <= 2:  # 월~수: 주말까지 거리 있음
        time_guide = "오늘은 {0}입니다. '이번 주말에' 같은 표현은 거리가 멀어 어색합니다. '오늘 퇴근길에', '잠들기 전에', '오늘 하루를 마무리하며' 등 오늘/당일 중심의 자연스러운 표현을 사용하세요.".format(weekday_str)
    elif weekday <= 4:  # 목~금: 주말 코앞
        time_guide = "오늘은 {0}입니다. '다가오는 주말에', '이번 주말 플레이리스트로' 등 주말을 자연스럽게 기대하는 표현이 잘 어울립니다.".format(weekday_str)
    else:  # 토~일: 주말 당일
        time_guide = "오늘은 {0}입니다. '이번 주말에', '오늘 게임하면서' 등 주말 당일 분위기에 맞는 표현을 사용하세요.".format(weekday_str)

    prompt = f"""당신은 게임을 사랑하는 독자들에게 매주 가장 매력적인 게임 음악 1곡을 추천하는 큐레이터입니다.
다음 유튜브 영상이 이번 주 추천곡으로 뽑혔습니다. 이 곡은 최근 화제가 된 게임({game_context.get('game_name', '게임')})의 분위기와 관련이 깊거나 해당 게임의 곡입니다.

영상 정보:
- 제목: {video['title']}
- 채널: {video['channel']}

위 추천 영상을 뉴스레터 구독자에게 소개하는 짧은 코멘트를 작성해주세요.
주의사항: **반드시 위 '영상 정보'에 적힌 실제 유튜브 '제목'에 맞는 게임 곡 코멘트를 작성하세요.** 만약 영상 제목과 원래 의도했던 게임명({game_context.get('game_name')})이 서로 다르다면, 무조건 실제 영상 제목에 해당하는 게임을 타겟으로 소개글을 작성해야 합니다. (잘못된 게임명으로 소개하면 안 됨)

작성 규칙:
1. 한국어로 친근한 톤(해요체)으로 작성.
2. 이모지 적극 포함.
3. **가장 중요: 이 곡과 게임이 이번 주에 특별히 선정된 이유를 맥락이 확실히 잡히도록 첫 문장에 자연스럽게 설명하세요. 단, 최신 출시작이 아닌 경우(예: 단순 업데이트, 이벤트, 과거 명작 재조명 등) '신작', '출시' 등의 단어를 써서 억지로 최신작인 것처럼 거짓으로 꾸미지 마세요. 있는 그대로의 소식(대규모 업데이트 기념, 최근 화제가 된 이유 등)을 바탕으로 소개해야 합니다.**
4. **[발행 요일 고려 필수]** {time_guide}
5. 이 뉴스레터는 영어·일본어로도 번역 배포되므로, 한국 특유의 속어·관용구·밈(예: "국룰", "ㅋㅋ", "월급드립" 등)은 피하고, 전 세계 게이머라면 누구나 공감할 수 있는 보편적인 정서와 위트 있는 표현으로 작성할 것.
6. **총 150자 이내로 콤팩트하게 작성할 것.**

출력: 오직 완성된 코멘트 텍스트만 (JSON 등 다른 포맷 금지)"""
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        log.warning(f"Comment generation failed: {e}")
        return f"🎵 이번 주 추천 OST: {video['title']}"

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
                log.info("♻️ 오늘 이미 생성된 사운드트랙 데이터 재사용")
                return
        except: pass

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 1. 큐레이션: 트렌드 및 과거 내역 읽기
    trending_games = _get_trending_games()
    last_track = _get_last_week_soundtrack()
    
    skip_games = []
    MAX_ATTEMPTS = 3
    video = None
    game_context = None
    query = ""
    
    for attempt in range(MAX_ATTEMPTS):
        # 2. AI 검색어 생성
        log.info(f"🤔 AI가 이번 주 화제작과 장르를 분석하여 검색어를 생성중입니다... (시도 {attempt+1}/{MAX_ATTEMPTS})")
        game_context = _generate_search_query(client, trending_games, last_track, skip_games)
        query = game_context.get("youtube_query", "")
        log.info(f"🎯 AI 선정 게임: {game_context.get('game_name')} / 선정이유: {game_context.get('reason')}")
        log.info(f"🔍 유튜브 검색어: {query}")

        # 3. 유튜브 검색
        try:
            videos = _youtube_search(query, max_results=3)
        except Exception as e:
            log.error(f"YouTube search failed: {e}")
            return
            
        video = _pick_best_video(videos)
        if not video:
            log.warning("No videos found. Retrying...")
            skip_games.append(game_context.get('game_name', 'Unknown'))
            continue
            
        log.info(f"선택된 영상: {video['title']} / 채널: {video['channel']}")
        
        # 실제 영상이 게임과 맞는지 검증
        is_match = _verify_video_match(video, game_context, client)
        if is_match:
            log.info("✅ 영상 매칭 검증 통과!")
            break
        else:
            log.warning(f"❌ 영상 매칭 실패 (전혀 다른 영상). 후보에서 제외하고 다시 찾습니다.")
            skip_games.append(game_context.get('game_name', 'Unknown'))
            video = None

    if not video:
        log.error("최대 재시도 횟수를 초과하여 적절한 사운드트랙을 찾지 못했습니다.")
        return

    # 4. AI 코멘트 작성
    comment = _gemini_comment(video, game_context, client)
    log.info(f"💬 생성된 코멘트:\n{comment}")

    # 5. 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "section": "soundtrack",
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

    log.info(f"✅ 사운드트랙 데이터 저장 완료: {OUTPUT_PATH}")

    if test_mode:
        print("\n===== 테스트 결과 =====")
        print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    run(test_mode="--test" in sys.argv)
