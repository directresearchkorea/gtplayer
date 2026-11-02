import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from instagrapi import Client

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
SESSION_FILE = TMP_DIR / "instagram_session.json"
TARGETS_FILE = SCRIPT_DIR / "instagram_targets.json"
FOLLOWED_LOG_FILE = SCRIPT_DIR / "instagram_followed.json"

def delay(min_sec=30, max_sec=90, is_test=False):
    if is_test:
        return
    sleep_time = random.uniform(min_sec, max_sec)
    print(f"⏳ 사람처럼 보이기 위해 대기 중... ({sleep_time:.1f}초)")
    time.sleep(sleep_time)

def load_targets():
    if not TARGETS_FILE.exists():
        print(f"[X] 타겟 파일이 존재하지 않습니다: {TARGETS_FILE}")
        return [], 50, []
    
    with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 하위 호환성을 위해 targets 키도 지원
    seeds = data.get('seed_accounts', data.get('targets', []))
    min_followers = data.get('min_followers', 50)
    comments = data.get('comments', [])
    
    return seeds, min_followers, comments

def load_followed_users():
    if not FOLLOWED_LOG_FILE.exists():
        return []
    with open(FOLLOWED_LOG_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []

def save_followed_user(username):
    users = load_followed_users()
    if username not in users:
        users.append(username)
        with open(FOLLOWED_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Instagram Engagement Automator (Dynamic Targeting)")
    parser.add_argument('--test', action='store_true', help="실제로 팔로우/댓글을 실행하지 않고 테스트 로그만 출력합니다.")
    args = parser.parse_args()

    print("="*50)
    print(f"🚀 인스타그램 동적 타겟팅 및 자동화 시작 {'(테스트 모드)' if args.test else ''}")
    print("="*50)

    if not SESSION_FILE.exists():
        print("[X] 저장된 인스타그램 세션이 없습니다. 먼저 instagram_login.py를 실행하세요.")
        return

    seed_accounts, min_followers, comments = load_targets()
    if not seed_accounts:
        print("[X] 시드 계정(seed_accounts) 리스트가 비어 있습니다.")
        return

    cl = Client()
    # 잦은 API 호출로 인한 차단 방지
    cl.delay_range = [3, 7]

    print("🔑 세션 로딩 중...")
    try:
        cl.load_settings(SESSION_FILE)
        # cl.login_by_sessionid(os.environ.get("IG_SESSIONID", ""))
    except Exception as e:
        print(f"[X] 세션 로딩 실패: {e}")
        print("세션이 만료되었을 수 있습니다. instagram_login.py를 다시 실행해주세요.")
        return
    
    # 내 계정 정보 확인
    try:
        me = cl.account_info()
        print(f"[V] 로그인 확인: {me.username}")
        initial_following_count = getattr(me, 'following_count', 0)
        print(f"📊 시작 전 팔로잉 수: {initial_following_count}명")
    except Exception as e:
        print(f"[X] 계정 정보 확인 실패 (세션 만료 의심): {e}")
        return

    max_actions = 5  # 하루 최대 처리 계정 수 (밴 방지)
    processed_count = 0
    successful_follows = []  # 성공했다고 반환된 계정 저장

    # 시드 계정 하나를 랜덤하게 선택
    seed_username = random.choice(seed_accounts)
    print(f"\n🌱 선택된 시드 계정: @{seed_username}")
    
    try:
        seed_user_id = cl.user_id_from_username(seed_username)
        # 팔로워 중 일부만 샘플링 (API 호출 최소화)
        print("🔎 시드 계정의 팔로워 목록을 탐색합니다...")
        followers = cl.user_followers(seed_user_id, amount=20)
    except Exception as e:
        print(f"[X] 시드 계정 탐색 실패: {e}")
        return

    follower_list = list(followers.values())
    random.shuffle(follower_list)

    followed_history = load_followed_users()

    for target_user_info in follower_list:
        if processed_count >= max_actions:
            print(f"\n🛑 일일 최대 활동량({max_actions}개 계정) 도달. 작업을 종료합니다.")
            break

        target_username = target_user_info.username
        target_user_id = target_user_info.pk

        print(f"\n👉 타겟 후보 검토 중: @{target_username}")

        # 로컬 기록을 통해 이미 팔로우한 유저인지 검사 (API 호출 없음)
        if target_username in followed_history:
            print(f"   => ⏩ 과거에 이미 팔로우한 기록이 있어 건너뜁니다.")
            continue
        
        try:
            # cl.user_followers()에서 반환된 기본 정보(UserShort) 활용 (추가 API 호출 없음)
            is_private = getattr(target_user_info, 'is_private', False)
            
            if is_private:
                print(f"   => ⏩ 비공개(Private) 계정이므로 건너뜁니다.")
                delay(2, 5, args.test)
                continue

            # 1. 팔로우 로직
            if args.test:
                print(f"   [TEST] @{target_username} 팔로우 시도")
            else:
                try:
                    follow_success = cl.user_follow(target_user_id)
                    if follow_success:
                        print(f"   [V] @{target_username} 팔로우 완료 (API 응답 성공)")
                        save_followed_user(target_username)
                        followed_history.append(target_username)
                        successful_follows.append((target_username, target_user_id))
                    else:
                        print(f"   [X] @{target_username} 팔로우 실패 (인스타그램 측에서 거부함 - 액션 블락 의심)")
                except Exception as e:
                    print(f"   [!] 팔로우 중 오류 발생: {e}")

            # 인스타그램의 강력한 봇 탐지를 피하기 위해 매우 넉넉한 딜레이 적용 (3분 ~ 5분)
            delay(180, 300, args.test)

            # 2. 최근 게시물에 댓글 작성 로직 (현재 비활성화)
            print(f"   [!] @{target_username} 댓글 작성 기능은 현재 비활성화되어 생략합니다.")
            
            processed_count += 1
            delay(10, 20, args.test)

        except Exception as e:
            print(f"[X] @{target_username} 처리 중 오류 발생: {e}")
            delay(10, 20, args.test)

    print("\n" + "="*40)
    print("🔍 최종 팔로우 및 팔로잉 수 점검")
    print("="*40)
    
    if not args.test and successful_follows:
        try:
            # 1. 팔로잉 수 증감 확인
            me_after = cl.account_info()
            final_following_count = getattr(me_after, 'following_count', 0)
            print(f"📊 작업 후 팔로잉 수: {final_following_count}명 (시작 전: {initial_following_count}명)")
            
            # 2. 실제 팔로잉 리스트에서 확인
            print("현재 실제 팔로잉 리스트 조회 중...")
            current_following = cl.user_following(me.pk)
            
            actual_success_count = 0
            for username, user_id in successful_follows:
                # user_following의 key는 string 형태의 user_id임
                if str(user_id) in current_following:
                    print(f"   ✅ @{username} (ID: {user_id}) -> 실제 팔로잉 목록에서 확인됨")
                    actual_success_count += 1
                else:
                    print(f"   ❌ @{username} (ID: {user_id}) -> 실제 팔로잉 목록에 없음 (액션 블락 혹은 서버 반영 지연)")
            
            print(f"\n📢 최종 요약: 시도 {len(successful_follows)}건 중 {actual_success_count}건 실제 반영 성공")
            
        except Exception as e:
            print(f"[!] 최종 점검 중 오류 발생: {e}")
    else:
        print("테스트 모드이거나 성공한 팔로우 시도가 없어 최종 점검을 생략합니다.")

    print("\n🎉 모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료합니다.")
