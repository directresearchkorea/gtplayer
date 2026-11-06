"""
post_to_youtube_community.py — Playwright 기반 YouTube 커뮤니티 자동 포스팅 (No-API)

에디션 JSON을 읽어 Gemini로 유튜브 커뮤니티 전용 포스트 본문을 생성하고, 
저장된 브라우저 세션(youtube_state.json)을 활용해 유튜브 커뮤니티에 자동으로 게시합니다.
카드 이미지(card_cover.png 등)가 존재하면 첨부합니다.

사용법:
  py sns_manager/execution/post_to_youtube_community.py                         # 최신 에디션 (기본 한국어)
  py sns_manager/execution/post_to_youtube_community.py --lang en                # 영어로 작성
  py sns_manager/execution/post_to_youtube_community.py edition_096.json         # 특정 에디션
  py sns_manager/execution/post_to_youtube_community.py --test                   # 테스트 모드 (발행 안함)
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

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
STATE_PATH = TMP_DIR / "youtube_state.json"
EDITIONS_DIR = BASE_DIR / "web" / "editions"
INSTAGRAM_DIR = BASE_DIR / "web" / "instagram"

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_to_youtube_community")

SITE_URL = "https://www.gtplayer.net"

# ── 1. 에디션에서 컨텍스트 추출 ──────────────────────────
def extract_context(edition, lang="ko"):
    num = edition.get("num", "???")
    date = edition.get("date", "")
    
    # 해당 언어 번역 데이터 가져오기 (기본 ko는 메인 데이터에서 가져올 수도 있음)
    trans = edition.get("translations", {}).get(lang, {})
    
    subject = edition.get("email_subject", {}).get(lang, "")
    if not subject:
        subject = edition.get("email_subject", {}).get("ko", "")

    # calendar
    cal_trans = trans.get("calendar", {}) if trans else {}
    releases = []
    r_idx = 0
    while True:
        game_key = f"releases.{r_idx}.game"
        # 다국어 번역에 있으면 그것을 쓰고, 없으면 한국어 기본 데이터에서 매칭 시도
        if trans and game_key in cal_trans:
            game_name = cal_trans.get(game_key)
            dev_name = cal_trans.get(f"releases.{r_idx}.dev", "")
            releases.append(f"{game_name} ({dev_name})" if dev_name else game_name)
            r_idx += 1
        elif lang == "ko":
            # 한국어는 원본 구조 탐색
            # release 데이터가 edition["calendar"]["releases"] 에 있을 수 있음
            releases_list = edition.get("calendar", {}).get("releases", [])
            if r_idx < len(releases_list):
                item = releases_list[r_idx]
                game_name = item.get("game", "")
                dev_name = item.get("developer", "")
                releases.append(f"{game_name} ({dev_name})" if dev_name else game_name)
                r_idx += 1
            else:
                break
        else:
            break

    # briefing
    brief_trans = trans.get("briefing", {}) if trans else {}
    headlines = []
    h_idx = 0
    while True:
        title_key = f"items.{h_idx}.title"
        if trans and title_key in brief_trans:
            headlines.append(brief_trans.get(title_key))
            h_idx += 1
        elif lang == "ko":
            brief_items = edition.get("briefing", {}).get("items", [])
            if h_idx < len(brief_items):
                headlines.append(brief_items[h_idx].get("title", ""))
                h_idx += 1
            else:
                break
        else:
            break

    # drk
    drk_trans = trans.get("drk", {}) if trans else {}
    if trans and drk_trans:
        drk_title = drk_trans.get("title", "")
        drk_intro = drk_trans.get("intro", "")
    else:
        drk_title = edition.get("drk", {}).get("title", "")
        drk_intro = edition.get("drk", {}).get("intro", "")

    return {
        "num": num,
        "date": date,
        "subject": subject,
        "releases": releases[:5],
        "headlines": headlines[:5],
        "drk_title": drk_title,
        "drk_intro": drk_intro
    }

def build_post_url(num, lang="ko"):
    if lang == "ko":
        return f"{SITE_URL}/edition-{num}/"
    return f"{SITE_URL}/edition-{num}-{lang}/"

# ── 2. Gemini로 YouTube 커뮤니티 포스트 본문 생성 ────────────────────────
def generate_youtube_post(ctx, lang="ko"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 .env에 없습니다.")
        return None

    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2] / 'newsletter_manager' / 'execution'))
    from llm_client import genai
    client = genai.Client(api_key=api_key)
    post_url = build_post_url(ctx["num"], lang)

    if lang == "ko":
        prompt = f"""유튜브 커뮤니티 게시판에 올릴 게이머 대상의 친근하고 가독성 좋은 홍보 글을 한국어로 작성해줘.

