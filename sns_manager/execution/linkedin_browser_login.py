"""
linkedin_browser_login.py — Playwright 기반 LinkedIn 로그인 세션 저장 유틸리티

이 스크립트를 실행하면 크롬 창이 열립니다.
링크드인에 로그인하고 홈 피드가 보일 때 터미널에서 [엔터]를 누르면
쿠키와 로그인 세션 정보가 .tmp/linkedin_state.json에 저장되어,
이후의 자동 업로드 시 재로그인 없이 진행 가능합니다.
"""

import sys
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("linkedin_browser_login")

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
STATE_PATH = TMP_DIR / "linkedin_state.json"

def run():
    TMP_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        log.info("📢 크롬 브라우저를 시작합니다...")
        try:
            browser = p.chromium.launch(
                channel="chrome", 
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception as e:
            log.warning(f"설치된 크롬을 찾지 못해 기본 Chromium으로 시작합니다: {e}")
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

        context = browser.new_context()
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        log.info("🌐 링크드인 로그인 페이지로 이동 중...")
        page.goto("https://www.linkedin.com/login")

        print("\n" + "="*70)
        print(" [로그인 가이드]")
        print(" 1. 브라우저 창에서 링크드인 계정으로 로그인을 진행해 주세요.")
        print(" 2. 로그인 후 홈 화면(피드)이 완전히 로드되면 터미널 창으로 돌아옵니다.")
        print(" 3. 터미널 창에서 [엔터]키를 누르면 로그인 세션이 저장되고 브라우저가 종료됩니다.")
        print("="*70 + "\n")

        input("🔑 로그인을 완료하고 피드가 뜨면 [엔터] 키를 누르세요...")

        # 세션 저장
        context.storage_state(path=str(STATE_PATH))
        log.info(f"✅ 로그인 세션이 성공적으로 저장되었습니다: {STATE_PATH.name}")

        browser.close()

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n종료합니다.")
