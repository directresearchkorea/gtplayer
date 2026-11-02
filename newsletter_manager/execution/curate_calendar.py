"""
curate_calendar.py — 게임 캘린더 (섹션 1 + 1-B) LLM 선별 스크립트
수집된 뉴스 후보에서 Gemini API를 사용해 캘린더 6건을 선정합니다.
에디터 호환 형식을 위해 한국어로만 생성합니다.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COLLECTED_NEWS_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "collected_news.json"
EVENTS_DB_PATH = SCRIPT_DIR / "events_calendar.json"
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "calendar_output.json"

# Section 1-B: upcoming events within this many months
EVENTS_LOOKAHEAD_MONTHS = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("curate_calendar")


# ---------------------------------------------------------------------------
# Gemini API
# ---------------------------------------------------------------------------

PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-flash-lite-latest"
MAX_RETRIES = 2
RETRY_DELAY = 5


def init_gemini():
    """Initialize Gemini API client."""
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not found in .env")
        sys.exit(1)
    return genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Section 1: Calendar curation
# ---------------------------------------------------------------------------

def build_calendar_prompt(candidates: list, yesterday_sent: list) -> str:
    """Build the LLM prompt for calendar section curation."""

    candidate_lines = []
    for i, c in enumerate(candidates, 1):
        cross = f" | 교차출현: {c['cross_reference_count']}곳" if c.get("cross_reference_count", 0) > 0 else ""
        views = f" | 조회수: {c['view_count']}" if c.get("view_count") else ""
        candidate_lines.append(
            f"{i}. {c['title']} | 출처: {c['source_name']} | 국가: {c['country']}{views}{cross}\n"
            f"   URL: {c['url']}\n"
            f"   요약: {c.get('summary', 'N/A')[:100]}"
        )

    yesterday_lines = []
    for item in yesterday_sent:
        if item.get("section") == "calendar":
            yesterday_lines.append(f"- {item['title']} ({item.get('category', '')})")

    today_str = datetime.now().strftime("%Y-%m-%d (%a)")

    prompt = f"""당신은 게임 캘린더 큐레이터입니다. 아래 후보 목록에서 **게임 출시/업데이트/이벤트**에 해당하는 항목만 선정하세요.

오늘 날짜: {today_str}

[후보 리스트]
{chr(10).join(candidate_lines)}

[어제 발송 목록]
{chr(10).join(yesterday_lines) if yesterday_lines else "(없음)"}

⚠️ 캘린더에 포함할 수 있는 항목 (반드시 아래 중 하나):
- "release": 신작 게임 출시, 얼리 액세스 시작, 정식 출시
- "update": 대규모 업데이트, 시즌 출시, DLC 출시
- "event": 베타 테스트 시작/종료, CBT, OBT

❌ 절대 포함하지 말 것:
- 단순 뉴스, 루머, 리뷰, 업계 동향, 매출/실적, 인사/조직 이슈
- 커뮤니티 이슈, 밸런스 패치 논란, 개발 소식
- e스포츠 대회 및 리그 (리그 개막, 매치 결과, 선수 영입 등. e스포츠는 이 캘린더 구역 소속이 아닙니다)
- 여러 소식을 하나로 묶은 '종합 뉴스/브리핑/모음집/투데이' 성격의 기사 (해당 게임만의 단독 기사가 아닐 경우 무조건 제외하세요)
- 게임의 출시/업데이트/이벤트가 아닌 모든 것

지시사항:
1. 위 기준에 맞는 항목만 선정 (최대 6건)
2. **중요:** 단순 업데이트보다 신작 **'출시(release)'** 관련 뉴스를 최우선으로 선정하세요.
3. **중요 (출처 우선순위):** 링크(article_url) 추출 시, 가급적 한국(KR) 미디어나 영미권(IN, GLOBAL) 미디어의 기사를 최우선으로 선정하세요. 일본(JP) 매체의 기사는 아주 중요한 글로벌 릴리즈가 아니거나 다른 출처가 없을 경우에만 최소한으로 사용하세요.
4. 오늘({today_str}) 기준 실제 출시일/업데이트일/이벤트 시작일이 3일 이내(오늘, 내일, 모레)인 게임 및 이벤트만 선정하세요. 실제 출시일/업데이트일이 오늘 기준으로 3일보다 많이 남았거나 먼 미래에 출시된다는 단순 발표/뉴스(예: '내년 출시', '2027년 출시', '수개월 뒤 출시')는 캘린더에 절대 선정하지 마세요. (그러한 소식은 하단의 뉴스 브리핑 섹션으로 가야 합니다.)
5. 어제 발송 목록과 중복되는 주제 제외
6. 날짜 정확성: 기사에 시차(예: 현지 28일, 한국 29일)로 인해 날짜가 혼용되어 있다면 기사 본문의 맥락을 파악하여 가장 정확한 공식 출시일을 적어주세요.
7. 각 항목에 대해 아래 JSON 형식으로 출력하세요:

