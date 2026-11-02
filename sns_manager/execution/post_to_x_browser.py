"""
post_to_x_browser.py — Playwright 기반 X(Twitter) 자동 포스팅 (No-API)

에디션 JSON을 읽어 Gemini로 트윗을 생성하고, 
저장된 브라우저 세션(x_state.json)을 활용해 X에 자동으로 게시합니다.
대표 카드 이미지(card_news.png)가 존재하면 트윗에 첨부합니다.

사용법:
  py sns_manager/execution/post_to_x_browser.py                          # 최신 에디션
  py sns_manager/execution/post_to_x_browser.py edition_025.json          # 특정 에디션
  py sns_manager/execution/post_to_x_browser.py edition_025.json --test   # 테스트 모드 (발행 안함)
"""

import os
import sys
import json
import logging
import argparse
import random
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
STATE_PATH = TMP_DIR / "x_state.json"
EDITIONS_DIR = BASE_DIR / "web" / "editions"
INSTAGRAM_DIR = BASE_DIR / "web" / "instagram" # 인스타 카드 디렉토리 재활용 (X 카드와 이미지 동일)

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_to_x_browser")

SITE_URL = "https://www.gtplayer.net"

def delay(min_sec=10, max_sec=20):
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

# ── 1. 에디션에서 컨텍스트 추출 ──────────────────────────────
def extract_context(edition):
    sections = edition.get("sections", {})
    ctx = {
        "num": edition.get("num", "???"),
        "date": edition.get("date", ""),
        "subject_ko": edition.get("email_subject", {}).get("ko", ""),
        "subject_en": edition.get("email_subject", {}).get("en", ""),
        "subject_ja": edition.get("email_subject", {}).get("ja", ""),
    }

    cal = sections.get("calendar", {})
    if cal.get("enabled"):
        games = [f"{r['game']} ({', '.join(r.get('platforms', []))})" for r in cal.get("releases", [])[:5]]
        ctx["releases"] = games
        ctx["events"] = [e["name"] for e in cal.get("events", [])[:3]]

    briefing = sections.get("briefing", {})
    if briefing.get("enabled"):
        ctx["headlines"] = [item["title"] for item in briefing.get("items", [])[:5]]

    drk = sections.get("drk", {})
    if drk.get("enabled"):
        ctx["drk_title"] = drk.get("title", "")
        ctx["drk_intro"] = drk.get("intro", "")[:200]

    return ctx

def build_post_url(num, lang="ko"):
    if lang == "ko":
        return f"{SITE_URL}/edition-{num}/"
    else:
        return f"{SITE_URL}/edition-{num}-{lang}/"

