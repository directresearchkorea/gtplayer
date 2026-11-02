import os
import requests
from requests_oauthlib import OAuth1
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

api_key = os.getenv("X_API_KEY")
api_secret = os.getenv("X_API_SECRET")
access_token = os.getenv("X_ACCESS_TOKEN")
access_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

print("--- X API 키 확인 ---")
print(f"API_KEY: {api_key[:5] if api_key else 'None'}...")
print(f"ACCESS_TOKEN: {access_token[:5] if access_token else 'None'}...")
print("-" * 20)

if not all([api_key, api_secret, access_token, access_secret]):
    print("❌ 오류: .env에 키가 부족합니다.")
    exit(1)

auth = OAuth1(api_key, api_secret, access_token, access_secret)
url = "https://api.twitter.com/2/tweets"
payload = {"text": "GTPlayer X API Connection Test 🎮"}

try:
    print("🚀 API 요청 중...")
    resp = requests.post(url, json=payload, auth=auth, timeout=30)
    print(f"상태 코드: {resp.status_code}")
    print(f"응답 본문: {resp.text}")
except Exception as e:
    print(f"❌ 예외 발생: {e}")
