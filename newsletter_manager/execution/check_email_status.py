"""
SendGrid 이메일 발송 상태 확인 스크립트
- 최근 발송된 메일의 상태(delivered / bounced / blocked 등)를 조회
"""

import os
import sys
import subprocess
import urllib.request
import json

try:
    from dotenv import load_dotenv
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv", "--quiet"])
    from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

# ── 최근 발송 활동 조회 ─────────────────────────────────────────────────────────
url = "https://api.sendgrid.com/v3/messages?limit=10"
req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        messages = data.get("messages", [])
        if not messages:
            print("❌ 최근 메시지 내역이 없습니다.")
            print("   → SendGrid 대시보드 > Activity 탭에서 직접 확인하세요.")
        else:
            print(f"최근 {len(messages)}건 발송 내역:\n")
            for m in messages:
                print(f"  제목    : {m.get('subject','')}")
                print(f"  수신자  : {m.get('to_email','')}")
                print(f"  상태    : {m.get('status','')}")
                print(f"  시각    : {m.get('last_event_time','')}")
                print(f"  클릭수  : {m.get('clicks_count',0)}")
                print(f"  열람수  : {m.get('opens_count',0)}")
                print("-" * 50)
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"[HTTP {e.code}] 오류: {body}")
    if e.code == 403:
        print("\n⚠️  Email Activity Feed 권한이 없습니다.")
        print("   → SendGrid 대시보드에서 직접 확인이 필요합니다.")
        print("   경로: Activity > Email Activity")
except Exception as e:
    print(f"[오류] {e}")
