"""
youtube_community_login.py — Playwright 기반 YouTube 로그인 세션 저장 유틸리티

이 스크립트를 실행하면 크롬 창이 열립니다.
유튜브(구글) 계정에 로그인하고 홈 피드가 보일 때 터미널에서 [엔터]를 누르면
쿠키와 로그인 세션 정보가 .tmp/youtube_state.json에 저장되어,
이후의 자동 커뮤니티 업로드 시 재로그인 없이 진행 가능합니다.
"""

import sys
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("youtube_community_login")

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
USER_DATA_DIR = TMP_DIR / "youtube_user_data"

def run():
    TMP_DIR.mkdir(exist_ok=True)
    USER_DATA_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        log.info("📢 실 환경 Chrome/Edge 지속형(Persistent) 브라우저를 시작합니다...")
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
                log.info(f"✅ 브라우저 프로필 실행 성공 ({channel_name or 'Chromium'})")
                break
            except Exception as e:
                log.warning(f"⚠️ 브라우저 실행 시도 실패 ({channel_name}): {e}")

        if not context:
            log.error("❌ 브라우저를 실행할 수 없습니다.")
            return

        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        log.info("🌐 유튜브 로그인 페이지로 이동 중...")
        page.goto("https://accounts.google.com/ServiceLogin?service=youtube")

        print("\n" + "="*70)
        print(" [로그인 가이드]")
        print(" 1. 열린 브라우저 창에서 유튜브 채널 관리 권한이 있는 구글 계정으로 로그인해 주세요.")
        print(" 2. 로그인 후 유튜브 홈 화면이 완전히 로드되면 터미널 창으로 돌아옵니다.")
        print(" 3. 터미널 창에서 [엔터]키를 누르면 지속형 세션 프로필 저장이 완료되고 브라우저가 닫힙니다.")
        print("="*70 + "\n")

        input("🔑 로그인을 완료하고 유튜브 홈 화면이 뜨면 [엔터] 키를 누르세요...")

        log.info(f"✅ 지속형 브라우저 프로필 저장이 완료되었습니다: {USER_DATA_DIR}")
        context.close()

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n종료합니다.")
