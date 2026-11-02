"""
instagram_browser_automator.py - Playwright 기반 인스타그램 자동화 (Headed 브라우저 제어)

저장된 세션 정보를 로드하여 타겟 계정(시드 계정의 팔로워)을 안전하게 자동 팔로우합니다.

사용법:
  py sns_manager/execution/instagram_browser_automator.py [--test]
"""

import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
STATE_PATH = TMP_DIR / "instagram_state.json"
TARGETS_FILE = SCRIPT_DIR / "instagram_targets.json"
FOLLOWED_LOG_FILE = SCRIPT_DIR / "instagram_followed.json"

def delay(min_sec=180, max_sec=300, is_test=False):
    if is_test:
        return
    sleep_time = random.uniform(min_sec, max_sec)
    print(f"⏳ 대기 중... ({sleep_time:.1f}초)")
    time.sleep(sleep_time)

def load_targets():
    if not TARGETS_FILE.exists():
        print(f"[X] 설정 파일이 없습니다: {TARGETS_FILE}")
        return []
    with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('seed_accounts', [])

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
    parser = argparse.ArgumentParser(description="Instagram Playwright Automator")
    parser.add_argument('--test', action='store_true', help="실제 클릭을 수행하지 않는 테스트 모드")
    args = parser.parse_args()

    print("="*50)
    print(f"🚀 인스타그램 브라우저 자동화 시작 {'(테스트 모드)' if args.test else ''}")
    print("="*50)

    if not STATE_PATH.exists():
        print("❌ 로그인 세션 파일이 없습니다. 먼저 instagram_browser_login.py를 실행하세요.")
        return

    seed_accounts = load_targets()
    if not seed_accounts:
        print("❌ 시드 계정이 비어 있습니다.")
        return

    followed_history = load_followed_users()
    seed_username = random.choice(seed_accounts)
    print(f"🌱 선택된 시드 계정: @{seed_username}")

    max_actions = 5
    processed_count = 0
    successful_follows = []

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

        # 로그인 세션 상태 적용하여 컨텍스트 생성
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()
        
        # 봇 탐지 속이기 우회 스크립트
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 2. 시드 계정 탐색 및 팔로워 목록 열기 (최대 3개 시드 시도)
        targets = []
        random.shuffle(seed_accounts)

        for seed_username in seed_accounts[:3]:
            print(f"\n🌱 선택된 시드 계정 시도: @{seed_username}")
            print(f"🔗 @{seed_username} 프로필 진입 중...")
            page.goto(f"https://www.instagram.com/{seed_username}/")
            page.wait_for_timeout(3000)

            # 로그인 여부 검사
            if page.locator('a[href="/accounts/emailsignup/"]').is_visible() or page.locator('button:has-text("Log In")').is_visible():
                print("❌ 세션이 만료되었습니다. instagram_browser_login.py를 다시 실행하세요.")
                browser.close()
                return

            # 시드 계정 자동 확장 (연관 계정 수집)
            print("🌱 연관 계정(시드 확장용) 탐색 시도...")
            try:
                similar_btn = page.locator('button[aria-label="Similar accounts"], button[aria-label="유사한 계정"], button[aria-label*="Down chevron"]').first
                if similar_btn.is_visible():
                    similar_btn.click()
                    page.wait_for_timeout(3000)
                    
                suggested_links = page.locator('a[href^="/"]').all()
                new_seeds = set()
                for link in suggested_links:
                    href = link.get_attribute('href')
                    if href:
                        parts = [p for p in href.split('/') if p]
                        if len(parts) == 1:
                            username = parts[0]
                            if username not in seed_accounts and username not in ['explore', 'reels', 'direct', 'play', 'accounts', 'developer', 'about', 'blog', 'help', 'api', 'privacy', 'terms', 'locations', 'popular']:
                                new_seeds.add(username)
                
                if new_seeds:
                    added_seeds = random.sample(list(new_seeds), min(2, len(new_seeds)))
                    print(f"💡 새로운 타겟 시드 계정 자동 발굴 및 추가: {added_seeds}")
                    with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
                        t_data = json.load(f)
                    t_data['seed_accounts'] = list(set(t_data.get('seed_accounts', []) + added_seeds))
                    with open(TARGETS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(t_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ 연관 계정 탐색 실패 (무시하고 진행): {e}")

            # 팔로워 목록 열기 (강화된 다국어/요소 셀렉터)
            print("🔎 팔로워 목록 여는 중...")
            followers_link = page.locator('a[href*="/followers"], a:has-text("followers"), a:has-text("팔로워"), button:has-text("팔로워"), button:has-text("followers")').first
            try:
                followers_link.wait_for(state="visible", timeout=7000)
                followers_link.click()
                page.wait_for_timeout(4000)
            except Exception as e:
                print(f"❌ @{seed_username} 팔로워 링크를 찾을 수 없어 다음 시드 계정을 시도합니다.")
                screenshot_path = TMP_DIR / "instagram_followers_failed.png"
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:
                    pass
                continue

            # 3. 팔로워 목록 스크롤 및 username 파싱
            print("📜 팔로워 리스트 스크롤링 및 수집 중...")
            dialog_selector = 'div[role="dialog"]'
            try:
                page.wait_for_selector(dialog_selector, timeout=7000)
            except Exception:
                print(f"❌ @{seed_username} 팔로워 대화상자가 열리지 않았습니다. 다음 시드 계정 시도...")
                continue
            
            scroll_script = """
            (() => {
                const dialog = document.querySelector('div[role="dialog"]');
                const scrollable = dialog ? (dialog.querySelector('div[style*="overflow-y"]') || dialog.querySelector('._aano') || dialog) : null;
                if (scrollable) {
                    scrollable.scrollBy(0, 500);
                    return true;
                }
                return false;
            })()
            """
            
            target_usernames = set()
            for _ in range(3):
                page.evaluate(scroll_script)
                page.wait_for_timeout(1500)
                
                links = page.locator('div[role="dialog"] a[href^="/"]').all()
                for link in links:
                    href = link.get_attribute('href') or ""
                    parts = [p for p in href.split('/') if p]
                    if len(parts) == 1:
                        username = parts[0]
                        if username not in ['explore', 'reels', 'direct', 'play', 'accounts', 'developer', 'about', 'blog', 'help', 'api', 'privacy', 'terms', 'locations', 'popular']:
                            target_usernames.add(username)
            
            close_btn = page.locator('div[role="dialog"] button:has(svg[aria-label="Close"]), div[role="dialog"] button:has(svg[aria-label="닫기"])')
            if close_btn.is_visible():
                close_btn.click()
            
            targets = list(target_usernames)
            if targets:
                print(f"🎯 @{seed_username}에서 총 {len(targets)}개의 타겟 후보 계정을 발굴했습니다!")
                break
        print(f"후보 리스트: {targets[:10]}...")

        # 4. 각 타겟 순회 및 팔로우 시도
        for target in targets:
            if processed_count >= max_actions:
                print(f"\n🛑 일일 최대 활동량({max_actions}개 계정) 도달. 작업을 종료합니다.")
                break

            if target in followed_history:
                print(f"\n⏩ @{target} -> 과거에 이미 팔로우한 기록이 있어 건너뜁니다.")
                continue

            print(f"\n👉 @{target} 프로필 방문 중...")
            page.goto(f"https://www.instagram.com/{target}/")
            page.wait_for_timeout(3000)

            # 비공개 계정 여부 검사
            is_private = (
                page.locator('text="This account is private"').is_visible() or 
                page.locator('text="비공개 계정입니다"').is_visible()
            )
            if is_private:
                print(f"   => ⏩ 비공개 계정이므로 건너뜁니다.")
                continue

            import re
            # 한국인 계정 필터링 (한글 감지)
            try:
                profile_text = page.locator('header').inner_text(timeout=3000)
                if not re.search(r'[가-힣]', profile_text):
                    print("   => ⏩ 프로필(이름/소개글)에 한글이 전혀 없어 외국인/글로벌 계정으로 간주하고 건너뜁니다.")
                    continue
                else:
                    print("   => 🇰🇷 한글 프로필 감지 완료 (한국 게이머 확인)")
            except Exception as e:
                print(f"   ⚠️ 프로필 텍스트 분석 실패, 일단 진행합니다: {e}")

            # 최신 게시물 좋아요 누르기 시도
            try:
                first_post = page.locator('a[href^="/p/"]').first
                if first_post.is_visible():
                    post_href = first_post.get_attribute('href')
                    if post_href:
                        post_url = f"https://www.instagram.com{post_href}"
                        print(f"   📸 최신 게시물로 이동 중: {post_url}")
                        page.goto(post_url)
                        page.wait_for_timeout(3000)
                        
                        # 좋아요 버튼 찾기 (영어/한국어/일본어 대응)
                        like_button = page.locator('button:has(svg[aria-label="Like"]), button:has(svg[aria-label="좋아요"]), button:has(svg[aria-label="いいね！"]), button:has(svg[aria-label="「いいね！」"])').first
                        if like_button.is_visible():
                            if args.test:
                                print(f"   [TEST] 게시물 좋아요 클릭 시뮬레이션")
                            else:
                                print(f"   🖱 게시물 좋아요 클릭!")
                                like_button.click()
                                page.wait_for_timeout(2000)
                        else:
                            print("   ⏩ 이미 좋아요 상태이거나 좋아요 버튼을 찾을 수 없습니다.")
                        
                        # 프로필 페이지로 복귀
                        print(f"   🔙 프로필로 돌아가는 중...")
                        page.goto(f"https://www.instagram.com/{target}/")
                        page.wait_for_timeout(3000)
                else:
                    print("   ⏩ 게시물이 없어 좋아요 작업을 건너뜁니다.")
            except Exception as e:
                print(f"   ⚠️ 좋아요 작업 중 에러 발생 (건너뜀): {e}")
                # 혹시 모르니 프로필 페이지로 다시 리디렉트
                page.goto(f"https://www.instagram.com/{target}/")
                page.wait_for_timeout(3000)

            # 팔로우 버튼 검색
            # 다국어 및 상황을 고려한 셀렉터 구성
            follow_button = None
            button_texts = ["Follow", "팔로우", "Follow Back", "맞팔로우"]
            for text in button_texts:
                btn = page.locator(f'button:has-text("{text}")').first
                if btn.is_visible():
                    follow_button = btn
                    break

            if not follow_button:
                # 이미 팔로잉 중이거나 요청중인지 확인
                is_following = (
                    page.locator('button:has-text("Following")').is_visible() or 
                    page.locator('button:has-text("팔로잉")').is_visible() or 
                    page.locator('button:has-text("Requested")').is_visible() or 
                    page.locator('button:has-text("요청됨")').is_visible()
                )
                if is_following:
                    print("   => ⏩ 이미 팔로우 또는 팔로우 요청 상태이므로 건너뜁니다.")
                else:
                    print("   => ⚠️ 팔로우 버튼을 찾을 수 없습니다. (스킵)")
                continue

            # 실제 클릭 실행
            if args.test:
                print(f"   [TEST] @{target} 팔로우 버튼 클릭 시뮬레이션")
                processed_count += 1
            else:
                print(f"   🖱 @{target} 팔로우 버튼 클릭!")
                follow_button.click()
                page.wait_for_timeout(4000)  # 서버 반영 대기

                # 결과 2차 검증 (버튼이 Following/팔로잉/Requested/요청됨 으로 바뀌었는지 확인)
                success_indicators = ["Following", "팔로잉", "Requested", "요청됨"]
                succeeded = False
                for indicator in success_indicators:
                    if page.locator(f'button:has-text("{indicator}")').is_visible():
                        succeeded = True
                        break

                if succeeded:
                    print(f"   ✅ @{target} 팔로우 완료 및 검증 성공!")
                    save_followed_user(target)
                    followed_history.append(target)
                    successful_follows.append(target)
                    processed_count += 1
                    delay(240, 420, args.test)  # 4분 ~ 7분 아주 긴 랜덤 딜레이 (사람처럼)
                else:
                    print(f"   ❌ @{target} 팔로우 후 상태 검증 실패 (액션 블락 의심!)")
                    delay(15, 30, args.test)

        print("\n" + "="*40)
        print("🔍 최종 팔로우 및 팔로잉 수 점검")
        print("="*40)
        
        if not args.test and successful_follows:
            print(f"📢 최종 요약: 오늘 {len(successful_follows)}개 계정을 성공적으로 팔로우하고 검증했습니다.")
            print(f"목록: {successful_follows}")
        else:
            print("최종 점검 대상이 없거나 테스트 모드입니다.")

        browser.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n종료합니다.")
