"""
post_to_linkedin_browser.py — Playwright 기반 LinkedIn 영어 자동 포스팅 (No-API)

에디션 JSON을 읽어 Gemini로 링크드인 전용 영어 포스트 본문을 생성하고, 
저장된 브라우저 세션(linkedin_state.json)을 활용해 링크드인에 자동으로 게시합니다.
영문 번역 카드 이미지들(card_news_en.png, card_calendar_en.png, card_drk_en.png)이 존재하면 첨부합니다.

사용법:
  py sns_manager/execution/post_to_linkedin_browser.py                          # 최신 에디션
  py sns_manager/execution/post_to_linkedin_browser.py edition_096.json          # 특정 에디션
  py sns_manager/execution/post_to_linkedin_browser.py edition_096.json --test   # 테스트 모드 (발행 안함)
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
STATE_PATH = TMP_DIR / "linkedin_state.json"
EDITIONS_DIR = BASE_DIR / "web" / "editions"
INSTAGRAM_DIR = BASE_DIR / "web" / "instagram"

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_to_linkedin_browser")

SITE_URL = "https://www.gtplayer.net"

def delay(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

# ── 1. 에디션에서 영문 컨텍스트 추출 ──────────────────────────
def extract_en_context(edition):
    num = edition.get("num", "???")
    date = edition.get("date", "")
    
    # 영어 번역 데이터 가져오기
    trans_en = edition.get("translations", {}).get("en", {})
    
    subject_en = edition.get("email_subject", {}).get("en", "")
    if not subject_en:
        subject_en = edition.get("email_subject", {}).get("ko", "")

    # calendar
    cal_trans = trans_en.get("calendar", {})
    releases = []
    # calendar.releases.X.game
    r_idx = 0
    while True:
        game_key = f"releases.{r_idx}.game"
        if game_key in cal_trans:
            game_name = cal_trans.get(game_key)
            dev_name = cal_trans.get(f"releases.{r_idx}.dev", "")
            releases.append(f"{game_name} (by {dev_name})" if dev_name else game_name)
            r_idx += 1
        else:
            break

    # briefing
    brief_trans = trans_en.get("briefing", {})
    headlines = []
    h_idx = 0
    while True:
        title_key = f"items.{h_idx}.title"
        if title_key in brief_trans:
            headlines.append(brief_trans.get(title_key))
            h_idx += 1
        else:
            break

    # drk
    drk_trans = trans_en.get("drk", {})
    drk_title = drk_trans.get("title", "")
    drk_intro = drk_trans.get("intro", "")

    return {
        "num": num,
        "date": date,
        "subject": subject_en,
        "releases": releases[:5],
        "headlines": headlines[:5],
        "drk_title": drk_title,
        "drk_intro": drk_intro
    }

def build_post_url(num):
    return f"{SITE_URL}/edition-{num}-en/"

# ── 2. Gemini로 LinkedIn 포스트 생성 ────────────────────────
def generate_linkedin_post(ctx):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 .env에 없습니다.")
        return None

    from google import genai
    client = genai.Client(api_key=api_key)
    post_url = build_post_url(ctx["num"])

    prompt = f"""Write an engaging LinkedIn post in English based on this gaming newsletter edition. Keep the tone suitable and professional for the LinkedIn audience, but make it an exciting hook. Do not use overly heavy or academic words like 'analysis' or 'deep dive'.

**Rules:**
1. Structure MUST exactly follow this format (ensure there are blank lines separating the sections):
   {ctx['subject']}

   [2-line engaging hook sharing exciting gaming news]

   {post_url}
2. Do NOT add hashtags, greetings, or bullet points. Just output those exact parts.
3. Do NOT use markdown symbols like asterisks (*) or double asterisks (**).

**Edition Details:**
- Edition: #{ctx['num']} ({ctx['date']})
- Subject/Theme: {ctx['subject']}
- Game Releases: {', '.join(ctx['releases']) if ctx['releases'] else 'None'}
- News Headlines: {'; '.join(ctx['headlines']) if ctx['headlines'] else 'None'}
- Dr. K Insight: {ctx['drk_title']} ({ctx['drk_intro'][:150]}...)

