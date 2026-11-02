import os
import re
import time
import random
import google.generativeai as genai
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import googleapiclient.errors

# 1. 환경 변수 및 설정 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ 환경 변수에 GEMINI_API_KEY가 없습니다. .env 파일을 확인해주세요.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
# 최신 gemini 모델 설정
model = genai.GenerativeModel('gemini-2.5-flash')

# YouTube API 스코프 (좋아요와 댓글 작성을 위해 force-ssl 등 필요)
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def get_authenticated_service():
    """OAuth 2.0을 통해 인증된 YouTube 서비스 객체를 반환합니다."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"❌ '{CLIENT_SECRETS_FILE}' 파일이 최상위 폴더에 없습니다.")
                print("Google Cloud Console에서 OAuth 2.0 자격증명을 다운로드하여 저장해주세요.")
                exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    return build('youtube', 'v3', credentials=creds)

def extract_video_id(url):
    """YouTube URL에서 Video ID를 추출합니다."""
    # 정규식 패턴: v= 뒷부분이나 짧은 주소 끝부분 매칭
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def generate_comment(title, description, top_comments="없음"):
    """Gemini API를 활용하여 맥락에 맞는 적절한 호응 댓글을 생성합니다."""
    prompt = (
        f"유튜브 영상 제목: {title}\n"
        f"유튜브 영상 설명: {description}\n"
        f"다른 시청자들의 댓글 반응: {top_comments}\n\n"
        "이 영상에 남길 유튜브 댓글을 생성해줘. 다음 규칙을 엄격히 지켜:\n"
        "1. 이 영상이 좋은 포인트를 '아주 짧게(핵심 1~2단어 위주)' 짚어줄 것.\n"
        "2. 문장 끝에는 무조건 '감사합니다!' 혹은 '잘 봤습니다!' 같이 짧고 깔끔한 인사로 끝낼 것.\n"
        "3. 전체 길이는 1~2문장으로, 절대 길게 주절거리지 말 것.\n"
        "4. 기계 같지 않고 현실 유튜브 유저처럼 자연스럽고 경쾌한 말투로 작성할 것.\n"
        "5. 해시태그 금지."
    )
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace('"', '').strip()
        return text
    except Exception as e:
        print(f"⚠️ Gemini 댓글 생성 에러: {e}")
        return "좋은 영상 잘 보고 갑니다! 응원해요." # Fallback

def read_target_urls(filename="youtube_targets.txt"):
    """youtube_targets.txt 파일에서 유효한 URL 리스트를 가져옵니다."""
    if not os.path.exists(filename):
        print(f"❌ 타겟 파일 '{filename}'이 없습니다.")
        return []
        
    urls = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 빈 줄과 주석(#) 무시
            if not line or line.startswith('#'):
                continue
            urls.append(line)
    return urls

def main():
    print("▶️ YouTube 자동 반응 봇을 시작합니다...")
    
    # YouTube API 클라이언트 인증
    youtube = get_authenticated_service()
    print("✅ YouTube 계정 인증 성공")
    
    # 타겟 URL 가져오기
    urls = read_target_urls()
    if not urls:
        print("작업할 URL이 없습니다. youtube_targets.txt를 확인하세요.")
        return

    for index, url in enumerate(urls, 1):
        print(f"\n--- [작업 {index}/{len(urls)}] ----------------------------")
        print(f"🔗 타겟 링크: {url}")
        
        video_id = extract_video_id(url)
        if not video_id:
            print("❌ 올바른 YouTube URL이 아닙니다. 건너뜁니다.")
            continue
            
        print(f"📌 Video ID 파싱됨: {video_id}")
        
        try:
            # 1. 영상 정보 가져오기
            video_response = youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if not video_response.get("items"):
                print("❌ 영상 정보를 찾을 수 없습니다. (비공개 처리되었거나 삭제된 영상일 수 있습니다.)")
                continue
                
            snippet = video_response["items"][0]["snippet"]
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            
            print(f"📺 영상 제목: {title}")
            
            # 다른 사람들의 댓글 가져오기 (문맥 파악용)
            top_comments = []
            try:
                comments_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=5,
                    order="relevance" # 인기순
                ).execute()
                for item in comments_response.get("items", []):
                    text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                    top_comments.append(text)
            except Exception as e:
                print(f"⚠️ 댓글을 가져오는 중 오류 발생 (참고 불가): {e}")
                
            comments_text = "\n- ".join(top_comments) if top_comments else "없음"
            
            # 2. 맞춤 댓글 생성
            comment_text = generate_comment(title, description[:500], comments_text)
            print(f"🤖 생성된 댓글: {comment_text}")
            
            # 3. 좋아요 남기기 ('rate' method) - 테스트를 위해 임시 비활성화
            # youtube.videos().rate(
            #     id=video_id,
            #     rating="like"
            # ).execute()
            # print("👍 좋아요 남기기 성공!")
            print("🛑 (테스트 모드) '좋아요' 누르기를 건너뛰었습니다.")
            
            # 4. 댓글 작성 남기기 ('commentThreads' method) - 테스트를 위해 임시 비활성화
            # youtube.commentThreads().insert(
            #     part="snippet",
            #     body={
            #         "snippet": {
            #             "videoId": video_id,
            #             "topLevelComment": {
            #                 "snippet": {
            #                     "textOriginal": comment_text
            #                 }
            #             }
            #         }
            #     }
            # ).execute()
            # print("💬 댓글 작성 성공!")
            print("🛑 (테스트 모드) '실제 댓글 달기'를 건너뛰었습니다.")
            
            # 마지막 영상이 아니면 안전한 대기시간 적용
            if index < len(urls):
                delay_minutes = random.randint(10, 20)
                delay_seconds = delay_minutes * 60
                print(f"⏳ 봇 탐지 방지를 위해 {delay_minutes}분({delay_seconds}초) 동안 대기합니다...")
                time.sleep(delay_seconds)

        except googleapiclient.errors.HttpError as e:
            print(f"❌ YouTube API 에러 발생: {e}")
        except Exception as e:
            print(f"❌ 예기치 않은 오류 발생: {e}")
            
    print("\n✅ 모든 타겟 작업을 마쳤습니다.")

if __name__ == "__main__":
    main()
