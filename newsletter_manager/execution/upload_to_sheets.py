"""
CSV 데이터를 구글 시트에 업로드하는 스크립트
============================================
.tmp/youtube_micro_influencers_KR.csv 파일을 읽어
새로운 구글 스프레드시트를 생성하고 데이터를 업로드합니다.

사용법:
    py execution/upload_to_sheets.py
"""

import os
import sys
import csv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# === 설정 ===
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]
CLIENT_SECRETS_FILE = "credentials.json"
TOKEN_FILE = "sheets_token.json"  # 시트용 별도 토큰
CSV_FILE = os.path.join(".tmp", "youtube_micro_influencers_KR.csv")
SHEET_TITLE = "YouTube 게임 마이크로 인플루언서 (한국)"


def get_credentials():
    """Google Sheets API 인증"""
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
    return creds


def main():
    print("📤 구글 시트 업로드를 시작합니다...\n")

    # CSV 파일 읽기
    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV 파일이 없습니다: {CSV_FILE}")
        sys.exit(1)

    rows = []
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    print(f"📄 CSV 로드 완료: {len(rows)-1}개 채널 데이터")

    # 인증
    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)
    print("✅ Google Sheets API 인증 성공")

    # 새 스프레드시트 생성
    spreadsheet = sheets_service.spreadsheets().create(
        body={
            "properties": {"title": SHEET_TITLE},
            "sheets": [{
                "properties": {
                    "title": "한국 (KR)",
                    "gridProperties": {"frozenRowCount": 1}
                }
            }]
        }
    ).execute()

    spreadsheet_id = spreadsheet["spreadsheetId"]
    sheet_url = spreadsheet["spreadsheetUrl"]
    print(f"📊 스프레드시트 생성 완료!")

    # 데이터 업로드
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="한국 (KR)!A1",
        valueInputOption="RAW",
        body={"values": rows}
    ).execute()

    print(f"✅ {len(rows)-1}개 채널 데이터 업로드 완료!")

    # 헤더 서식 (굵게 + 배경색)
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            {
                "repeatCell": {
                    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "autoResizeDimensions": {
                    "dimensions": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 9}
                }
            }
        ]}
    ).execute()

    print(f"\n{'='*50}")
    print(f"🔗 시트 링크: {sheet_url}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
