import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import re
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
NEWSLETTER_EXEC_DIR = BASE_DIR / 'newsletter_manager' / 'execution'
SNS_EXEC_DIR = BASE_DIR / 'sns_manager' / 'execution'
EDITIONS_DIR = BASE_DIR / 'web' / 'editions'

# Dynamic Scheduling Pipeline (GitHub Pages + SendGrid)

def translate_edition(data):
    """Gemini를 이용해 에디션 내 텍스트 영/일 번역 수행"""
    load_dotenv(dotenv_path=str(BASE_DIR / '.env'))
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        log.error("GEMINI_API_KEY가 .env에 없습니다")
        return data

    from google import genai
    client = genai.Client(api_key=api_key)

    sections = data.get('sections', {})
    texts = {}

    # Extract all texts
    cal = sections.get('calendar', {})
    for i, r in enumerate(cal.get('releases', [])):
        texts[f'calendar.releases.{i}.game'] = r.get('game', '')
        texts[f'calendar.releases.{i}.note'] = r.get('note', '')
        texts[f'calendar.releases.{i}.dev'] = r.get('dev', '')
    for i, ev in enumerate(cal.get('events', [])):
        texts[f'calendar.events.{i}.name'] = ev.get('name', '')
        texts[f'calendar.events.{i}.note'] = ev.get('note', '')
        texts[f'calendar.events.{i}.venue'] = ev.get('venue', '')

    for i, item in enumerate(sections.get('briefing', {}).get('items', [])):
        texts[f'briefing.items.{i}.title'] = item.get('title', '')
        texts[f'briefing.items.{i}.source'] = item.get('source', '')
        texts[f'briefing.items.{i}.time'] = item.get('time', '')

    fb = sections.get('feedback', {})
    if 'game' in fb: texts['feedback.game'] = fb.get('game', '')
    if 'period' in fb: texts['feedback.period'] = fb.get('period', '')
    if 'sources' in fb: texts['feedback.sources'] = fb.get('sources', '')
    for i, kw in enumerate(fb.get('keywords', [])): texts[f'feedback.keywords.{i}.text'] = kw.get('text', '')
    for i, c in enumerate(fb.get('comments', [])): texts[f'feedback.comments.{i}.text'] = c.get('text', '')
    for j, item in enumerate(fb.get('items', [])):
        texts[f'feedback.items.{j}.game'] = item.get('game', '')
        texts[f'feedback.items.{j}.period'] = item.get('period', '')
        texts[f'feedback.items.{j}.sources'] = item.get('sources', '')
        for i, kw in enumerate(item.get('keywords', [])): texts[f'feedback.items.{j}.keywords.{i}.text'] = kw.get('text', '')
        for i, c in enumerate(item.get('comments', [])): texts[f'feedback.items.{j}.comments.{i}.text'] = c.get('text', '')

    drk = sections.get('drk', {})
    texts['drk.title'] = drk.get('title', '')
    texts['drk.intro'] = drk.get('intro', '')
    texts['drk.points'] = drk.get('points', '')

    meme = sections.get('meme', {})
    if 'what_happened' in meme:
        texts['meme.what_happened'] = meme.get('what_happened', '')
    if 'one_liner' in meme:
        texts['meme.one_liner'] = meme.get('one_liner', '')
    if 'items' in meme:
        for i, item in enumerate(meme.get('items', [])):
            texts[f'meme.items.{i}.comment'] = item.get('comment', '')

    st = sections.get('soundtrack', {})
    if 'game' in st: texts['soundtrack.game'] = st.get('game', '')
    texts['soundtrack.title'] = st.get('title', '')
    texts['soundtrack.comment'] = st.get('comment', '')

    tr = sections.get('trailer', {})
    if 'game' in tr: texts['trailer.game'] = tr.get('game', '')
    texts['trailer.title'] = tr.get('title', '')
    texts['trailer.comment'] = tr.get('comment', '')

    ep = sections.get('epic', {})
    if 'game' in ep: texts['epic.game'] = ep.get('game', '')
    texts['epic.title'] = ep.get('title', '')
    texts['epic.comment'] = ep.get('comment', '')

    nl = sections.get('newsletter_feedback', {})
    texts['newsletter_feedback.question'] = nl.get('question', '')
    texts['newsletter_feedback.upLabel'] = nl.get('upLabel', '')
    texts['newsletter_feedback.downLabel'] = nl.get('downLabel', '')

    chart = sections.get('chart', {})
    if 'game' in chart: texts['chart.game'] = chart.get('game', '')
    if 'title' in chart: texts['chart.title'] = chart.get('title', '')
    if 'comment' in chart: texts['chart.comment'] = chart.get('comment', '')

    texts = {k: str(v) for k, v in texts.items() if v and str(v).strip()}

    existing_tr = data.get('translations', {})
    translations = {'en': existing_tr.get('en', {}), 'ja': existing_tr.get('ja', {})}
    
    for lang, lang_name in [('en', 'English'), ('ja', 'Japanese')]:
        if translations[lang]:
            log.info(f"🌐 {lang_name} 번역이 이미 존재하여 건너뜁니다.")
            continue
            
        if not texts:
            continue
            
        extra_instruction = ""
        if lang == 'en':
            extra_instruction = "IMPORTANT: If there are any dates/times (e.g., Epic Games/Steam distribution end times) which are implicitly in KST (UTC+9), convert them to UTC (subtract 9 hours) and explicitly write 'UTC' next to the time."
            
        json_payload = json.dumps(texts, ensure_ascii=False, indent=2)
        prompt = f"""아래 JSON의 한국어 값들을 {lang_name}로 번역해주세요.
키는 그대로 유지하고, 값만 {lang_name}로 번역하세요.
게임 이름, 고유명사는 공식 {lang_name} 표기를 사용하세요.
{extra_instruction}
JSON만 출력하세요.

```json
{json_payload}
```"""
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt,
                )
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    flat = json.loads(json_match.group(0))
                    for key, val in flat.items():
                        parts = key.split('.', 1)
                        sec = parts[0]
                        field = parts[1] if len(parts) > 1 else ''
                        if sec not in translations[lang]:
                            translations[lang][sec] = {}
                        translations[lang][sec][field] = val
                    log.info(f'🌐 {lang_name} 번역 완료')
                    break
            except Exception as e:
                log.error(f'❌ {lang_name} 번역 오류 (시도 {attempt+1}/{max_retries}): {e}')
                if attempt < max_retries - 1:
                    time.sleep(3)
            
    data['translations'] = translations
    data['languages'] = ['ko', 'en', 'ja']
    return data

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?", default=None, help="타겟 날짜 (YYYY-MM-DD)")
    parser.add_argument("--now", action="store_true", help="즉각 실행 및 발행")
    args, unknown = parser.parse_known_args()

    if args.date and not args.date.startswith("--"):
        today_str = args.date
    else:
        from datetime import datetime as dt_class
        today_str = dt_class.now().strftime('%Y-%m-%d')
        if dt_class.now().weekday() >= 5:
            log.info("😴 주말(토/일)이므로 뉴스레터 파이프라인을 실행하지 않고 종료합니다.")
            return
        
    log.info("="*60)
    log.info(f" GTPlayer 모닝 파이프라인 시작 (타겟 날짜: {today_str})")
    log.info("="*60)

    nums = []
    for f in EDITIONS_DIR.glob("edition_*.json"):
        try:
            nums.append(int(f.stem.split('_')[1]))
        except:
            pass
    next_num = max(nums) + 1 if nums else 1
    num = f"{next_num:03d}"

    # 1. 뼈대 / 스크립트 기반 데이터 수집 및 생성
    log.info(f"[1/4] 파이프라인 수집 시작 (Edition: {num})")
    subprocess.run([sys.executable, str(NEWSLETTER_EXEC_DIR / 'generate_edition.py')], cwd=BASE_DIR, check=True)

    json_path = EDITIONS_DIR / f'edition_{num}.json'
    if not json_path.exists():
        log.error(f"생성 실패: {json_path} 를 찾을 수 없습니다.")
        return

    # 동적 시간 할당 로직: 생성 시점에 따라 추천 발행 시간을 지정
    now_dt = datetime.now()
    now_hour = now_dt.hour
    
    if args.now:
        publish_time = now_dt.strftime("%H:%M")
        social_time = publish_time
    elif now_hour < 10:
        publish_time = "07:00"
        social_time = "07:05"
    elif now_hour < 13:
        publish_time = "13:00"
        social_time = "13:05"
    elif now_hour < 15:
        publish_time = "14:30"
        social_time = "14:35"
    else:
        publish_time = "17:00"
        social_time = "17:05"

    log.info(f"[2/4] 스케줄러 시간 주입 (목표: {publish_time})")
    with open(json_path, 'r', encoding='utf-8') as f:
        edition = json.load(f)
    
    if 'schedule' not in edition:
        edition['schedule'] = {}
    edition['schedule']['date'] = today_str
    edition['schedule']['time'] = publish_time
    edition['schedule']['target'] = "all"
    edition['schedule']['languages'] = ["ko", "en", "ja"]
    edition['status'] = "published" if args.now else "scheduled"

    # 3. 자동 번역 (Gemini)
    log.info(f"[3/4] Gemini 영/일 자동 초벌 번역 시작")
    edition = translate_edition(edition)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    # 3.5 인스타그램 카드 사전 생성
    log.info(f"[3.5/4] 소셜 미디어 트위터/인스타용 카드 이미지 생성")
    subprocess.run([sys.executable, str(NEWSLETTER_EXEC_DIR / 'generate_card_image.py'), f'edition_{num}.json', '--type', 'all'], cwd=BASE_DIR)

    # 링크드인용 영어 카드 뉴스 생성
    log.info(f"🌐 링크드인용 영어 카드 뉴스 생성")
    subprocess.run([sys.executable, str(NEWSLETTER_EXEC_DIR / 'generate_card_image.py'), f'edition_{num}.json', '--type', 'all', '--lang', 'en'], cwd=BASE_DIR)

    # 무료 게임 전용 카드 (B&W) 생성
    if edition.get('sections', {}).get('epic', {}).get('enabled', False):
        log.info(f"🎁 무료 게임 섹션 감지 - B&W 무료 게임 단독 포스팅용 카드 생성")
        subprocess.run([sys.executable, str(NEWSLETTER_EXEC_DIR / 'generate_card_image.py'), f'edition_{num}.json', '--type', 'freegame'], cwd=BASE_DIR)

    # 4. 즉시 발행(--now) 또는 예약 발행(scheduled_publish.py 대기)
    if args.now:
        log.info("👉 즉시 발행(--now) 감지: 정적 사이트 빌드, GitHub 푸시, 이메일 발송, 소셜 미디어 포스팅을 즉시 시작합니다.")
        subprocess.run([sys.executable, str(NEWSLETTER_EXEC_DIR / 'scheduled_publish.py'), str(json_path)], cwd=BASE_DIR)
    else:
        log.info(f"📅 예약 발행 대기: 예약 시각({publish_time})에 백그라운드 스케줄러(scheduled_publish.py)가 GitHub Pages 발행, 이메일 발송, 소셜 미디어 포스팅을 함께 처리합니다.")

    log.info("🎉 파이프라인 작동 완료!")

if __name__ == '__main__':
    main()