**규칙:**
1. 구조는 반드시 다음 포맷을 지킬 것:
   [🔥오늘의 핵심 헤드라인 또는 기대작 요약 1~2줄]
   
   주요 뉴스 요약:
   - [뉴스 요약 1]
   - [뉴스 요약 2]
   - [뉴스 요약 3]
   
   🎮 전체 캘린더와 상세 기사는 아래 뉴스레터에서 확인해 보세요!
   👉 {post_url}
2. 이모지를 적절히 섞어서 게이머 친화적인 어조로 작성해줘.
3. 마크다운 볼드표시(*, **)는 절대 사용하지 말 것 (유튜브 텍스트에서 깨짐).
4. 해시태그는 넣지 말 것.

**에디션 상세 정보:**
- 에디션 번호: #{ctx['num']}
- 주제: {ctx['subject']}
- 주요 출시 정보: {', '.join(ctx['releases']) if ctx['releases'] else '없음'}
- 주요 뉴스 헤드라인: {'; '.join(ctx['headlines']) if ctx['headlines'] else '없음'}
- Dr. K 인사이트: {ctx['drk_title']} ({ctx['drk_intro'][:150]}...)

출력은 오직 유튜브 포스트 본문만 출력할 것."""
    else:
        prompt = f"""Write an engaging YouTube Community post in English targeting gamers based on this newsletter edition.

**Rules:**
1. Structure MUST follow this format:
   [🔥1-2 line catchy hook/summary]
   
   Key Highlights:
   - [Highlight 1]
   - [Highlight 2]
   - [Highlight 3]
   
   🎮 Check out the full calendar and detailed briefing here!
   👉 {post_url}
2. Use gaming emojis appropriately to make it friendly.
3. Do NOT use markdown symbols like * or ** (they mess up on YouTube).
4. Do NOT add hashtags.

**Edition Details:**
- Edition: #{ctx['num']}
- Subject: {ctx['subject']}
- Game Releases: {', '.join(ctx['releases']) if ctx['releases'] else 'None'}
- News Headlines: {'; '.join(ctx['headlines']) if ctx['headlines'] else 'None'}
- Insight Topic: {ctx['drk_title']} ({ctx['drk_intro'][:150]}...)

