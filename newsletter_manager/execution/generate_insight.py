"""
generate_insight.py — 섹션 4 (Dr. K 인사이트) 자동 생성
섹션 1, 2 결과를 종합하여 하나의 깊이 있는 업계 인사이트 코멘트를 작성합니다.
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CALENDAR_OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "calendar_output.json"
BRIEFING_OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "briefing_output.json"
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "insight_output.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("generate_insight")

def init_gemini():
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not found in .env")
        sys.exit(1)
    return genai.Client(api_key=GEMINI_API_KEY)

def load_news_context() -> str:
    """Combine Section 1 & 2 results for LLM context."""
    context = []
    if CALENDAR_OUTPUT_PATH.exists():
        with open(CALENDAR_OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data.get("calendar_items", []):
                context.append(f"[캘린더] {item.get('game')} - {item.get('note')}")
    
    if BRIEFING_OUTPUT_PATH.exists():
        with open(BRIEFING_OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data.get("briefing_items", []):
                context.append(f"[브리핑] {item.get('title')}")
    
    return "\n".join(context)

def generate_drk_commentary(client, context: str) -> dict:
    today_str = datetime.now().strftime("%f")
    prompt = f"""당신은 'Dr. K'라는 필명을 사용하는 게임 산업 전문가입니다. 
당신은 업계의 이면을 꿰뚫어 보는 날카로운 통찰력을 가지고 있으며, 냉철하면서도 게임에 대한 애정이 담긴 분석을 제공합니다.

오늘의 주요 뉴스들:
{context}

주요 뉴스들을 종합하여 가장 의미 있는 하나의 주제를 선정하고, 독자들에게 깊이 있는 인사이트를 제공하는 코멘트를 작성해주세요.

작성 가이드라인:
- 불필요한 수식어를 제거하고 간결하게 표현하세요.
- 인사이트 도출 시, 다음 중 최소 하나를 반드시 포함하여 **"그래서 산업 및 소비자들에게 어떤 영향이 있는지"**가 명확하게 드러나도록 작성하세요: [실제 게임 형태의 변화, 소비자 반응, 플랫폼 구조, 게임 소비 구조, 게임 사례, 소비자 심리]

2. 본문:
   - 첫 번째 항목(intro): 독자의 호기심을 끄는 강렬한 2줄짜리 Hook 문장 (디자인상 흰색 네모박스 밖에 단독으로 배치됩니다). 오늘 뉴스에서 발견한 흥미로운 현상이나 질문으로 시작하세요.
   - 두 번째 항목(points): 복잡하고 장황한 서론 없이 바로 본론으로 들어가, 다음 4문단 구조를 명확히 유지하며 전체 약 500자 내외로 콤팩트하게 작성하세요.
     * 1문단: 오늘 뉴스에서 발견한 중요한 현상/팩트 요약
     * 2문단: 산업 및 소비자들에게 미치는 구체적 영향과 의미 분석 (위 가이드라인 요소 포함)
     * 3문단: Dr. K의 핵심 통찰 (가장 중요한 문구는 마크다운 볼드체 처리)
     * 4문단: 마무리 전망 또는 독자에게 던지는 질문
3. 어투: 신뢰감을 주는 전문가적 톤(-입니다, -습니다 체)으로 작성. (해요체 금지)
4. 이 뉴스레터는 영어·일본어로도 번역 배포되므로, 한국 특유의 속어·관용구·밈은 피하고 전 세계 게이머라면 누구나 공감할 수 있는 보편적인 정서와 세련된 어휘로 작성할 것.
5. 문장 중간중간 적절한 이모지 사용.

아래 JSON 형식으로만 파싱 가능하게 출력하세요:

```json
{{
  "title": "인사이트 제목",
  "intro": "2줄짜리 강렬한 Hook 문장 (호기심 유발)",
  "points": "본격적인 4문단 통찰과 핵심 분석 (약 500자 내외, \\n\\n으로 문단 구분)"
}}
```

중요: JSON 객체만 출력하세요. 다른 텍스트는 포함하지 마세요.
"""
    for attempt in range(3):
        try:
            log.info(f"Generating Dr. K commentary (attempt {attempt+1})...")
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            
            return json.loads(text)
        except Exception as e:
            log.warning(f"Failed to generate insight (attempt {attempt+1}): {e}")
            import time
            time.sleep(3)
            
    log.error("All attempts to generate insight failed.")
    return {
        "title": "오늘의 인사이트를 준비 중입니다",
        "intro": "기술적인 문제로 인해 인사이트 생성이 지연되고 있습니다.",
        "points": "잠시 후 다시 확인해 주시기 바랍니다."
    }

def run():
    client = init_gemini()
    context = load_news_context()
    if not context:
        log.warning("No news context found for insight generation.")
    
    insight = generate_drk_commentary(client, context)
    
    output = {
        "section": "drk",
        "content": insight,
        "generation_time": datetime.now().isoformat()
    }
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    log.info(f"Insight saved to {OUTPUT_PATH}")
    return output

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    run()
