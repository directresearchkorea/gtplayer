"""
curate_briefing.py — 게임 브리핑 (섹션 2) LLM 선별 스크립트
수집된 뉴스 후보에서 Gemini API를 사용해 브리핑 6~7건을 선정합니다.
에디터 호환 형식을 위해 한국어로만 생성합니다.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from llm_client import genai
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COLLECTED_NEWS_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "collected_news.json"
CALENDAR_OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "calendar_output.json"
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "briefing_output.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("curate_briefing")


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
# Section 2: Briefing curation
# ---------------------------------------------------------------------------

def build_briefing_prompt(
    candidates: list,
    yesterday_sent: list,
    calendar_items: list,
) -> str:
    """Build the LLM prompt for briefing section curation."""

    from llm_client import trim_candidates
    candidates = trim_candidates(candidates)
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
        if item.get("section") == "briefing":
            yesterday_lines.append(f"- {item['title']} ({item.get('category', '')})")

    calendar_lines = []
    for item in calendar_items:
        calendar_lines.append(f"- {item.get('game', '')} ({item.get('category', '')})")

    today_str = datetime.now().strftime("%Y-%m-%d (%a)")

    prompt = f"""당신은 20년 경력의 시니어 PR 전문가입니다.
아래 후보 목록에서 [게임 산업의 트렌드와 인사이트]를 실무자 관점에서 분석하고 오늘의 게임 브리핑에 실을 뉴스를 큐레이션해주세요.

오늘 날짜: {today_str}

[후보 리스트]
{chr(10).join(candidate_lines)}

[어제 발송된 브리핑]
{chr(10).join(yesterday_lines) if yesterday_lines else "(없음)"}

[오늘 캘린더 섹션에서 이미 다룬 뉴스]
{chr(10).join(calendar_lines) if calendar_lines else "(없음)"}

⚠️ 필수 필터링 및 큐레이션 규칙 (순서대로 엄격히 적용):
- **[최우선 1] 당일 브리핑 목록 내부 중복 절대 금지:** 선정하는 브리핑 항목들 안에서도 같은 게임, 같은 인물/기업 사건(예: PC Gamer와 IGN이 동시에 보도한 동일 이슈)이 **절대 2개 이상 중복으로 들어가지 않게 딱 1건만** 선정하세요!
- **[최우선 2] 어제 브리핑 및 오늘 캘린더 중복 배제:** 어제 발송된 브리핑이나 오늘 캘린더 섹션 리스트에 이미 존재하는 게임이나 사건/주제는 **절대로 또 선정하지 마세요**. 언론사나 출처(URL)가 달라도 같은 사건(예: 호라이즌 6 발표 등)을 다루고 있다면 무조건 제외해야 합니다! (이 규칙은 다른 어떤 규칙보다 우선합니다)
- **선정 기준:** 반드시 '새로운 소식(발표, 업데이트, 신작 출시, 이벤트 등)'을 담은 팩트 위주의 기사여야 합니다. [반응이 좋은 게임, 인사 이동, 소비자 평가, 순위 및 기록, 업계적으로 의미가 큰 뉴스]를 우선하세요. **특히 실제 출시일이 오늘 기준 3일 초과로 남아 상단 캘린더 섹션에서 다루지 못한 화제의 대형 신작 출시 발표 및 예정 소식(예: '갓 오브 워 신작 발표', '내년 출시 예정 대작' 등)은 적극적으로 이 뉴스 브리핑 섹션에 포함시켜야 합니다.**
- **제외 기준:** 단순 트렌드나 영향이 불명확한 뉴스, 리뷰, 특정 게임 플레이 팁, 개발자 인터뷰, 오피니언, 칼럼 형태의 기사는 제외하세요. (PC/콘솔/모바일 게임 외의 하드웨어나 영화 관련 뉴스도 제외)
- **국가 배분:** 인도/일본/한국을 각각 2개씩 선별하고, 글로벌(GLOBAL) 뉴스를 1~2개 포함하세요. (총 7건 내외)

