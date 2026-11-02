"""
x_browser_automator.py - X(Twitter) 브라우저 자동 좋아요 처리 (No-API)

API를 사용하지 않고 브라우저 자동화를 통해 트위터에 접속하여
타겟 키워드 관련 최신 트윗에 좋아요(Like)를 누릅니다.

사용법:
  py sns_manager/execution/x_browser_automator.py               # 기본 (1개 좋아요 누르기)
  py sns_manager/execution/x_browser_automator.py --max-likes 3 # 최대 개수 지정
  py sns_manager/execution/x_browser_automator.py --visible     # 브라우저 창 띄우기 (디버깅용)
"""

import os
import sys
import time
import random
import logging
import argparse
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Playwright 설치 필요: py -m pip install playwright && py -m playwright install chromium
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 오류: playwright가 설치되어 있지 않습니다. 명령어로 설치해 주세요:")
    print("   py -m pip install playwright")
    print("   py -m playwright install chromium")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
TMP_DIR = BASE_DIR / ".tmp"
STATE_PATH = TMP_DIR / "x_state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("x_browser_automator")


def find_latest_edition():
    editions_dir = BASE_DIR / "web" / "editions"
    files = sorted(editions_dir.glob("edition_*.json"), reverse=True)
    return files[0] if files else None

def clean_game_name(raw_name):
    if not raw_name:
        return ""
    # 콜론/하이픈/물결표 등 부제 구분자 앞의 메인 게임명만 추출 (예: '헬 렛 루즈: 베트남' -> '헬 렛 루즈')
    main_name = re.split(r'[:\-–~]', raw_name)[0].strip()
    # 괄호 제거 (예: '게임명 (모바일)' -> '게임명')
    main_name = re.sub(r'\(.*?\)', '', main_name).strip()
    return main_name

def get_dynamic_query():
    latest_json = find_latest_edition()
    raw_keywords = []
    seen_raw = set()
    
    if latest_json and latest_json.exists():
        import json, re
        try:
            with open(latest_json, "r", encoding="utf-8") as f:
                edition = json.load(f)
                sections = edition.get("sections", {})
                
                # 1. 트레일러 / OST / 게임씬 메인 타겟 게임명
                for sec_key in ["trailer", "gamescene", "soundtrack"]:
                    sec = sections.get(sec_key, {})
                    if sec.get("enabled", False):
                        gname = sec.get("ai_game_name") or sec.get("game")
                        if gname and gname not in seen_raw:
                            raw_keywords.append(gname.strip())
                            seen_raw.add(gname.strip())
                            
                # 2. 브리핑 타이틀에서 따옴표('...') 안의 핵심 게임명 추출
                for item in sections.get("briefing", {}).get("items", []):
                    title = item.get("title", "")
                    quoted = re.findall(r"'([^']+)'", title)
                    for q in quoted:
                        q_clean = q.strip()
                        if len(q_clean) >= 2 and q_clean not in seen_raw:
                            if not any(w in q_clean for w in ["뉴스", "이슈", "출시", "업데이트", "단독", "공개", "연기"]):
                                raw_keywords.append(q_clean)
                                seen_raw.add(q_clean)

                # 3. 캘린더 주요 신작 게임명
                for r in sections.get("calendar", {}).get("releases", []):
                    gname = r.get("game")
                    if gname and gname.strip() not in seen_raw:
                        raw_keywords.append(gname.strip())
                        seen_raw.add(gname.strip())

        except Exception as e:
            log.error(f"❌ 에디션 JSON 키워드 로딩 실패: {e}")

    # 실제 트위터 유저들이 검색/언급하는 핵심 단어(부제 제거 + 띄어쓰기 제거 변형)로 정제
    final_terms = []
    seen_terms = set()
    
    for raw in raw_keywords:
        main_title = clean_game_name(raw)
        if len(main_title) >= 2:
            # 1) 기본 메인 이름 (예: "헬 렛 루즈")
            if main_title not in seen_terms:
                final_terms.append(f'"{main_title}"')
                seen_terms.add(main_title)
            # 2) 띄어쓰기 없는 붙여쓰기 버전 (예: "헬렛루즈")
            unspaced = main_title.replace(" ", "")
            if len(unspaced) >= 2 and unspaced != main_title and unspaced not in seen_terms:
                final_terms.append(f'"{unspaced}"')
                seen_terms.add(unspaced)

    if final_terms:
        selected = final_terms[:6]  # 트위터 실검색용 정제 키워드 최대 6개 조합
        query = f'({" OR ".join(selected)}) -filter:replies -filter:retweets'
        log.info(f"💡 트위터 유저용 정제 키워드 조합 성공: {', '.join(selected)}")
    else:
        query = '("스팀게임" OR "신작게임" OR "PS5" OR "닌텐도스위치") -filter:replies -filter:retweets'
        log.info("⚠️ 동적 키워드 추출 실패. 기본 키워드를 사용합니다.")
    
    return query

