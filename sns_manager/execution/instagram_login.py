"""
instagram_login.py - instagrapi를 이용한 인스타그램 로그인 및 세션 저장 유틸리티

최초 1회만 터미널에서 실행하여 인스타그램 ID와 비밀번호를 입력합니다.
로그인 성공 시, 현재 폴더의 .tmp/instagram_session.json에 세션 정보가 저장되며,
이후 파이프라인에서는 비밀번호 없이 이 세션 파일을 사용하여 백그라운드 구동됩니다.
"""

import os
import sys
from pathlib import Path
from instagrapi import Client

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
SESSION_FILE = TMP_DIR / "instagram_session.json"

def get_credentials():
    print("="*50)
    print("인스타그램 자동 포스팅용 세션 생성")
    print("="*50)
    print("이 도구는 페이스북 비즈니스 페이지 연동 없이")
    print("개인/프로페셔널 계정 그대로 자동 포스팅하기 위한 설정입니다.")
    print("⚠️ 2단계 인증이 설정되어 있다면 바로 다음 단계에서 코드를 입력해야 합니다.")
    print()
    
    import getpass
    username = input("인스타그램 아이디(ID): ").strip()
    password = getpass.getpass("인스타그램 비밀번호(PW): ").strip()
    
    return username, password

def main():
    TMP_DIR.mkdir(exist_ok=True)
    username, password = get_credentials()
    
    if not username or not password:
        print("❌ ID 또는 비밀번호가 입력되지 않았습니다.")
        return

    print("\n⏳ 인스타그램에 로그인 중입니다. 잠시만 기다려주세요...")
    
    cl = Client()
    # 잦은 로그인 시도를 줄이기 위해 잠시 대기
    cl.delay_range = [1, 3]

    try:
        # 로그인 시도
        success = cl.login(username, password)
        if success:
            print(f"✅ 로그인 성공! (사용자: {username})")
            
            # 세션 덤프 (json으로 쿠키 저장)
            cl.dump_settings(SESSION_FILE)
            print(f"🔒 세션 정보가 저장되었습니다: {SESSION_FILE.name}")
            print("🚀 이제 post_to_instagram.py 에서 비밀번호 없이 이 세션을 사용하여 자동 포스팅됩니다.")
        else:
            print("❌ 로그인은 되었으나 상태가 올바르지 않습니다.")
            
    except Exception as e:
        print(f"\n❌ 로그인 실패!")
        print(f"원인: {e}")
        print("\n[가능한 해결 방법]")
        print("1. 아이디와 비밀번호를 다시 확인해주세요.")
        print("2. 인스타그램 앱을 열어 '본인이 로그인한 것이 맞습니까?' 알림이 떴는지 확인 후 승인해주세요.")
        print("3. 너무 많은 로그인 시도로 인해 일시 차단되었을 수 있습니다. 잠시 후 시도해주세요.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료합니다.")