Output ONLY the LinkedIn post text. No quotes or explanations."""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        post_text = response.text.strip()
        post_text = post_text.strip('"').strip("'").strip("`")
        # 볼드 기호 강제 제거
        post_text = post_text.replace("**", "").replace("*", "")
        
        # 줄바꿈 구분 및 빈 라인 삽입 포스트 프로세싱
        lines = [line.strip() for line in post_text.split("\n") if line.strip()]
        if len(lines) >= 3:
            title = lines[0]
            url = lines[-1]
            if not url.startswith("http"):
                # URL이 마지막 라인이 아닌 경우 백업 처리
                url = post_url
                hook = "\n".join(lines[1:])
            else:
                hook = "\n".join(lines[1:-1])
            post_text = f"{title}\n\n{hook}\n\n{url}"
        elif len(lines) == 2:
            post_text = f"{lines[0]}\n\n{lines[1]}"
            
        log.info(f"   ✅ 링크드인 영문 포스트 생성 및 포맷팅 완료 ({len(post_text)}자)")
        return post_text
    except Exception as e:
        log.error(f"   ❌ Gemini 오류: {e}")
        return None

# ── 3. Playwright 브라우저 포스팅 ─────────────────────────────
def post_to_linkedin_via_browser(page, text, image_paths, is_test=False):
    log.info("📢 링크드인 피드 페이지로 이동 중...")
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    # 로그인 여부 검사: 피드(feed) URL에 머물러 있는지 검사
    if "feed" not in page.url:
        log.error("❌ LinkedIn 세션이 만료되었습니다. linkedin_browser_login.py를 먼저 실행해 주세요.")
        # 디버그용 스크린샷 저장
        debug_shot = BASE_DIR / ".tmp" / "debug_linkedin_login_redirect.png"
        try:
            page.screenshot(path=str(debug_shot))
            log.info(f"   📸 로그인 필요 스크린샷 저장됨: {debug_shot}")
        except Exception:
            pass
        return False

    # 1. 'Start a post' (글쓰기 시작) 버튼 대기 및 찾기
    log.info("🖱 'Start a post' 버튼 찾는 중...")
    trigger_selector = '//button[contains(@class, "share-box-feed-entry__trigger")] | //*[text()="Start a post"] | //*[text()="글 올리기"] | //*[text()="글쓰기 시작"]'
    
    try:
        # 최대 20초간 글쓰기 버튼이 화면에 나타나기를 대기
        page.wait_for_selector(trigger_selector, timeout=20000)
    except Exception as e:
        log.warning(f"⚠️ 버튼 대기 중 타임아웃 발생 (페이지 로딩 지연): {e}")

    trigger = page.locator(trigger_selector).first
    if not trigger.is_visible():
        log.error("❌ 'Start a post' 버튼을 찾을 수 없습니다. 피드가 로딩 중이거나 레이아웃이 다릅니다.")
        # 디버그용 스크린샷 저장
        debug_shot = BASE_DIR / ".tmp" / "debug_linkedin_no_trigger.png"
        try:
            page.screenshot(path=str(debug_shot))
            log.info(f"   📸 에러 분석용 스크린샷 저장됨: {debug_shot}")
        except Exception:
            pass
        return False

    log.info("🖱 'Start a post' 버튼 클릭!")
    trigger.click()
    page.wait_for_timeout(1500)

    # 1.5 만약 클릭이 안 되어 모달이 안 열렸을 경우를 위한 백업 (dispatch_event 강제 격발)
    if not page.locator('.ql-editor').first.is_visible():
        log.info("   ⚠️ 일반 클릭 무반응 감지 - dispatch_event('click') 강제 격발 시도...")
        trigger.dispatch_event("click")
        page.wait_for_timeout(3000)

    # 2. 이미지 카드 뉴스 첨부 (선택) - 본문 입력 전에 이미지를 먼저 등록해야 버튼이 가려지지 않습니다.
    valid_images = [img for img in image_paths if Path(img).exists()]
    if valid_images:
        log.info(f"🖼 이미지 첨부 중 ({len(valid_images)}장)...")
        try:
            # 1. 포토 버튼 (미디어 추가) 찾기
            photo_btn = page.locator('button[aria-label*="media" i], button[aria-label*="미디어" i], button[aria-label*="사진" i], button.share-promoted-detour-button').first
            
            # 2. 파일 선택 인터셉터 설정 후 버튼 클릭
            with page.expect_file_chooser() as fc_info:
                photo_btn.click()
            
            file_chooser = fc_info.value
            file_chooser.set_files(valid_images)
            page.wait_for_timeout(5000) # 업로드 및 렌더링 완료 대기

            # 3. 이미지 업로드 완료 확인 버튼 ('완료' / 'Next' / 'Done') 클릭
            done_btn = page.locator('button:has-text("Next"), button:has-text("Done"), button:has-text("다음"), button:has-text("완료"), button:has-text("저장"), button.share-box-footer__primary-btn').filter(visible=True).first
            if done_btn.is_visible():
                log.info("🖱 이미지 첨부 완료 버튼 클릭 ('Next' / 'Done' / '완료')")
                done_btn.click()
                page.wait_for_timeout(3000)
        except Exception as e:
            log.warning(f"⚠️ 이미지 첨부 실패: {e}")

    # 3. 글 본문 주입
    log.info("✍️ 포스트 본문 주입 중...")
    editor_selector = '.ql-editor, div[role="textbox"][data-artdeco-is-focused="true"], div[role="textbox"][aria-label*="생각 나누기"], div[role="textbox"]'
    try:
        page.wait_for_selector(editor_selector, state="visible", timeout=10000)
    except Exception:
        pass

    textarea = page.locator(editor_selector).filter(visible=True).first
    if not textarea.is_visible():
        log.error("❌ 글쓰기 에디터 창을 찾을 수 없습니다.")
        # 디버그용 스크린샷 저장
        debug_shot = BASE_DIR / ".tmp" / "debug_linkedin_no_editor.png"
        try:
            page.screenshot(path=str(debug_shot))
            log.info(f"   📸 에디터 오류 분석용 스크린샷 저장됨: {debug_shot}")
        except Exception:
            pass
        return False

    textarea.click()
    textarea.fill(text)
    page.wait_for_timeout(2000)

    # 4. 발행 버튼 클릭
    # LinkedIn post button: button:has-text("Post"), button.share-actions__post-button, button:has-text("게시물")
    post_btn = page.locator('button.share-actions__post-button, button:has-text("Post"), button:has-text("업데이트"), button:has-text("게시물"), button:has-text("게시")').filter(visible=True).first
    if not post_btn.is_visible():
        post_btn = page.locator('button.share-box_actions__post-btn, button.share-box_actions__send-btn').filter(visible=True).first

    if not post_btn.is_visible():
        log.error("❌ Post(게시) 버튼을 찾을 수 없습니다.")
        return False

    # 포스트 버튼 활성화 대기 (텍스트나 이미지가 들어간 후 활성화됨)
    # LinkedIn post button is disabled by default if empty, we wait for it to be enabled.
    if is_test:
        log.info("   [TEST] LinkedIn 포스팅 발행 버튼 클릭 시뮬레이션 성공 (실제 클릭 안함)")
        # 디버그용 스크린샷 저장
        debug_shot = BASE_DIR / ".tmp" / "debug_linkedin_composer.png"
        try:
            page.screenshot(path=str(debug_shot))
            log.info(f"   📸 테스트용 스크린샷 저장됨: {debug_shot}")
        except Exception:
            pass
        return True
    else:
        log.info("🖱 LinkedIn 발행 버튼 클릭!")
        post_btn.click(force=True)
        page.wait_for_timeout(8000) # 포스트 처리 대기

        # 발행이 잘 되었는지 대화상자가 닫혔는지 주소 확인으로 검사
        # (성공 시 보통 모달창 div[role="dialog"]가 닫힘)
        dialog = page.locator('div[role="dialog"]').first
        if not dialog.is_visible():
            log.info("✅ LinkedIn 포스팅 성공!")
            return True
        else:
            log.error("❌ LinkedIn 포스팅 실패 (작성 창이 닫히지 않음)")
            # 디버깅 스크린샷 저장
            fail_shot = BASE_DIR / ".tmp" / "debug_linkedin_post_fail.png"
            try:
                page.screenshot(path=str(fail_shot))
                log.info(f"   📸 디버깅 스크린샷 저장됨: {fail_shot}")
            except Exception:
                pass
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

    # 중복 발행 방지
    if not is_test:
        social_linkedin = edition.get("social", {}).get("linkedin", {})
        results_saved = social_linkedin.get("results", {})
        if results_saved.get("posted"):
            log.info(f"ℹ️ 에디션 #{num}은 이미 링크드인에 성공적으로 포스팅되었습니다. (스킵)")
            return results_saved

    ctx = extract_en_context(edition)
    post_text = generate_linkedin_post(ctx)

    if not post_text:
        log.error("❌ 생성된 링크드인 포스트 문구가 없어 업로드를 중단합니다.")
        return

    if not STATE_PATH.exists():
        log.error("❌ LinkedIn 세션 파일이 없습니다. linkedin_browser_login.py를 먼저 실행하세요.")
        return

    card_dir = INSTAGRAM_DIR / f"edition_{num}"
    cover_path = card_dir / "card_cover_en.png"
    if not cover_path.exists():
        cover_path = card_dir / "card_cover.png"

    image_paths = [
        str(cover_path),
        str(card_dir / "card_news_en.png"),
        str(card_dir / "card_calendar_en.png"),
        str(card_dir / "card_drk_en.png")
    ]

    with sync_playwright() as p:
        # 봇 탐지 회피를 위해 헤디드(창 있음) 구동을 우선적으로 시도하되,
        # 작업 스케줄러 백그라운드 구동 등으로 GUI 창을 열 수 없는 경우 헤드리스(창 없음) 모드로 자동 폴백(Fallback)합니다.
        browser = None
        for launch_headless in [False, True]:
            try:
                browser = p.chromium.launch(
                    channel="chrome",
                    headless=launch_headless,
                    args=["--disable-blink-features=AutomationControlled"]
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
                        args=["--disable-blink-features=AutomationControlled"]
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

        success = post_to_linkedin_via_browser(page, post_text, image_paths, is_test)
        browser.close()

    # 결과 저장
    results = {
        "posted": success,
        "text": post_text,
        "error": None if success else "LinkedIn posting failed"
    }

    if "social" not in edition:
        edition["social"] = {}
    
    edition["social"]["linkedin"] = {
        "results": results,
        "updated_at": datetime.now().isoformat()
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    log.info(f"💾 LinkedIn 발행 결과 에디션 파일에 저장 완료: {json_path.name}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Playwright Automator")
    parser.add_argument("edition_file", nargs="?", default=None, help="에디션 JSON 파일명")
    parser.add_argument("--test", action="store_true", help="실제 클릭 발행을 생략하는 테스트 모드")
    args = parser.parse_args()

    try:
        run(edition_file=args.edition_file, is_test=args.test)
    except KeyboardInterrupt:
        print("\n종료합니다.")