# ── 2. Gemini로 트윗 생성 ────────────────────────────────────
def generate_tweet(ctx, lang="ko"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 .env에 없습니다.")
        return None

    from google import genai
    client = genai.Client(api_key=api_key)
    post_url = build_post_url(ctx["num"], lang)

    prompt_map = {
        "ko": f"""아래 게임 뉴스레터 에디션 정보를 바탕으로 X(트위터) 포스트를 작성해주세요.

**규칙:**
1. 총 길이: URL과 해시태그를 제외한 본문 길이를 반드시 **한국어 90자 이내**로 매우 짧게 요약! (트위터 글자수 초과 방지)
2. 말투: X(트위터) 유저들이 좋아하는 친근하고 편안한 대화체 (예: ~네요!, ~인 거 아시나요?, ~해볼까요? 등)
3. 첫 줄: 시선을 확 끄는 흥미로운 한 문장 훅
4. 2번째 줄: 복잡한 사실 나열은 피하고, 가장 핵심적인 뉴스 1개만 골라서 한 문장으로 임팩트 있게 요약
5. 마지막 줄: URL (아래 URL을 그대로 사용)
6. 해시태그 2~3개 (오늘 다룬 구체적인 대표 게임 이름 1~2개 필수 포함 + #GTPlayer)
7. 이모지는 너무 과하지 않게 자연스러운 위치에 2~3개만 사용
8. 딱딱한 뉴스 봇 느낌은 절대 금지. 실제 게이머가 흥미로운 소식을 공유하는 듯한 느낌으로 작성.

**에디션 정보:**
- 에디션: #{ctx['num']} ({ctx['date']})
- 제목: {ctx.get('subject_ko', '')}
- 오늘 출시 게임: {', '.join(ctx.get('releases', ['없음']))}
- 뉴스 헤드라인: {'; '.join(ctx.get('headlines', ['없음']))}
- Dr. K 인사이트: {ctx.get('drk_title', '없음')}

**URL:** {post_url}

트윗 텍스트만 출력하세요. 따옴표나 설명 없이.""",

        "en": f"""Write an X (Twitter) post based on this gaming newsletter edition.

**Rules:**
1. Total length: under 250 chars including URL
2. First line: a compelling hook that stops the scroll
3. 2-3 lines: summarize today's key content (use specific game names/numbers)
4. Last line: URL (use the exact URL below)
5. 2-3 hashtags (gaming-related + #GTPlayer)
6. Use 2-3 emojis naturally

**Edition info:**
- Edition: #{ctx['num']} ({ctx['date']})
- Subject: {ctx.get('subject_en', '')}
- Today's releases: {', '.join(ctx.get('releases', ['None']))}
- Headlines: {'; '.join(ctx.get('headlines', ['None']))}
- Dr. K Insight: {ctx.get('drk_title', 'None')}

**URL:** {post_url}

Output ONLY the tweet text. No quotes or explanations.""",

        "ja": f"""以下のゲームニュースレターの情報をもとに、X（Twitter）のポストを作成してください。

**ルール:**
1. URL込みで250文字以内
2. 1行目：スクロールを止める強力なフック
3. 2〜3行：本日のハイライト要約（具体的なゲーム名・数字を入れる）
4. 最後の行：URL（以下のURLをそのまま使用）
5. ハッシュタグ2〜3個（ゲーム関連 + #GTPlayer）
6. 絵文字2〜3個を自然に使用

**エディション情報:**
- エディション: #{ctx['num']} ({ctx['date']})
- タイトル: {ctx.get('subject_ja', '')}
- 本日のリリース: {', '.join(ctx.get('releases', ['なし']))}
- ヘッドライン: {'; '.join(ctx.get('headlines', ['なし']))}
- Dr. Kインサイト: {ctx.get('drk_title', 'なし')}

**URL:** {post_url}

ツイートのテキストのみ出力してください。引用符や説明は不要です。""",
    }

    prompt = prompt_map.get(lang, prompt_map["ko"])

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        tweet = response.text.strip()
        tweet = tweet.strip('"').strip("'").strip("`")
        log.info(f"   ✅ [{lang.upper()}] 트윗 생성 완료 ({len(tweet)}자)")
        return tweet
    except Exception as e:
        log.error(f"   ❌ [{lang.upper()}] Gemini 오류: {e}")
        return None

# ── 3. Playwright 브라우저 포스팅 ─────────────────────────────
def post_tweet_via_browser(page, text, image_path=None, is_test=False):
    """Playwright를 이용해 X에 트윗을 작성하고 포스팅합니다."""
    log.info("📢 X 트윗 작성 페이지로 이동 중...")
    try:
        page.goto("https://x.com/intent/post", wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log.warning(f"⚠️ page.goto 페이지 로딩 타임아웃/에러 (계속 진행 시도): {e}")
    
    # 텍스트 입력창 로딩 대기 (최대 45초, DOM 부착 상태 기준)
    textarea_locator = page.locator('[data-testid="tweetTextarea_0"]')
    try:
        page.wait_for_selector('[data-testid="tweetTextarea_0"]', state="attached", timeout=45000)
    except Exception:
        log.info("⚠️ X 홈 피드의 인라인 작성창이 DOM에 부착되지 않았습니다. 사이드바 '게시하기' 버튼 클릭을 시도합니다.")
        try:
            post_sidebar_btn = page.locator('[data-testid="SideNav_NewTweet_Button"]').first
            post_sidebar_btn.wait_for(state="visible", timeout=20000)
            post_sidebar_btn.click(force=True)
            log.info("🖱 사이드바 '게시하기' 버튼을 클릭했습니다. 작성창 로딩 대기 중...")
            page.wait_for_selector('[data-testid="tweetTextarea_0"]', state="attached", timeout=20000)
        except Exception as btn_err:
            log.error(f"❌ 사이드바 버튼 클릭 또는 작성창 대기 실패: {btn_err}")

    # 로그인 여부 검사
    current_url = page.url
    log.info(f"   현재 페이지 URL: {current_url}")
    if "login" in current_url or "flow/login" in current_url:
        log.error("❌ X 세션이 만료되었습니다. x_browser_login.py를 먼저 실행해 주세요.")
        return False

    # 텍스트 입력창 찾기 및 채우기 (포커싱 + 키보드 주입 방식으로 강력화)
    if textarea_locator.count() == 0:
        log.error("❌ 트윗 입력창을 찾을 수 없습니다.")
        # 디버깅 스크린샷 저장
        debug_shot = BASE_DIR / ".tmp" / "debug_x_composer.png"
        try:
            page.screenshot(path=str(debug_shot))
            log.info(f"   📸 디버깅 스크린샷 저장됨: {debug_shot}")
        except Exception as e:
            log.warning(f"   스크린샷 저장 실패: {e}")
        return False

    log.info("✍️ 트윗 본문 주입 중 (포커싱 + 키보드 주입)...")
    try:
        textarea = textarea_locator.first
        textarea.focus()
        textarea.click(force=True)
        page.wait_for_timeout(1000)
        # 기존 텍스트 전체 선택 후 삭제 (안전 지우기)
        page.keyboard.press("Control+KeyA")
        page.keyboard.press("Backspace")
        # 키보드 입력을 통해 page.keyboard.type 사용 (Draft.js 안정성 극대화)
        page.keyboard.type(text)
        page.wait_for_timeout(2000)
    except Exception as fill_err:
        log.error(f"❌ 텍스트 주입 실패: {fill_err}")
        return False

    # 이미지 첨부 (옵션)
    if image_path and Path(image_path).exists():
        log.info(f"🖼 이미지 첨부 중: {Path(image_path).name}")
        file_input = page.locator('input[data-testid="fileInput"]').first
        try:
            file_input.set_input_files(image_path)
            page.wait_for_timeout(4000) # 업로드 완료 대기
        except Exception as e:
            log.warning(f"⚠️ 이미지 첨부 실패 (생략 후 계속 진행): {e}")

    # 포스팅 버튼 클릭 (대화상자 안의 버튼을 명확히 지정하여 왼쪽 사이드바 버튼 클릭 방지)
    post_btn = page.locator('div[role="dialog"] [data-testid="tweetButton"]').first
    if not post_btn.is_visible():
        post_btn = page.locator('[data-testid="tweetButton"]:visible').last

    if not post_btn.is_visible():
        log.error("❌ 포스트 버튼을 찾을 수 없습니다.")
        return False

    if is_test:
        log.info("   [TEST] X 포스팅 발행 버튼 클릭 시뮬레이션 성공")
        return True
    else:
        log.info("🖱 X 포스팅 발행 버튼 클릭 및 이벤트 디스패치!")
        try:
            post_btn.click(force=True, timeout=3000)
        except Exception:
            pass
        # React 핸들러 직접 격발을 위해 클릭 이벤트 디스패치 실행
        post_btn.dispatch_event("click")
        page.wait_for_timeout(6000) # 글 업로드 대기

        # 발행이 잘 되었는지 intent/post에서 페이지가 리다이렉트(이동)되었는지 여부로 판단
        # (홈 화면에 항상 떠 있는 다른 작성창으로 인해 is_visible 검사는 오탐이 발생함)
        if "intent/post" not in page.url:
            log.info("      X 포스팅 성공!")
            return True
        else:
            log.error("❌ X 포스팅 실패 (작성 창이 닫히지 않음)")
            # 디버깅용 스크린샷 캡처
            fail_shot = BASE_DIR / ".tmp" / f"debug_x_post_fail.png"
            try:
                page.screenshot(path=str(fail_shot))
                log.info(f"   📸 디버깅 스크린샷 저장됨: {fail_shot}")
            except Exception as e:
                log.warning(f"   스크린샷 저장 실패: {e}")
            return False

def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None

def run(edition_file=None, is_test=False):
    if edition_file:
        json_path = EDITIONS_DIR / edition_file
        if not json_path.exists():
            json_path = Path(edition_file)
    else:
        json_path = find_latest_edition()

    if not json_path or not json_path.exists():
        log.error(f"❌ 에디션 파일 없음: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        edition = json.load(f)

    num = edition.get("num", "000")
    log.info(f"📄 에디션 #{num} 로드")

    # 중복 발행 방지: 이미 성공적으로 업로드된 기록이 있는지 검사
    if not is_test:
        social_x = edition.get("social", {}).get("x", {})
        results_saved = social_x.get("results", {})
        if results_saved.get("ko", {}).get("posted"):
            log.info(f"ℹ️ 에디션 #{num}은 이미 X(트위터)에 성공적으로 포스팅되었습니다. (스킵)")
            return results_saved

    ctx = extract_context(edition)
    
    # 한국어 트윗만 생성 및 포스팅
    tweets = {}
    tweet_text = generate_tweet(ctx, "ko")
    if tweet_text:
        tweets["ko"] = tweet_text

    if not tweets:
        log.error("❌ 생성된 트윗 문구가 없어 포스팅을 중단합니다.")
        return

    if not STATE_PATH.exists():
        log.error("❌ X 세션 파일이 없습니다. x_browser_login.py를 먼저 실행하세요.")
        return

    # 카드 이미지 경로 파악 (우선순위: card_cover_dynamic.png -> card_cover.png -> card_news.png)
    card_path = None
    for name in ["card_cover_dynamic.png", "card_cover.png", "card_news.png"]:
        p = INSTAGRAM_DIR / f"edition_{num}" / name
        if p.exists():
            card_path = p
            break
    image_path = str(card_path) if card_path else None

    with sync_playwright() as p:
        # 봇 탐지 회피를 위해 헤디드(창 있음) 구동을 우선적으로 시도하되,
        # 작업 스케줄러 백그라운드 구동 등으로 GUI 창을 열 수 없는 경우 헤드리스(창 없음) 모드로 자동 폴백(Fallback)합니다.
        browser = None
        for launch_headless in [False, True]:
            try:
                browser = p.chromium.launch(
                    channel="chrome",
                    headless=launch_headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-renderer-backgrounding",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows"
                    ]
                )
                print(f"✅ 브라우저 실행 성공 (Headless={launch_headless})")
                break
            except Exception as e:
                print(f"⚠️ 브라우저 실행 시도 실패 (Headless={launch_headless}, Channel=chrome): {e}")
                
        if browser is None:
            # chrome 채널이 실패한 경우 일반 chromium으로 재시도
            for launch_headless in [False, True]:
                try:
                    browser = p.chromium.launch(
                        headless=launch_headless,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-renderer-backgrounding",
                            "--disable-background-timer-throttling",
                            "--disable-backgrounding-occluded-windows"
                        ]
                    )
                    print(f"✅ 일반 Chromium 브라우저 실행 성공 (Headless={launch_headless})")
                    break
                except Exception as e:
                    print(f"⚠️ 일반 Chromium 실행 시도 실패 (Headless={launch_headless}): {e}")
                    
        if browser is None:
            print("❌ 오류: 브라우저를 전혀 실행할 수 없습니다.")
            return

        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 언어별 트윗 순차 발행
        results = {}
        for lang, text in tweets.items():
            log.info(f"\n🔄 X [{lang.upper()}] 트윗 포스팅 시작...")
            success = post_tweet_via_browser(page, text, image_path, is_test)
            results[lang] = {
                "posted": success,
                "text": text,
                "error": None if success else "Posting failed or blocked"
            }
            # 언어 간에 과속 방지를 위해 딜레이 부여
            if len(tweets) > 1 and lang != list(tweets.keys())[-1]:
                log.info("⏰ 다음 언어 포스팅 전 잠시 대기합니다...")
                delay(10, 20)

        browser.close()

    # 결과 저장
    if "social" not in edition:
        edition["social"] = {}
    if "x" not in edition["social"]:
        edition["social"]["x"] = {}
    
    edition["social"]["x"]["results"] = results
    edition["social"]["x"]["updated_at"] = datetime.now().isoformat()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    log.info(f"💾 X 발행 결과 에디션 파일에 저장 완료: {json_path.name}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X Playwright Automator")
    parser.add_argument("edition_file", nargs="?", default=None, help="에디션 JSON 파일명")
    parser.add_argument("--test", action="store_true", help="실제 클릭 발행을 생략하는 테스트 모드")
    args = parser.parse_args()

    try:
        run(edition_file=args.edition_file, is_test=args.test)
    except KeyboardInterrupt:
        print("\n종료합니다.")
