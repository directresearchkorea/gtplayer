import os
from pathlib import Path
from instagrapi import Client

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
SESSION_FILE = TMP_DIR / "instagram_session.json"

def main():
    if not SESSION_FILE.exists():
        print("[X] 세션 파일이 없습니다.")
        return

    cl = Client()
    cl.delay_range = [2, 5]

    try:
        cl.load_settings(SESSION_FILE)
        # cl.login_by_sessionid(os.environ.get("IG_SESSIONID", ""))
    except Exception as e:
        print(f"[X] 로그인 실패: {e}")
        return

    print("[V] 로그인 성공\n")

    print("="*40)
    print("Method A: 해시태그 기반 타겟 검색 (#게임스타그램)")
    print("="*40)
    try:
        # 인기 게시물 5개 가져오기
        medias = cl.hashtag_medias_top("게임스타그램", amount=5)
        users_a = set()
        for m in medias:
            if m.user and m.user.username:
                users_a.add(m.user.username)
        for u in users_a:
            print(f"- @{u}")
    except Exception as e:
        print(f"해시태그 검색 오류: {e}")

    print("\n" + "="*40)
    print("Method B: 시드 계정 기반 타겟 검색 (@playstation_korea 팔로워)")
    print("="*40)
    try:
        # playstation_korea 의 user_id 찾기
        user_id = cl.user_id_from_username("playstation_korea")
        # 팔로워 10명 가져오기
        followers = cl.user_followers(user_id, amount=10)
        
        count = 0
        for uid, user_info in followers.items():
            print(f"- @{user_info.username}")
            count += 1
            if count >= 5: # 5명만 출력
                break
    except Exception as e:
        print(f"시드 계정 검색 오류: {e}")

if __name__ == "__main__":
    main()