def run(max_likes=1, visible=False):
    log.info(f"🚀 X(Twitter) 브라우저 자동화 시작 (목표 좋아요: {max_likes}개)")
    
    if not STATE_PATH.exists():
        log.error("❌ 저장된 로그인 세션(x_state.json)이 없습니다.")
        log.error("   먼저 'py sns_manager/execution/x_browser_login.py'를 실행하여 로그인해주세요!")
        return

    # 타겟 검색 URL (동적 게임명 추출)
    from urllib.parse import quote
    query = get_dynamic_query()
    search_url = f"https://x.com/search?q={quote(query)}&f=live"

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="msedge",
                headless=not visible, 
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception:
            browser = p.chromium.launch(
                headless=not visible, 
                args=["--disable-blink-features=AutomationControlled"]
            )
        
        # 저장된 인증 쿠키를 이용해 새 텍스트 생성
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()

        # 브라우저 고유 탐지 우회 시도(옵션)
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        log.info(f"🔍 검색 페이지 접속 중: {query}")
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # 페이지 로딩을 위한 지연 대기
            page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
        except Exception as e:
            log.error(f"❌ 접속 오류 혹은 트윗을 찾을 수 없습니다: {e}")
            # 로그인 문제가 있을 가능성도 있으므로 캡처 혹은 상태 점검 요망
            browser.close()
            return

        log.info("✅ 트윗 목록 발견 처리 시작...")
        
        likes_done = 0
        scroll_attempts = 0

        while likes_done < max_likes and scroll_attempts < 10:
            tweets = page.query_selector_all('article[data-testid="tweet"]')
            
            for tweet in tweets:
                if likes_done >= max_likes:
                    break
                
                try:
                    # 작성자 정보 검사 (공식 언론사, 웹진, 브랜드 공식 계정 제외)
                    user_elem = tweet.query_selector('[data-testid="User-Name"]')
                    if user_elem:
                        author_info = user_elem.inner_text().lower()
                        excluded_keywords = [
                            "inven", "gamemeca", "ruliweb", "thisisgame", "ign", "gamefocus", "khgames",
                            "playstation", "nintendo", "xbox", "steam", "인벤", "게임메카", "루리웹", 
                            "디스이즈게임", "게임포커스", "경향게임스", "공식", "뉴스", "news", "bot", "봇"
                        ]
                        if any(ex in author_info for ex in excluded_keywords):
                            author_display = user_elem.inner_text().split("\n")[0]
                            log.info(f"   ⏩ 공식/언론사 계정 감지 ({author_display}) -> 개인 유저가 아니므로 건너뜁니다.")
                            continue

                    # 해당 트윗 내에 표시된 '좋아요(Like)' 버튼 찾기
                    like_btn = tweet.query_selector('[data-testid="like"]')
                    
                    if like_btn:
                        # 화면에 노출되도록 스크롤
                        like_btn.scroll_into_view_if_needed()
                        
                        # 어스뷰를 피하기 위해 살짝 대기 (아주 천천히)
                        delay = random.uniform(15.0, 35.0)
                        log.info(f"   ⏳ {delay:.1f}초 대기 후 좋아요 클릭 시도...")
                        time.sleep(delay)
                        
                        like_btn.click()
                        likes_done += 1
                        log.info(f"   ❤️ 좋아요 성공! ({likes_done}/{max_likes})")
                        
                        # 클릭 후 추가 대기
                        time.sleep(random.uniform(1.0, 3.0))
                    else:
                        # 이미 좋아요가 눌려있는 경우 [data-testid="unlike"] 로 잡힘
                        pass
                except Exception as e:
                    log.warning(f"   ⚠️ 버튼 클릭 중 예외 발생: {e}")
            
            # 한 화면에서 더 이상 누를 트윗이 없다면 스크롤 다운
            if likes_done < max_likes:
                page.mouse.wheel(0, 800)
                time.sleep(random.uniform(2.0, 4.0))
                scroll_attempts += 1
        
        if likes_done >= max_likes:
            log.info("🎉 목표 좋아요 개수 달성 완료. 브라우저를 종료합니다.")
        else:
            log.info("⚠️ 더 이상 누를 수 있는 대상을 찾지 못했거나 오류로 조기 종료되었습니다.")

        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-likes", type=int, default=1, help="하루 1회당 좋아요 개수 (기본 1)")
    parser.add_argument("--visible", action="store_true", help="브라우저 화면을 직접 보며 실행")
    
    args = parser.parse_args()
    
    try:
        run(max_likes=args.max_likes, visible=args.visible)
    except Exception as e:
        log.error(f"실행 중 치명적 오류 발생: {e}")
