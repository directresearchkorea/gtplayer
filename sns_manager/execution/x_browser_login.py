"""
x_browser_login.py - X(Twitter) 브라우저 로그인 세션 저장

API를 거치지 않는 브라우저 자동화를 위해 최초 1회 수동으로 로그인하여 
쿠키와 세션을 .tmp 폴더에 저장합니다.

사용법:
  py sns_manager/execution/x_browser_login.py
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(exist_ok=True)

STATE_PATH = TMP_DIR / "x_state.json"

def run():
    print("🚀 X(Twitter) 초기 로그인 세션을 구성합니다.")
    print("   크롬 창이 열리면 직접 로그인해 주시고,")
    print("   완전히 홈 피드가 보이면 터미널 창에서 [엔터] 키를 눌러주세요.")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="chrome", 
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception:
            # 에지가 없으면 일반 브라우저로 런칭 시도
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
        context = browser.new_context()
        page = context.new_page()
        
        # 봇 탐지 속이기
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 네트워크가 느릴 때를 위해 타임아웃을 90초로 여유 있게 설정합니다.
        page.goto("https://x.com/login", timeout=90000)
        
        input("\n✅ 로그인 완료 후 메인 피드가 표시되면 [엔터] 키를 눌러주세요...")
        
        # 상태(세션 및 쿠키) 저장
        context.storage_state(path=str(STATE_PATH))
        print(f"\n💾 성공적으로 세션 쿠키가 저장되었습니다! (경로: {STATE_PATH})")
        print("이제 매일 `x_browser_automator.py`를 사용할 수 있습니다.")
        
        browser.close()

if __name__ == "__main__":
    run()
