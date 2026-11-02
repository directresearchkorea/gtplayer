import os
import sys
import json
import urllib.request
import urllib.error
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
TMP_DIR = BASE_DIR / '.tmp'
EDITIONS_DIR = BASE_DIR / 'web' / 'editions'
SUBSCRIBERS_PATH = Path(__file__).parent / 'subscribers.json'

try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv", "--quiet"])
    from dotenv import load_dotenv

def load_env():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

def get_local_members_count():
    if not SUBSCRIBERS_PATH.exists():
        return 0
    try:
        with open(SUBSCRIBERS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return sum(1 for s in data.get("subscribers", []) if s.get("subscribed", False))
    except Exception as e:
        print(f"Subscribers read error: {e}")
        return 0

def get_sendgrid_weekly_stats(api_key):
    stats = {
        "posts": 0,
        "email_count": {"ko": 0, "en": 0, "ja": 0},
        "opened_count": {"ko": 0, "en": 0, "ja": 0}
    }
    if not api_key:
        return stats
    url = "https://api.sendgrid.com/v3/messages?limit=50"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            for m in data.get("messages", []):
                subj = m.get("subject", "")
                if "#" in subj or "GTPlayer" in subj:
                    if "(JP)" in subj or any('\u3040' <= ch <= '\u30ff' for ch in subj):
                        lang = "ja"
                    elif any('\uac00' <= ch <= '\ud7a3' for ch in subj):
                        lang = "ko"
                    else:
                        lang = "en"
                    stats["posts"] += 1
                    stats["email_count"][lang] += 1
                    stats["opened_count"][lang] += int(m.get("opens_count", 0))
    except Exception as e:
        print(f"SendGrid Stats API Info: {e}")
    return stats

def get_weekly_editions(days=7):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    weekly_data = []
    
    for f in EDITIONS_DIR.glob("edition_*.json"):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                date_str = data.get("date")
                if date_str:
                    ed_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    if ed_date >= cutoff:
                        weekly_data.append((ed_date, data))
        except Exception:
            pass
            
    weekly_data.sort(key=lambda x: x[0])
    return [d[1] for d in weekly_data]

def main():
    load_env()
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
    admin_email = os.getenv("TO_EMAIL", "admin@gtplayer.net")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    sender_email = admin_email

    print("📊 주간 발송 현황 보고서 수집 중...")
    
    # 1. 주간 에디션 취합 (최근 7일)
    editions = get_weekly_editions(days=7)
    editions_html = ""
    
    for ed in editions:
        num = ed.get("num", "")
        date_str = ed.get("date", "")
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            weekday = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
        except Exception:
            weekday = "?"
            
        x_status = "대기/없음"
        insta_status = "대기/없음"
        social = ed.get("social", {})
        
        if "x" in social:
            posted = social["x"].get("results", {}).get("ko", {}).get("posted", False)
            err = social["x"].get("results", {}).get("ko", {}).get("error")
            x_status = "성공" if posted else (f"실패 ({err})" if err else "실패")
        else:
            try:
                x_file = TMP_DIR / "x_posts.json"
                if x_file.exists():
                    x_data = json.loads(x_file.read_text(encoding="utf-8"))
                    if x_data.get("edition") == num:
                        res_ko = x_data.get("results", {}).get("ko", {})
                        x_status = "성공" if res_ko.get("posted") else "실패"
            except Exception:
                pass
            
        if "instagram" in social:
            posted = social["instagram"].get("results", {}).get("carousel", {}).get("posted", False)
            err = social["instagram"].get("results", {}).get("carousel", {}).get("error")
            insta_status = "성공" if posted else (f"실패 ({err})" if err else "실패")
        else:
            try:
                in_file = TMP_DIR / "instagram_posts.json"
                if in_file.exists():
                    in_data = json.loads(in_file.read_text(encoding="utf-8"))
                    if in_data.get("edition") == num:
                        res_car = in_data.get("results", {}).get("carousel", {})
                        insta_status = "성공" if res_car.get("posted") else "실패"
            except Exception:
                pass
            
        editions_html += f"- Edition #{num} ({date_str} {weekday}요일) [X: {x_status}] [Insta: {insta_status}]\n"

    # 2. 이메일 통계 (SendGrid 기준)
    print("📈 이메일 발송 통계 수집 중...")
    email_stats = get_sendgrid_weekly_stats(sendgrid_key)
    
    # 3. 구독자 수 및 주간 증감 (subscribers.json 기준)
    current_members = get_local_members_count()
    stats_file = TMP_DIR / 'weekly_stats.json'
    prev_members = current_members
    
    if stats_file.exists():
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                prev_members = stats.get('members', current_members)
        except Exception:
            pass

    diff = current_members - prev_members
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    
    TMP_DIR.mkdir(exist_ok=True)
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump({"members": current_members, "last_updated": datetime.datetime.now().isoformat()}, f)
    
    total_email_count = sum(email_stats['email_count'].values())
    total_opened_count = sum(email_stats['opened_count'].values())
    open_rate = round((total_opened_count / total_email_count) * 100, 1) if total_email_count > 0 else 0

    subject = f"[GTPlayer] 주간 통계 보고서 (총 {len(editions)}건 발행)"
    text_content = f"""GTPlayer 주간 발송 현황 보고서
=======================================
지난 1주일 간의 에디션 성과 요약 (GitHub Pages + SendGrid)

📈 주간 종합 통계
---------------------------------------
- 총 발행 에디션 수 : {len(editions)} 건
- 현재 총 구독자 수 : {current_members} 명 (주간 증감: {diff_str})

📧 주간 이메일 발송 통계
---------------------------------------
- 전체 발송 수 : 총 {total_email_count} 통
  * 한국어(KO) : {email_stats['email_count']['ko']} 통
  * 영어(EN)   : {email_stats['email_count']['en']} 통
  * 일본어(JA) : {email_stats['email_count']['ja']} 통

- 전체 오픈 수 : 총 {total_opened_count} 회 (평균 오픈율: {open_rate}%)
  * 한국어(KO) : {email_stats['opened_count']['ko']} 회
  * 영어(EN)   : {email_stats['opened_count']['en']} 회
  * 일본어(JA) : {email_stats['opened_count']['ja']} 회

📅 주간 발행 에디션 목록 및 소셜 미디어 배포 결과
---------------------------------------
{editions_html}
이 메일은 자동 생성된 주간 보고서입니다.
"""

    print("📧 Gmail SMTP를 통해 이메일 발송 중...")
    if not gmail_password:
        print("❌ 오류: .env 파일에 GMAIL_APP_PASSWORD가 설정되지 않았습니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = f"GTPlayer Admin <{sender_email}>"
    msg['To'] = admin_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, gmail_password)
        server.send_message(msg)
        server.quit()
        print("주간 보고서 이메일 전송 성공!")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    main()