```json
[
  {{
    "category": "release" | "update" | "event",
    "game": "게임 이름 (한국어)",
    "dev": "개발사 (한국어)",
    "date": "날짜 (한국어, 예: '3월 20일(목)')",
    "platforms": ["PC", "PS5"],
    "color": "#10b981",
    "note": "신작/업데이트 내용 설명 (가볍고 명확한 한 문장으로 작성. 출시일, 게임 장르/정보, 핵심 내용을 모두 포함. 예: '3월 26일 정식 출시되는 액션 RPG로, 신규 캐릭터 3종과 스토리 모드가 추가됩니다.')",
    "country": "KR" | "IN" | "JP",
    "article_url": "가장 상세한 뉴스 기사 URL (후보 리스트에서 선택)",
    "source_name": "출처 이름"
  }}
]
```

중요: 
- article_url은 반드시 후보 리스트에 있는 URL 중 하나여야 합니다
- 기준에 맞지 않는 뉴스를 억지로 포함하지 마세요. 0건이어도 됩니다.
- JSON 배열만 출력하세요
"""
    return prompt


def curate_calendar(client, candidates: list, yesterday_sent: list) -> list:
    """Use Gemini to select 6 calendar items with retry and model fallback."""
    prompt = build_calendar_prompt(candidates, yesterday_sent)

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(MAX_RETRIES):
            try:
                log.info(f"Sending calendar curation to {model_name} (attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0]

                items = json.loads(text)
                log.info(f"Calendar: Selected {len(items)} items")
                return items

            except json.JSONDecodeError as e:
                log.error(f"Failed to parse Gemini JSON: {e}")
                return []
            except Exception as e:
                log.warning(f"[{model_name}] attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

    return []


# ---------------------------------------------------------------------------
# Section 1-B: Dynamic Events & Global events
# ---------------------------------------------------------------------------

def build_dynamic_events_prompt(candidates: list) -> str:
    candidate_lines = []
    for i, c in enumerate(candidates, 1):
        candidate_lines.append(
            f"{i}. {c['title']} | 요약: {c.get('summary', 'N/A')[:100]}\n   URL: {c['url']}"
        )

    today_str = datetime.now().strftime("%Y-%m-%d (%a)")

    prompt = f"""당신은 게임 행사 및 이벤트 캘린더 큐레이터입니다.
아래 뉴스 후보 목록을 읽고, **이번 주 또는 다가오는 주요 '게임 관련 행사/이벤트'** 일정이 포함된 뉴스가 있다면 1~2건을 추출하세요.

오늘 날짜: {today_str}

[후보 리스트]
{chr(10).join(candidate_lines)}

⚠️ 추출 대상 이벤트 종류 (아래 중 하나에 해당해야 함):
- 온라인 쇼케이스 (예: Nintendo Direct, State of Play, 개발자 라이브 방송)
- e스포츠 대회 결승 및 주요 매치 일정
- 대형 오프라인 팝업 스토어, 오프라인 이벤트
- 주요 게임의 주말 한정 베타 테스트 (CBT, OBT) 일정
(* 단순 출시일 발표 뉴스는 제외하세요. 실제 '행사/방송/테스트'가 벌어지는 일정만 해당됩니다.)

