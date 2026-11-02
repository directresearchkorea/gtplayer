"""
GTPlayer #001 — 실제 뉴스레터 테스트 발송
이미지를 인라인 첨부(Content-ID)로 포함하여 발송
"""

import os
import sys
import base64
import subprocess

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName,
        FileType, Disposition, ContentId
    )
    from dotenv import load_dotenv
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sendgrid", "python-dotenv", "--quiet"])
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName,
        FileType, Disposition, ContentId
    )
    from dotenv import load_dotenv

# ── 환경변수 ───────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

FROM_EMAIL = os.getenv('FROM_EMAIL', 'admin@gtplayer.net')
FROM_NAME  = os.getenv('FROM_NAME', 'GTPlayer 뉴스레터')
TO_EMAIL   = os.getenv('TO_EMAIL', 'admin@gtplayer.net')

# ── 파일 경로 ─────────────────────────────────────────────────────────────────
BASE       = os.path.join(os.path.dirname(__file__), '..', '..')
HTML_FILE  = os.path.join(BASE, '.tmp', 'gtplayer_001.html')
IMG_FILE   = os.getenv('NEWSLETTER_IMG', os.path.join(BASE, '.tmp', 'gamescene_001.png'))

# ── HTML 로드 ─────────────────────────────────────────────────────────────────
with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html_content = f.read()

# ── 이미지 base64 인코딩 ───────────────────────────────────────────────────────
with open(IMG_FILE, 'rb') as f:
    encoded_img = base64.b64encode(f.read()).decode()

# ── 메일 구성 ─────────────────────────────────────────────────────────────────
message = Mail(
    from_email=(FROM_EMAIL, FROM_NAME),
    to_emails=TO_EMAIL,
    subject='[GTPlayer] #001 — 게임 인사이트 뉴스레터 · 2026.03.14',
    html_content=html_content,
)

# 인라인 이미지 첨부 (Content-ID: gamescene001)
attachment = Attachment()
attachment.file_content = FileContent(encoded_img)
attachment.file_type    = FileType('image/png')
attachment.file_name    = FileName('gamescene001.png')
attachment.disposition  = Disposition('inline')
attachment.content_id   = ContentId('gamescene001')
message.attachment      = attachment

# ── 발송 ─────────────────────────────────────────────────────────────────────
sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
try:
    response = sg.send(message)
    print(f"✅ GTPlayer #001 발송 성공! (status: {response.status_code})")
    print(f"   수신: {TO_EMAIL}")
    print(f"   제목: [GTPlayer] #001 — 게임 인사이트 뉴스레터 · 2026.03.14")
except Exception as e:
    print(f"❌ 발송 실패: {e}")