지시사항:
각 선정된 항목에 대해 아래 JSON 형식으로만 배열을 출력하세요. 어떤 추가 설명이나 마크다운 백틱(```) 텍스트도 포함하지 마세요.

```json
[
  {{
    "category": "discount" | "issue" | "personnel" | "release" | "update",
    "tag": "출시" | "업데이트" | "할인" | "이슈" | "인사이동",
    "title": "한줄 뉴스 제목 (한국어, 30자 이내)",
    "source": "출처 이름",
    "time": "뉴스 발행 날짜 (예: '3월 26일' 등 명확한 날짜로 기재. '오늘' 또는 '1일 전' 등 상대적 표현 금지)",
    "country": "KR" | "IN" | "JP" | "GLOBAL",
    "article_url": "뉴스 기사 URL"
  }}
]
```

중요:
- article_url은 반드시 후보 리스트에 있는 URL 중 하나여야 합니다
- 캘린더 섹션과 절대 겹치지 않도록 하세요
- 비디오 게임과 직접 관련 없는 뉴스는 제외하세요
- JSON 배열만 출력하세요
"""
    return prompt



def deduplicate_briefing_items(items: list) -> list:
    """동일한 이슈/인물/게임이 브리핑 목록 내에 2개 이상 중복 선정된 경우 1개만 남김."""
    import re
    from difflib import SequenceMatcher

    STOPWORDS = {"신작", "출시", "발표", "공개", "예정", "업데이트", "게임", "이슈", "논란", "의혹", "공식", "진행", "개최", "실시"}

    def extract_keywords(text: str, url: str = "") -> set:
        clean = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", text.lower())
        words = set()
        for w in clean.split():
            # 조사 제거
            w = re.sub(r"(은|는|이|가|을|를|의|에|서|로|과|와|도|만)$", "", w)
            if len(w) >= 2 and w not in STOPWORDS:
                words.add(w)
        # URL 슬러그의 핵심 영문 키워드도 보조 추출
        slug_words = [
            sw for sw in re.findall(r"[a-z]{4,}", (url or "").lower())
            if sw not in {"https", "http", "www", "html", "news", "view", "article", "articles", "games", "gaming", "industry", "webzine", "inven", "gamemeca", "famitsu", "pcgamer", "steampowered", "store"}
        ]
        return words, set(slug_words)

    unique = []
    seen_urls = set()
    seen_meta = []

    for item in items:
        if not isinstance(item, dict):
            continue
        url = (item.get("article_url") or "").strip()
        title = (item.get("title") or "").strip()
        if not title:
            continue
        if url and url in seen_urls:
            continue

        title_kws, slug_kws = extract_keywords(title, url)
        is_dup = False
        for prev_title, prev_tkws, prev_skws in seen_meta:
            # 1) 제목 유사도 검사
            if SequenceMatcher(None, title.lower(), prev_title.lower()).ratio() >= 0.55:
                is_dup = True
                break
            # 2) 제목 핵심 키워드 2개 이상 겹침
            if len(title_kws & prev_tkws) >= 2:
                is_dup = True
                break
            # 3) 제목 핵심 키워드 1개 이상 겹치면서 URL 영문 슬러그 키워드도 2개 이상 겹침 (타 매체 동일 외신 번역 기사)
            if len(title_kws & prev_tkws) >= 1 and len(slug_kws & prev_skws) >= 2:
                is_dup = True
                break
            # 4) 영문 URL 슬러그 핵심 키워드가 3개 이상 겹침 (예: nvidia, jensen, huang, investigation)
            if len(slug_kws & prev_skws) >= 3:
                is_dup = True
                break

        if is_dup:
            log.info(f"🔄 중복 브리핑 이슈 자동 제거: {title} ({item.get('source', '')})")
            continue

        if url:
            seen_urls.add(url)
        seen_meta.append((title, title_kws, slug_kws))
        unique.append(item)

    return unique


def curate_briefing(
    client,
    candidates: list,
    yesterday_sent: list,
    calendar_items: list,
) -> list:
    """Use Gemini to select 6-7 briefing items with retry and model fallback."""
    prompt = build_briefing_prompt(candidates, yesterday_sent, calendar_items)

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(MAX_RETRIES):
            try:
                log.info(f"Sending briefing curation to {model_name} (attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0]

                items = json.loads(text)
                items = deduplicate_briefing_items(items)
                tag_order = {"이슈": 0, "출시": 1, "업데이트": 2, "인사이동": 3, "할인": 4, "펀딩": 5, "인수합병": 6, "법률": 7, "행사": 8}
                items.sort(key=lambda x: tag_order.get(x.get("tag", ""), 99))
                log.info(f"Briefing: Selected {len(items)} unique items")
                return items

            except Exception as e:
                log.warning(f"[{model_name}] attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

    return []


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run():
    """Main curation pipeline for Section 2."""
    log.info("=" * 60)
    log.info("Starting briefing curation pipeline")
    log.info("=" * 60)

    if not COLLECTED_NEWS_PATH.exists():
        log.error(f"Collected news not found: {COLLECTED_NEWS_PATH}")
        sys.exit(1)

    with open(COLLECTED_NEWS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data["candidates"]
    yesterday_sent = data.get("yesterday_sent", [])

    calendar_items = []
    if CALENDAR_OUTPUT_PATH.exists():
        with open(CALENDAR_OUTPUT_PATH, "r", encoding="utf-8") as f:
            calendar_data = json.load(f)
            calendar_items = calendar_data.get("calendar_items", [])

    calendar_urls = {item.get("article_url") for item in calendar_items}
    filtered_candidates = [c for c in candidates if c["url"] not in calendar_urls]

    client = init_gemini()
    briefing_items = curate_briefing(client, filtered_candidates, yesterday_sent, calendar_items)

    output = {
        "section": "briefing",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "briefing_items": briefing_items,
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
    print(f"\n✅ Briefing curation complete: {len(result['briefing_items'])} items")