Output ONLY the post text. No explanations."""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        post_text = response.text.strip()
        post_text = post_text.strip('"').strip("'").strip("`")
        post_text = post_text.replace("**", "").replace("*", "").replace("https://", "").replace("http://", "")
        log.info(f"   ✅ 유튜브 커뮤니티 포스트 문구 생성 완료 ({len(post_text)}자)")
        return post_text
    except Exception as e:
        log.error(f"   ❌ Gemini 오류: {e}")
        return None

# ── 3. Playwright 브라우저 포스팅 ─────────────────────────────
def post_to_youtube_via_browser(page, text, image_paths, is_test=False):
    log.info("📢 채널 커뮤니티 페이지로 이동 중...")
    community_url = "https://www.youtube.com/channel/UCGlaH6KinYRCACkz7c-jnQg/community?show_create_dialog=1"
    page.goto(community_url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 로그인 상태 확인
    if "signin" in page.url or "accounts.google" in page.url:
        log.error("❌ YouTube 세션이 만료되었습니다. youtube_community_login.py를 먼저 실행해 주세요.")
        return False

    # 1. 커뮤니티 포스트 작성 플레이스홀더 영역 클릭 (에디터 확장)
    log.info("🔎 커뮤니티 작성 영역 클릭 및 에디터 확장 중...")
    placeholder_selector = '#placeholder-area, #simplebox-placeholder, #contenteditable-textarea, ytd-comment-simplebox-renderer'
    try:
        placeholder = page.locator(placeholder_selector).first
        if placeholder.is_visible():
            placeholder.click()
            page.wait_for_timeout(2000)
    except Exception as e:
        log.warning(f"⚠️ 작성 영역 클릭 실패: {e}")

    # 2. 에디터 텍스트 입력창 대기 및 실제 키보드 타이핑
    textbox_selector = 'div#contenteditable-root, div#textarea, div[contenteditable="true"]'
    if not page.locator(textbox_selector).first.is_visible():
        log.error("❌ 텍스트 입력 영역을 찾지 못했습니다.")
        return False

    log.info("✍️ 포스트 본문 주입 중 (키보드 이벤트 트리거)...")
    editor = page.locator(textbox_selector).first
    editor.click()
    page.wait_for_timeout(500)
    page.keyboard.type(text, delay=20)
    page.wait_for_timeout(3000)

    # 3. 이미지 카드 뉴스 첨부 (선택)
    valid_images = [img for img in image_paths if Path(img).exists()]
    if valid_images:
        log.info(f"🖼 이미지 첨부 시도 ({len(valid_images)}장)...")
        try:
            img_btns = page.locator('button[aria-label="이미지 추가"], button:has-text("이미지"), yt-button-shape:has-text("이미지") button').all()
            target_img_btn = next((b for b in img_btns if b.is_visible()), None)
            
            if target_img_btn:
                target_img_btn.click()
                page.wait_for_timeout(3000)
                
                select_btn = page.locator('button#select-button, button:has-text("컴퓨터에서 선택")').first
                if select_btn.is_visible():
                    with page.expect_file_chooser() as fc_info:
                        select_btn.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(valid_images) # 카드 뉴스 최대 4장 전체 업로드
                    page.wait_for_timeout(6000) # 이미지 로딩 및 콜라주 처리 대기
                    
                    confirm_btn = page.locator('button:has-text("확인"), button[aria-label="확인"]').first
                    if confirm_btn.is_visible():
                        log.info("👍 이미지 첨부 모달 '확인' 버튼 클릭!")
                        confirm_btn.click()
                        page.wait_for_timeout(4000) # 모달 닫힘 및 오버레이 해제 대기
            else:
                log.warning("⚠️ 이미지 첨부 버튼이 표시되지 않습니다. 건너뜁니다.")
        except Exception as e:
            log.warning(f"⚠️ 이미지 첨부 실패: {e}")

    # 4. 게시 버튼 찾기 및 클릭 (정확한 '게시' 단일 버튼 핀포인트 매칭)
    post_btns = page.locator('button').all()
    post_btn = None
    for b in post_btns:
        if b.is_visible():
            txt = b.inner_text().strip()
            aria = b.get_attribute("aria-label") or ""
            if txt == "게시" or aria == "게시":
                post_btn = b
                break
    
    # 외부 링크 안내 팝업 등의 팝업 레이어 차단 해제
    try:
        popup_btn = page.locator('ytd-popup-container button:has-text("확인"), ytd-popup-container button:has-text("동의"), ytd-popup-container button:has-text("이해했습니다"), ytd-popup-container button:has-text("닫기"), ytd-popup-container button:has-text("Got it")').first
        if popup_btn.is_visible():
            log.info("📢 유튜브 팝업 안합/경고 안내 팝업 감지 - 확인 클릭")
            popup_btn.click()
            page.wait_for_timeout(2000)
    except Exception:
        pass

    if not post_btn:
        log.error("❌ 게시(Post) 버튼을 찾지 못했습니다.")
        return False

    if is_test:
        log.info("   [TEST] 유튜브 포스팅 게시 버튼 클릭 시뮬레이션 성공")
        return True
    else:
        log.info("🖱 유튜브 커뮤니티 게시 버튼 클릭 (force=True)!")
        post_btn.click(force=True)
        page.wait_for_timeout(8000) # 게시물 등록 처리 대기
        log.info("✅ YouTube 커뮤니티 포스팅 완료!")
        return True

def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None

def run(edition_file=None, lang="ko", is_test=False):
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
    log.info(f"📄 에디션 #{num} 로드 (언어: {lang})")

    # 중복 발행 방지
    if not is_test:
        social_youtube = edition.get("social", {}).get("youtube_community", {})
        results_saved = social_youtube.get("results", {})
        if results_saved.get("posted"):
            log.info(f"ℹ️ 에디션 #{num}은 이미 유튜브 커뮤니티에 성공적으로 포스팅되었습니다. (스킵)")
            return results_saved

    ctx = extract_context(edition, lang)
    post_text = generate_youtube_post(ctx, lang)

    if not post_text:
        log.error("❌ 생성된 유튜브 포스트 문구가 없어 업로드를 중단합니다.")
        return

    if not STATE_PATH.exists():
        log.error("❌ YouTube 세션 파일이 없습니다. youtube_community_login.py를 먼저 실행하세요.")
        return

    card_dir = INSTAGRAM_DIR / f"edition_{num}"
    all_cards = [
        card_dir / "card_cover.png",
        card_dir / "card_news.png",
        card_dir / "card_calendar.png",
        card_dir / "card_drk.png"
    ]
    image_paths = [str(c) for c in all_cards if c.exists()]

    USER_DATA_DIR = TMP_DIR / "youtube_user_data"
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        log.info("📢 유튜브 커뮤니티 자동화 (지속형 프로필 구동)...")
        context = None
        for channel_name in ["chrome", "msedge", None]:
            try:
                kwargs = {
                    "user_data_dir": str(USER_DATA_DIR),
                    "headless": False,
                    "args": ["--disable-blink-features=AutomationControlled"]
                }
                if channel_name:
                    kwargs["channel"] = channel_name
                context = p.chromium.launch_persistent_context(**kwargs)
                log.info(f"✅ 지속형 브라우저 프로필 실행 성공 ({channel_name or 'Chromium'})")
                break
            except Exception as e:
                log.warning(f"⚠️ 브라우저 실행 시도 실패 ({channel_name}): {e}")

        if not context:
            log.error("❌ 오류: 브라우저를 실행할 수 없습니다.")
            return

        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        success = post_to_youtube_via_browser(page, post_text, image_paths, is_test)
        context.close()

    # 결과 저장
    results = {
        "posted": success,
        "text": post_text,
        "error": None if success else "YouTube Community posting failed"
    }

    if "social" not in edition:
        edition["social"] = {}
    
    edition["social"]["youtube_community"] = {
        "results": results,
        "updated_at": datetime.now().isoformat()
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    log.info(f"💾 YouTube 발행 결과 에디션 파일에 저장 완료: {json_path.name}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Community Playwright Automator")
    parser.add_argument("edition_file", nargs="?", default=None, help="에디션 JSON 파일명")
    parser.add_argument("--lang", default="ko", choices=["ko", "en", "ja"], help="발행 언어 선택 (ko/en/ja)")
    parser.add_argument("--test", action="store_true", help="실제 클릭 발행을 생략하는 테스트 모드")
    args = parser.parse_args()

    try:
        run(edition_file=args.edition_file, lang=args.lang, is_test=args.test)
    except KeyboardInterrupt:
        print("\n종료합니다.")