조건에 맞는 이벤트가 없으면 빈 배열 []을 출력하세요.
있다면 아래 JSON 배열 형식으로 출력하세요:
```json
[
  {{
    "name": "이벤트 이름 (예: LCK 서머 결승전)",
    "note": "간단한 부연 설명 (예: T1 vs GEN.G)",
    "venue": "온라인 / 오프라인 장소 (예: 잠실 실내체육관, Twitch)",
    "date": "이벤트 날짜 (예: 2026-04-05 ~ 04-06)",
    "tag": "e스포츠" | "쇼케이스" | "오프라인 행사" | "베타 테스트",
    "website": "뉴스 기사 URL"
  }}
]
```
중요: JSON 배열만 출력하세요.
"""
    return prompt


def curate_dynamic_events(client, candidates: list) -> list:
    prompt = build_dynamic_events_prompt(candidates)
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(MAX_RETRIES):
            try:
                log.info(f"Sending dynamic events curation to {model_name}...")
                response = client.models.generate_content(model=model_name, contents=prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0]
                items = json.loads(text)
                log.info(f"Dynamic Events: Found {len(items)} items")
                return items
            except Exception as e:
                log.warning(f"[{model_name}] dynamic events attempt {attempt+1} failed: {e}")
                time.sleep(1)
    return []


def get_upcoming_events() -> list:
    """Filter events_calendar.json for events within 3-6 months."""
    if not EVENTS_DB_PATH.exists():
        return []

    with open(EVENTS_DB_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)

    today = datetime.now().date()
    cutoff = today + timedelta(days=EVENTS_LOOKAHEAD_MONTHS * 30)

    upcoming = []
    for event in events:
        start = datetime.strptime(event["start_date"], "%Y-%m-%d").date()
        if today <= start <= cutoff:
            days_until = (start - today).days
            event["d_day"] = days_until
            event["d_day_str"] = f"D-{days_until}" if days_until > 0 else "D-Day"
            upcoming.append(event)

    upcoming.sort(key=lambda x: x["d_day"])
    return upcoming[:2]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run():
    """Main curation pipeline for Section 1 + 1-B."""
    log.info("=" * 60)
    log.info("Starting calendar curation pipeline")
    log.info("=" * 60)

    if not COLLECTED_NEWS_PATH.exists():
        log.error(f"Collected news not found: {COLLECTED_NEWS_PATH}")
        sys.exit(1)

    with open(COLLECTED_NEWS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data["candidates"]
    yesterday_sent = data.get("yesterday_sent", [])
    log.info(f"Loaded {len(candidates)} candidates")

    client = init_gemini()
    calendar_items_raw = curate_calendar(client, candidates, yesterday_sent)
    
    # 3일 이내 출시/업데이트 일정만 필터링하는 후처리 로직 추가
    calendar_items = []
    today = datetime.now().date()
    current_year = today.year
    
    import re
    def parse_item_date(date_str):
        year_match = re.search(r'(\d{4})\s*년', str(date_str))
        if not year_match:
            year_match = re.search(r'(\d{4})\s*[-./]', str(date_str))
        year = int(year_match.group(1)) if year_match else current_year
        
        m = re.search(r'(\d+)월\s*(\d+)일', str(date_str))
        if m:
            return (year, int(m.group(1)), int(m.group(2)))
        m2 = re.search(r'(\d+)/(\d+)', str(date_str))
        if m2:
            return (year, int(m2.group(1)), int(m2.group(2)))
        m3 = re.search(r'(\d+)-(\d+)', str(date_str))
        if m3:
            return (year, int(m3.group(1)), int(m3.group(2)))
        return None

    for item in calendar_items_raw:
        date_str = item.get("date", "")
        parsed = parse_item_date(date_str)
        if parsed:
            try:
                item_date = datetime(parsed[0], parsed[1], parsed[2]).date()
                diff_days = (item_date - today).days
                # 출시 예정일이 오늘 기준으로 3일 이내(어제 출시 포함해 -1 ~ 3일 이내)인 항목만 통과
                if -1 <= diff_days <= 3:
                    calendar_items.append(item)
                else:
                    log.info(f"Filtered out calendar item (not within 3 days): {item.get('game')} ({date_str})")
            except ValueError:
                # 날짜 변환 에러 시 안전을 위해 잔류
                calendar_items.append(item)
        else:
            # 날짜 파싱이 안 되는 경우는 먼 미래 일정으로 간주하여 필터링
            log.info(f"Filtered out calendar item (unparseable date): {item.get('game')} ({date_str})")

    dynamic_events = curate_dynamic_events(client, candidates)
    upcoming_events = get_upcoming_events()

    # Mix dynamic and static events (max 2 total)
    mixed_events = dynamic_events.copy()
    static_mapped = [
        {
            "name": e["name_ko"],
            "note": e.get("note_ko", ""),
            "venue": e["city_ko"],
            "date": f"{e['start_date']}~{e['end_date']}",
            "tag": "오프라인 행사",
            "d_day_str": e["d_day_str"],
            "website": e.get("website", "")
        }
        for e in upcoming_events
    ]
    
    for se in static_mapped:
        if len(mixed_events) < 2:
            mixed_events.append(se)

    output = {
        "section": "calendar",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "calendar_items": calendar_items,
        "upcoming_events": mixed_events,
        "generation_time": datetime.now().isoformat(),
    }

    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"Output saved to {output_path}")
    return output


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    result = run()
    print(f"\n✅ Calendar curation complete: {len(result['calendar_items'])} items")
