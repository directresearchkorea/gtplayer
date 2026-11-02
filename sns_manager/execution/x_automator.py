"""
x_automator.py — X(Twitter) 자동 좋아요 봇

타겟 키워드를 기반으로 트윗을 검색하고, 어뷰징 봇 탐지를 우회하기 위해
랜덤한 시간(5초 ~ 15초)을 대기하며 자연스럽게 좋아요(Like)를 누릅니다.

사용법:
  py execution/x_automator.py                  # 기본 실행 (최대 15개 좋아요)
  py execution/x_automator.py --max-likes 25   # 최대 개수 지정
  py execution/x_automator.py --test-mode      # 실제 좋아요 누르지 않고 검색 및 로그만 출력
"""

import os
import sys
import argparse
import time
import random
import logging
import requests
from pathlib import Path
from requests_oauthlib import OAuth1
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent

# 환경 변수 로드 (상위 폴더 및 web 폴더 탐색)
load_dotenv(dotenv_path=str(BASE_DIR / ".env"))
load_dotenv(dotenv_path=str(BASE_DIR / "web" / ".env"), override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("x_automator")


def get_auth():
    """X API OAuth 1.0a 인증 객체 생성"""
    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        log.error("❌ X API 환견 변수(X_API_KEY 등 4개)가 .env 파일에 설정되어 있지 않습니다.")
        sys.exit(1)

    return OAuth1(api_key, api_secret, access_token, access_secret)


def get_my_user_id(auth):
    """현재 인증된 계정의 User ID 반환"""
    url = "https://api.twitter.com/2/users/me"
    try:
        resp = requests.get(url, auth=auth, timeout=15)
        if resp.status_code == 200:
            user_id = resp.json()["data"]["id"]
            username = resp.json()["data"]["username"]
            log.info(f"✅ 인증 완료: @{username} (ID: {user_id})")
            return user_id
        else:
            log.error(f"❌ 사용자 정보 확인 실패 ({resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        log.error(f"❌ 접속 중 오류 발생: {e}")
        return None


def search_tweets(auth, query, max_results=30):
    """해당 쿼리로 최근 트윗 검색"""
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": query,
        "max_results": max_results,
        "tweet.fields": "created_at,author_id,public_metrics,lang",
    }
    try:
        log.info(f"🔍 트윗 검색 중: {query}")
        resp = requests.get(url, auth=auth, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            tweets = data.get("data", [])
            log.info(f"✅ 검색 완료: {len(tweets)}개의 트윗 발견")
            return tweets
        else:
            log.error(f"❌ 트윗 검색 실패 ({resp.status_code}): {resp.text}")
            return []
    except Exception as e:
        log.error(f"❌ 검색 중 오류 발생: {e}")
        return []


def like_tweet(auth, user_id, tweet_id, test_mode=False):
    """지정된 계정으로 트윗 좋아요 누르기"""
    if test_mode:
        log.info(f"   [TEST MODE] 좋아요 처리 건너뜀 (트윗 ID: {tweet_id})")
        return True

    url = f"https://api.twitter.com/2/users/{user_id}/likes"
    payload = {"tweet_id": str(tweet_id)}

    try:
        # API 섀도우밴 감지 우표를 위한 자연스러운 타이밍 지연 (5 ~ 15초)
        delay = random.uniform(5.5, 14.5)
        log.info(f"   ⏳ 사람처럼 행동하기 위해 {delay:.1f}초 대기 중...")
        time.sleep(delay)

        resp = requests.post(url, json=payload, auth=auth, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data", {}).get("liked"):
                log.info(f"   ❤️ 좋아요 성공! (트윗 ID: {tweet_id})")
                return True
            else:
                log.warning(f"   ⚠️ 응답은 정상이지만 liked=false (이미 눌렀을 수 있음).")
                return True
        elif resp.status_code == 429:
            log.error(f"   ❌ [Rate Limit Exceeded] API 한도 초과. 나중에 다시 시도하세요.")
            return False
        else:
            log.error(f"   ❌ 좋아요 실패 ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        log.error(f"   ❌ 좋아요 처리 중 예외 발생: {e}")
        return False


def run(max_likes=15, test_mode=False):
    """메인 실행 프로세스"""
    log.info("🚀 X(Twitter) 자동 좋아요 봇 실행")
    
    auth = get_auth()
    user_id = get_my_user_id(auth)
    if not user_id:
        return

    # 타겟 키워드: 리트윗, 답글 제외
    query = '(게임 OR 닌텐도 OR 플레이스테이션 OR 스팀 OR 엑스박스) -is:retweet -is:reply'
    
    tweets = search_tweets(auth, query, max_results=max_likes * 2)  # 여유 있게 두 배수로 검색
    if not tweets:
        log.info("대상이 없어 종료합니다.")
        return

    likes_count = 0
    for tweet in tweets:
        if likes_count >= max_likes:
            log.info(f"🎉 최대 목표치({max_likes}개) 달성! 작업을 종료합니다.")
            break

        tweet_id = tweet["id"]
        text_preview = tweet["text"][:40].replace('\n', ' ') + "..."
        log.info(f"\n[{likes_count + 1}번째 대상] {text_preview}")
        
        success = like_tweet(auth, user_id, tweet_id, test_mode=test_mode)
        if success:
            likes_count += 1
        else:
            # 실패(Rate Limit 등) 시에는 안전을 위해 중단
            if not test_mode:
                log.warning("⚠️ 좋아요 실패 처리가 발생하여 작업을 조기 중단할 수 있습니다.")
                break

    log.info(f"\n✅ 프로세스 완료! (총 누른 좋아요: {likes_count}개)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X 자동 좋아요 봇")
    parser.add_argument("--max-likes", type=int, default=15, help="1회 최대 좋아요 개수 (기본 15)")
    parser.add_argument("--test-mode", action="store_true", help="실제 좋아요를 누르지 않고 로그만 확인")
    
    args = parser.parse_args()
    
    run(max_likes=args.max_likes, test_mode=args.test_mode)
