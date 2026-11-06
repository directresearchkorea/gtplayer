"""
generate_subject.py — 생성된 파트별 데이터들을 로드해 최종 뉴스레터 발송 제목(subject)을 생성하는 스크립트.
"""
import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from llm_client import genai

SCRIPT_DIR = Path(__file__).parent
TMP_DIR = SCRIPT_DIR / ".." / ".." / ".tmp"
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_PATH = TMP_DIR / "subject_output.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_subject")

def main():
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY is missing.")
        sys.exit(1)

    # 1. Load Data
    drk_title = ""
    drk_file = TMP_DIR / "insight_output.json"
    if drk_file.exists():
        with open(drk_file, "r", encoding="utf-8") as f:
            try:
                drk_data = json.load(f).get("content", {})
                drk_title = drk_data.get("title", "")
            except: pass

    extras = []
    
    # Epic & Steam Free Games or Deals
    epic_file = TMP_DIR / "epic_output.json"
    if epic_file.exists():
        with open(epic_file, "r", encoding="utf-8") as f:
            try:
                epic_data = json.load(f)
                epic_current = epic_data.get("epic_current", [])
                steam_deal = epic_data.get("steam_deal")
                epic_discounted = epic_data.get("epic_discounted", [])
                
                if epic_current:
                    extras.append(f"[무료 게임] 에픽게임즈 무료 배포 - {epic_current[0]['title']}")
                elif steam_deal and steam_deal.get("type") == "free":
                    extras.append(f"[무료 게임] 스팀 무료 배포 - {steam_deal['name']}")
                elif epic_discounted:
                    extras.append(f"[할인 혜택] 에픽게임즈 할인 - {epic_discounted[0]['title']}")
                elif steam_deal:
                    extras.append(f"[할인 혜택] 스팀 할인 - {steam_deal['name']}")
            except: pass

    # Meme
    meme_file = TMP_DIR / "meme_output.json"
    if meme_file.exists():
        with open(meme_file, "r", encoding="utf-8") as f:
            try:
                meme_data = json.load(f).get("content", {})
                if meme_data.get("title"):
                    extras.append("[오늘의 밈] 포함")
            except: pass

    # Trailer
    trailer_file = TMP_DIR / "trailer_output.json"
    if trailer_file.exists():
        with open(trailer_file, "r", encoding="utf-8") as f:
            try:
                trailer_data = json.load(f).get("content", {})
                if trailer_data.get("title"):
                    extras.append(f"[추천 트레일러] {trailer_data.get('title')}")
            except: pass

    # Soundtrack
    ost_file = TMP_DIR / "soundtrack_output.json"
    if ost_file.exists():
        with open(ost_file, "r", encoding="utf-8") as f:
            try:
                ost_data = json.load(f).get("content", {})
                if ost_data.get("title"):
                    extras.append(f"[추천 OST] {ost_data.get('title')}")
            except: pass

    # User Feedback Analysis (GTcrawling / GTanalysis)
    fb_file = TMP_DIR / "feedback_output.json"
    if fb_file.exists():
        with open(fb_file, "r", encoding="utf-8") as f:
            try:
                fb_items = json.load(f).get("items", [])
                if fb_items:
                    games_str = ", ".join([it.get("game", "") for it in fb_items if it.get("game")])
                    if games_str:
                        extras.append(f"[유저 민심·리뷰 분석] {games_str}")
            except: pass

    if not drk_title:
        log.warning("인사이트 제목이 없습니다. 기본 제목을 생성합니다.")
        drk_title = "오늘의 게임 뉴스 헤드라인"

    # 2. Prompt Gemini
    prompt = f"""당신은 뉴스레터 편집장입니다. 이번 주 게이머들에게 발송될 뉴스레터의 이메일 제목(Subject Line)을 작성해야 합니다.

[이번 호 핵심 내용]
- 메인 테마: {drk_title}
- 부가 하이라이트: {', '.join(extras) if extras else '없음'}

작성 가이드:
1. 독자의 호기심을 즉각적으로 유발하고 클릭을 유도하는 매력적인 1줄짜리 제목을 작성하세요.
2. 메인 테마의 핵심 키워드와, 부가 콘텐츠(무료 게임, 트레일러, 유저 리뷰 분석 등) 중 가장 매력적인 요소 1개를 결합하세요.
3. 예시: "붉은사막 해외 반응 폭발!🔥 (feat. 주말 무료 배포)" 또는 "거대 자본 시대의 종말 📉, 그리고 이번 주 스팀 특가 안내 🎁"
4. 제목 끝이나 중간에 어울리는 이모지 1~2개를 적절히 섞어서 센스 있게 구성하세요.
5. 이 뉴스레터는 글로벌로 발송되므로, 결과물은 반드시 3개 국어(한국어, 영어, 일본어) 버전으로 생성해야 합니다. 의미가 동일하게 전달되어야 합니다.
6. 영어 및 일본어는 현지 게이머들이 자연스럽게 느끼는 클릭베이트(Click-bait) 혹은 흥미 유발 어투로 의역하세요. 너무 고리타분한 직역은 피하세요.
7. 중요: 부가 하이라이트 정보가 '[할인 혜택]' 등 '할인'인 경우, 제목에 '무료 배포' 또는 '무료'라는 단어를 사용해서는 절대 안 되며, 반드시 '할인', '특가', '세일', '할인 혜택' 등의 단어만 사용해야 합니다. 실제 무료 배포 게임이 있는 경우에만 '무료 배포' 또는 '무료'로 언급하세요.

반드시 아래 JSON 포맷으로만 출력하세요. (다른 텍스트 금지)
```json
{{
  "ko": "한국어 뉴스레터 제목",
  "en": "영어 뉴스레터 제목",
  "ja": "일본어 뉴스레터 제목"
}}
```"""

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        text = response.text.strip()
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            log.info(f"✨ Subject 생성 완료: {result['ko']}")
        else:
            log.warning("JSON 파싱 실패. Fallback 적용.")
            raise ValueError()
    except Exception as e:
        log.error(f"Generate subject failed: {e}")
        fallback = {
            "ko": f"{drk_title}",
            "en": "Global Gaming Insights & More",
            "ja": "今週のゲームインサイト"
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(fallback, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
