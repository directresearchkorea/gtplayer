"""
generate_scene.py — 섹션 5 (오늘의 게임씬) 생성
Gemini로 장면 묘사/코멘트 생성 → Imagen API로 실제 이미지 생성 → 저장
크롤링 데이터에 따른 Case 1(업데이트 예측) / Case 2(Dr.K 통찰 시각화, 아이러니 확률) 분기 포함.
"""
import os
import sys
import json
import re
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
COLLECTED_NEWS_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "collected_news.json"
INSIGHT_OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "insight_output.json"
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "scene_output.json"
IMAGES_DIR = SCRIPT_DIR / ".." / ".." / "web" / "assets" / "scenes"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_scene")

def run(force_test=False):
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not found")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    if OUTPUT_PATH.exists() and not force_test:
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            gen_time = existing.get("generation_time", "")
            existing_img = existing.get("content", {}).get("imgUrl", "")
            if gen_time[:10] == today_str and existing_img:
                img_path = SCRIPT_DIR / ".." / ".." / "web" / existing_img
                if img_path.exists():
                    log.info(f"♻️ Reusing today's scene image: {existing_img}")
                    return
        except Exception:
            pass

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 1. 로드하기 (뉴스 데이터 및 통찰)
    candidates = []
    if COLLECTED_NEWS_PATH.exists():
        with open(COLLECTED_NEWS_PATH, "r", encoding="utf-8") as f:
            news_data = json.load(f)
            candidates = news_data.get("candidates", [])
            
    insight_points = "(인사이트 데이터를 불러오지 못했습니다)"
    if INSIGHT_OUTPUT_PATH.exists():
        with open(INSIGHT_OUTPUT_PATH, "r", encoding="utf-8") as f:
            insight_data = json.load(f)
            # data has shape {"section":..., "content": {"points": ...}}
            insight = insight_data.get("content", {})
            insight_points = insight.get("points", "")

    # 2. 분기 로직 판별
    update_news_list = []
    for c in candidates:
        title = c.get("title", "")
        summary = c.get("summary", "")
        if any(kw in title for kw in ["업데이트", "패치", "신규"]) or any(kw in summary for kw in ["업데이트", "패치", "신규"]):
            update_news_list.append(c)

    is_case1 = len(update_news_list) > 0
    irony_flag = random.random() < 0.25

    force_mode = os.getenv("FORCE_MODE", "")
    if force_mode == "case1":
        is_case1 = True
        irony_flag = False
        if not update_news_list and candidates:
            update_news_list = [candidates[0]]
    elif force_mode == "case2_normal":
        is_case1 = False
        irony_flag = False
    elif force_mode == "case2_irony":
        is_case1 = False
        irony_flag = True

    # 3. 프롬프트 구성
    if is_case1:
        log.info("▶ Case 1: 업데이트/패치 소식 기반 미래 예측 모드")
        selected_news = random.choice(update_news_list)
        prompt = f"""당신은 탁월한 게임 분석가이자 프롬프트 엔지니어입니다.
최근 게임 소식 중 다음 업데이트/패치 소식을 바탕으로, 이 게임이 업데이트 된 이후의 미래 모습을 예측해주세요.

뉴스 제목: {selected_news.get('title')}
뉴스 요약: {selected_news.get('summary')}

지시사항:
1. 게임명: 위 뉴스에서 핵심이 되는 게임 이름
2. 장면 제목: 한국어, 기대감을 주는 업데이트 예측 제목
3. 코멘트: 작성자는 'Dr. K' 입니다. 독자들에게 앞선 인사이트 섹션과 별개로 보너스로 보여주는 이미지라는 뉘앙스로, 위 업데이트/패치 소식을 바탕으로 AI에게 어느 게임의 미래 모습을 상상해 보라고 지시했는지 1~2문장의 한국어로 설명하세요. **(주의: "Dr.K입니다" 등 자기소개나 인사말은 절대로 쓰지 마시고 쿨하게 본문만 작성하세요.)**
4. 이미지 프롬프트 (ai_prompt): 실제 이미지 생성을 위한 영어 프롬프트입니다. **절대 시네마틱이나 일러스트 느낌이 나게 하지 말고, 무조건 원작 게임의 인게임 스크린샷과 100% 동일한 화풍과 그래픽 엔진 스타일을 엄격히 강제하세요.** 프롬프트에 "Actual in-game screenshot, exact original game engine rendering, completely identical to original art style, NO cinematic styling, NO illustration" 문구를 반드시 포함하세요. 업데이트 요소가 반영된 장면을 구체적으로 묘사하세요.
5. 아래 JSON 포맷으로만 출력:
```json
{{
  "game": "게임 이름",
  "title": "장면 제목",
  "comment": "코멘트 내용",
  "ai_prompt": "이미지 생성을 위한 영어 프롬프트"
}}
```"""
    else:
        log.info(f"▶ Case 2: Dr.K 인사이트 시각화 모드 (Irony Flag: {irony_flag})")
        prompt = f"""당신은 심미안이 뛰어난 아트 디렉터이자 프롬프트 엔지니어입니다.
오늘 발행될 뉴스레터의 'Dr. K 인사이트' 섹션을 읽고, 그 주요 통찰의 분위기를 한 장의 예술적인 이미지로 시각화해주세요.

[Dr. K 인사이트 본문]
{insight_points}

지시사항:
1. 게임명: 위 인사이트에서 가장 핵심으로 다뤄지고 있는 메인 게임 1개를 선정하세요 (특정 게임이 없다면 '업계 동향').
2. 감성 평가: 내용이 긍정/희망/성장인지, 부정/비판/위기인지 문맥을 판단하세요.
{"3. [매우 중요] 현재 IRONY 플래그가 켜져 있습니다. 만약 내용이 부정/비판적임에도 불구하고, **의도적으로 따뜻하고 동화 같은 극도의 긍정적 화풍(Studio Ghibli style, soft watercolor, whimsical 등)을 적용하세요.** 코멘트에는 반드시 이 아이러니함을 꼬집는 은유적인 멘트를 넣고 '#반전 #아이러니' 해시태그를 포함하세요." if irony_flag else "3. 감성 스타일에 따른 화풍 선택: 내용이 긍정적이면 Studio Ghibli style (soft, watercolor, whimsical, warm lighting) 또는 Pixar 3D Style 등 따뜻한 느낌을, 부정/비판적이면 Hyper-realistic Cyberpunk style (sharp, neon, gritty, high-contrast, tech-noir) 또는 Epic Dark Fantasy 화풍을 강제 적용하세요."}
4. 이미지 프롬프트 (ai_prompt): 아래 문장 템플릿을 **정확히** 따르는 영문 프롬프트 생성.
   "A cinematic masterpiece reimagining [선정된 메인 게임명] based on Dr. K's insight. The visual must reflect a [선택된 화풍 스타일] mood. [인사이트를 나타낼 수 있는 핵심 시각적 상징물 영어 묘사]. Artistic composition, 8k, trending on ArtStation."
5. 코멘트: 작성자는 'Dr. K' 입니다. 방금 전 윗 단락에서 자신이 작성한 인사이트 내용과 이 이미지의 연결성을 설명하며, 이 그림을 통해 어떤 의도를 담았는지(또는 어떻게 흥미롭게 표현했는지) 1~2문장으로 매끄럽고 날카롭게 설명하세요. (예: "결국 앞서 말씀드린 현상을 시각화하면 이런 씁쓸한 풍경이 그려집니다.") **(주의: "안녕하세요", "Dr.K입니다" 등의 인사말은 절대로 넣지 마시고 본론만 작성하세요.)**
6. 아래 JSON 포맷으로만 출력:
```json
{{
  "game": "메인 게임 이름",
  "title": "장면 제목 (예술적인 이름)",
  "comment": "코멘트 내용",
  "ai_prompt": "이미지 생성을 위한 영어 프롬프트"
}}
```"""

    # 4. LLM 호출
    try:
        log.info("Step 1: Generating scene description via Gemini...")
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        text = response.text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        scene_data = json.loads(text)
        log.info(f"Scene selected: {scene_data.get('game', 'Unknown')}")
        
        # 5. Gemini Image Generation 호출
        img_prompt = scene_data.get("ai_prompt", "")
        img_url = ""
        
        def try_generate_image(prompt_text):
            image_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image"]
            for model_name in image_models:
                try:
                    log.info(f"Step 2: Generating image via {model_name}...")
                    img_resp = client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config={"response_modalities": ["IMAGE"]}
                    )
                    if img_resp.candidates and img_resp.candidates[0].content.parts:
                        for part in img_resp.candidates[0].content.parts:
                            if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                                return part.inline_data.data
                except Exception as model_err:
                    log.warning(f"Image generation with {model_name} failed: {model_err}")
            return None

        if img_prompt:
            log.info("Step 2: Generating image via Gemini Image API...")
            img_bytes = try_generate_image(img_prompt)
            
            # 1차 실패 시 저작권/정책 필터링 우회를 위한 프롬프트 순화 후 재시도
            if not img_bytes:
                log.info("Step 2-Fallback: Sanitizing prompt to avoid copyright/trademark filters and retrying...")
                try:
                    sanitize_prompt = f"""Rewrite the following image generation prompt into a generic, copyright-safe, descriptive visual prompt.
Do NOT use specific trademarked brand names, specific character names, or studio names.
Instead, describe the visual environment, genre aesthetic, color palette, camera angle, and action dynamics in detail.
Original prompt:
{img_prompt}

Return ONLY the rewritten English prompt text without markdown formatting or quotes."""
                    sanitized_res = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=sanitize_prompt
                    )
                    sanitized_prompt = sanitized_res.text.strip().strip('"').strip("'")
                    log.info(f"Sanitized Prompt: {sanitized_prompt}")
                    img_bytes = try_generate_image(sanitized_prompt)
                except Exception as san_err:
                    log.warning(f"Prompt sanitization failed: {san_err}")

            if img_bytes:
                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"scene_{timestamp}.png"
                filepath = IMAGES_DIR / filename
                
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                
                img_url = f"assets/scenes/{filename}"
                log.info(f"✅ Image successfully generated and saved: {filepath}")
            else:
                log.warning("❌ All image generation attempts failed")
        
        scene_data["imgUrl"] = img_url
        
        output = {
            "section": "gamescene",
            "content": scene_data,
            "generation_time": datetime.now().isoformat()
        }
        
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            
        log.info(f"Game scene saved to {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Failed to generate scene: {e}")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    run(force_test=True)
