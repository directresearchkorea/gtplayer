"""
YouTube 게임 마이크로 인플루언서 채널 수집기
============================================
게임 키워드로 영상을 검색하여 구독자 3,000명 이하의 소규모 채널을 수집합니다.
결과는 CSV 파일로 저장되어 구글 시트에서 바로 열 수 있습니다.

사용법:
    py execution/youtube_channel_finder.py
"""

import os
import sys
import csv
import json
import time
import random
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googleapiclient.errors

load_dotenv()

# === 설정 ===
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

MAX_SUBSCRIBERS = 3000
MIN_SUBSCRIBERS = 10
TARGET_COUNT = 100
PAGES_PER_KEYWORD = 2  # 키워드당 페이지 수 (1페이지 = 50결과)

PROGRESS_FILE = os.path.join(".tmp", "channel_finder_progress.json")
OUTPUT_CSV = os.path.join(".tmp", "youtube_micro_influencers_KR.csv")

# === 한국 게임 검색 키워드 ===
KEYWORDS = [
    "게임 공략",
    "게임 후기",
    "게임 추천",
    "게임 리뷰",
    "게임 플레이",
    "인디게임",
    "모바일게임 추천",
    "게임 실황",
    "신작 게임",
    "스팀 게임 추천",
]


def get_authenticated_service():
    """기존 token.json을 재사용하여 YouTube API 인증"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"❌ '{CLIENT_SECRETS_FILE}' 파일이 없습니다.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)


def load_progress():
    """이전 진행 상태를 불러옵니다 (중단 후 재개 가능)"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"channels": {}, "completed_keywords": [], "quota_used": 0}


def save_progress(progress):
    """진행 상태를 저장합니다"""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def write_csv(channels):
    """수집된 채널 데이터를 CSV로 저장합니다"""
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    
    # 구독자 수 기준 내림차순 정렬
    sorted_channels = sorted(channels.values(), key=lambda x: x["subscribers"], reverse=True)
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            "채널명", "채널 URL", "구독자 수", "영상 수",
            "채널 설명", "발견 키워드", "발견 영상 제목",
            "발견 영상 URL", "최근 영상 날짜"
        ])
        for ch in sorted_channels:
            writer.writerow([
                ch["name"],
                ch["url"],
                ch["subscribers"],
                ch["video_count"],
                ch.get("description", "")[:100],  # 설명은 100자까지
                ch["keyword"],
                ch["video_title"],
                ch["video_url"],
                ch.get("video_date", ""),
            ])
    
    print(f"\n📄 CSV 저장 완료: {OUTPUT_CSV} ({len(sorted_channels)}개 채널)")


def main():
    print("🔍 YouTube 한국 게임 마이크로 인플루언서 채널 수집을 시작합니다...")
    print(f"   목표: 구독자 {MAX_SUBSCRIBERS}명 이하 채널 {TARGET_COUNT}개\n")
    
    youtube = get_authenticated_service()
    print("✅ YouTube API 인증 성공\n")
    
    progress = load_progress()
    channels = progress["channels"]
    completed_keywords = progress["completed_keywords"]
    quota_used = progress["quota_used"]
    
    if channels:
        print(f"📌 이전 진행 상태 복원: {len(channels)}개 채널 수집됨, Quota {quota_used} 사용됨")
    
    for keyword in KEYWORDS:
        # 이미 목표 달성했으면 종료
        if len(channels) >= TARGET_COUNT:
            print(f"\n🎉 목표 달성! {len(channels)}개 채널 수집 완료!")
            break
        
        # 이미 처리한 키워드는 건너뛰기
        if keyword in completed_keywords:
            print(f"⏭️  '{keyword}' — 이미 처리됨, 건너뜁니다.")
            continue
        
        print(f"\n🔎 키워드: '{keyword}' 검색 중...")
        
        page_token = None
        new_found = 0
        
        for page in range(PAGES_PER_KEYWORD):
            # Quota 안전 한도 체크
            if quota_used >= 9500:
                print("\n⚠️ 일일 Quota 한도에 근접했습니다. 내일 다시 실행해주세요.")
                save_progress(progress)
                write_csv(channels)
                return
            
            try:
                # 1단계: 게임 영상 검색
                search_params = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "regionCode": "KR",
                    "relevanceLanguage": "ko",
                    "maxResults": 50,
                    "order": "date" if page == 1 else "relevance",
                }
                if page_token:
                    search_params["pageToken"] = page_token
                
                results = youtube.search().list(**search_params).execute()
                quota_used += 100
                
                # 고유 채널 ID 추출 (이미 수집한 채널 제외)
                video_data = {}  # channelId -> video info
                for item in results.get("items", []):
                    cid = item["snippet"]["channelId"]
                    if cid not in channels and cid not in video_data:
                        video_data[cid] = {
                            "video_title": item["snippet"]["title"],
                            "video_url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                            "video_date": item["snippet"]["publishedAt"][:10],
                            "keyword": keyword,
                        }
                
                if not video_data:
                    print(f"   페이지 {page+1}: 새로운 채널 없음")
                    page_token = results.get("nextPageToken")
                    if not page_token:
                        break
                    continue
                
                # 2단계: 채널 정보 일괄 조회 (최대 50개씩)
                channel_ids = list(video_data.keys())
                ch_response = youtube.channels().list(
                    part="snippet,statistics",
                    id=",".join(channel_ids)
                ).execute()
                quota_used += 5
                
                # 3단계: 구독자 수 필터링
                for ch in ch_response.get("items", []):
                    cid = ch["id"]
                    stats = ch.get("statistics", {})
                    
                    # 구독자 수 비공개인 경우 건너뛰기
                    if stats.get("hiddenSubscriberCount", False):
                        continue
                    
                    subs = int(stats.get("subscriberCount", 0))
                    
                    if MIN_SUBSCRIBERS <= subs <= MAX_SUBSCRIBERS:
                        vinfo = video_data[cid]
                        channels[cid] = {
                            "name": ch["snippet"]["title"],
                            "url": f"https://www.youtube.com/channel/{cid}",
                            "subscribers": subs,
                            "video_count": int(stats.get("videoCount", 0)),
                            "description": ch["snippet"].get("description", ""),
                            "keyword": vinfo["keyword"],
                            "video_title": vinfo["video_title"],
                            "video_url": vinfo["video_url"],
                            "video_date": vinfo["video_date"],
                        }
                        new_found += 1
                
                print(f"   페이지 {page+1}: +{new_found}개 (누적 {len(channels)}개) | Quota: {quota_used}")
                
                # 목표 달성 체크
                if len(channels) >= TARGET_COUNT:
                    break
                
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
                
                # API 부하 방지 딜레이
                time.sleep(random.uniform(0.5, 1.5))
                
            except googleapiclient.errors.HttpError as e:
                print(f"   ❌ API 에러: {e}")
                time.sleep(2)
                continue
        
        completed_keywords.append(keyword)
        progress["channels"] = channels
        progress["completed_keywords"] = completed_keywords
        progress["quota_used"] = quota_used
        save_progress(progress)
        
        print(f"   ✅ '{keyword}' 완료 — 현재 {len(channels)}개 채널 수집됨")
    
    # 최종 결과 CSV 저장
    write_csv(channels)
    
    print(f"\n{'='*50}")
    print(f"📊 최종 결과: {len(channels)}개 채널 수집 완료")
    print(f"📊 총 Quota 사용량: {quota_used}/10,000")
    print(f"📄 파일 경로: {OUTPUT_CSV}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
