"""
GTPlayer Newsletter — Test Send Script
Sends 3 design variants to the specified email via SendGrid.
"""

import os
import sys
import subprocess

# ── 의존성 확인 ────────────────────────────────────────────────────────────────
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:
    print("[ERROR] sendgrid 패키지가 없습니다. 설치 중...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sendgrid", "python-dotenv"])
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

try:
    from dotenv import load_dotenv
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

# ── 환경변수 로드 ───────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL       = os.getenv('FROM_EMAIL', 'admin@gtplayer.net')
FROM_NAME        = os.getenv('FROM_NAME', 'GTPlayer 뉴스레터')
TO_EMAIL         = os.getenv('TO_EMAIL', 'admin@gtplayer.net')

if not SENDGRID_API_KEY:
    print("[ERROR] SENDGRID_API_KEY가 .env에 없습니다.")
    sys.exit(1)

# ── 발송할 3개 이메일 정의 ──────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '.tmp')

emails = [
    {
        'subject': '[GTPlayer] 🌑 Option A: Dark Gaming Edition — 2026.03.14',
        'html_file': 'email_dark.html',
    },
    {
        'subject': '[GTPlayer] 🌿 Option B: Clean Minimal Edition — 2026.03.14',
        'html_file': 'email_clean.html',
    },
    {
        'subject': '[GTPlayer] 🔥 Option C: Bold Magazine Edition — 2026.03.14',
        'html_file': 'email_bold.html',
    },
]

# ── 발송 ───────────────────────────────────────────────────────────────────────
sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)

for i, email in enumerate(emails, 1):
    html_path = os.path.join(BASE_DIR, email['html_file'])
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    message = Mail(
        from_email=(FROM_EMAIL, FROM_NAME),
        to_emails=TO_EMAIL,
        subject=email['subject'],
        html_content=html_content,
    )

    try:
        response = sg.send(message)
        print(f"[{i}/3] ✅ 발송 성공: {email['subject'][:50]}... (status: {response.status_code})")
    except Exception as e:
        print(f"[{i}/3] ❌ 발송 실패: {email['subject'][:50]}...")
        print(f"       오류: {e}")

print("\n📬 모두 완료! admin@gtplayer.net 받은편지함을 확인하세요.")
