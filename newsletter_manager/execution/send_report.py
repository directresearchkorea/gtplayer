import os
import sys
import json
import urllib.request
import urllib.error
import datetime
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

def get_sendgrid_stats(api_key):
    url = "https://api.sendgrid.com/v3/messages?limit=15"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })
    stats = {"opens": 0, "clicks": 0, "delivered": 0, "status": "알 수 없음"}
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            messages = data.get("messages", [])
            if messages:
                for m in messages:
                    subj = m.get("subject", "")
                    if "GTPlayer" in subj or "게임 산업 인사이트" in subj or "#" in subj:
                        stats["status"] = m.get("status", "알 수 없음")
                        stats["opens"] = m.get("opens_count", 0)
                        stats["clicks"] = m.get("clicks_count", 0)
                        stats["delivered"] = 1 if stats["status"] == "delivered" else 0
                        break
    except Exception as e:
        print(f"SendGrid API Error: {e}")
    return stats

def parse_latest_edition():
    nums = []
    for f in EDITIONS_DIR.glob("edition_*.json"):
        try:
            nums.append(int(f.stem.split('_')[1]))
        except:
            pass
    if not nums:
        return None
    latest_num = max(nums)
    latest_file = EDITIONS_DIR / f"edition_{latest_num:03d}.json"
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def send_email_report(api_key, to_email, from_email, subject, html_content):
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    gmail_user = os.getenv("GMAIL_USER", "") or from_email
    if gmail_password:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formataddr
        from email.header import Header
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = formataddr((str(Header("GTPlayer Admin", 'utf-8')), gmail_user))
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as server:
                server.login(gmail_user, gmail_password)
                server.sendmail(gmail_user, [to_email], msg.as_string())
            print("보고서 이메일 전송 성공 (Gmail SMTP)!")
            return True
        except Exception as e:
            print(f"Gmail 보고서 전송 실패: {e}")

    if not api_key:
        return False

    url = "https://api.sendgrid.com/v3/mail/send"
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": "GTPlayer Admin"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 202):
                print("보고서 이메일 전송 성공!")
                return True
    except urllib.error.HTTPError as e:
        print(f"이메일 전송 실패: {e.read().decode()}")
    return False

def main():
    load_env()
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
    admin_email = os.getenv("REPORT_ADMIN_EMAIL", os.getenv("TO_EMAIL", "admin@gtplayer.net"))
    sender_email = os.getenv("SENDGRID_SENDER_EMAIL", os.getenv("FROM_EMAIL", "noreply@gtplayer.net"))

    print("📊 발송 현황 보고서 수집 중...")
    
    # 1. 최신 에디션 정보
    edition = parse_latest_edition()
    edition_num = edition.get("num", "알수없음") if edition else "알수없음"
    date_str = edition.get("date", datetime.datetime.now().strftime("%Y-%m-%d")) if edition else ""
    
    # 컨텐츠 요약 추출
    contents = []
    if edition and "sections" in edition:
        sec = edition["sections"]
        if "briefing" in sec and sec["briefing"].get("items"):
            contents.append(f"📰 브리핑 {len(sec['briefing']['items'])}건")
        if "calendar" in sec and sec["calendar"].get("releases"):
            contents.append(f"📅 신작 일정 {len(sec['calendar']['releases'])}건")
        if "feedback" in sec and sec["feedback"].get("enabled"):
            fb_count = len(sec["feedback"].get("items", [])) or 1
            contents.append(f"💬 유저 반응 분석 {fb_count}개 게임")
        if "meme" in sec and sec["meme"].get("title"):
            contents.append(f"🔥 화제의 밈: {sec['meme']['title']}")
        if "trailer" in sec and sec["trailer"].get("title"):
            contents.append(f"🎬 트레일러: {sec['trailer']['title']}")
    
    content_str = "<ul>" + "".join([f"<li>{c}</li>" for c in contents]) + "</ul>" if contents else "정보 없음"

    # 2. 구독자 수 및 증감 (subscribers.json 기준)
    current_members = get_local_members_count()
    
    stats_file = TMP_DIR / 'stats.json'
    prev_members = current_members
    if stats_file.exists():
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                prev_members = stats.get('members', current_members)
        except:
            pass

    diff = current_members - prev_members
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    
    TMP_DIR.mkdir(exist_ok=True)
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump({"members": current_members, "last_updated": datetime.datetime.now().isoformat()}, f)

    # 3. SendGrid 성과 (가장 최근 메일)
    sg_stats = get_sendgrid_stats(sendgrid_key)
    
    # 보고서 HTML 구성
    subject = f"[GTPlayer] 에디션 #{edition_num} 발송 현황 보고서"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #000; color: #fff; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">GTPlayer 발송 현황 보고서</h2>
            <p style="margin: 5px 0 0 0; color: #aaa;">에디션 #{edition_num} ({date_str})</p>
        </div>
        <div style="padding: 20px;">
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px;">✅ 발송 상태</h3>
            <p><strong>최근 메시지 상태:</strong> {sg_stats['status']}</p>
            
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px;">📈 성과 데이터</h3>
            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                <tr><td style="padding: 8px 0;"><strong>총 구독자 수</strong></td><td>{current_members} 명 ({diff_str})</td></tr>
                <tr><td style="padding: 8px 0;"><strong>이메일 오픈</strong></td><td>{sg_stats['opens']} 회</td></tr>
                <tr><td style="padding: 8px 0;"><strong>링크 클릭</strong></td><td>{sg_stats['clicks']} 회</td></tr>
            </table>
            
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px;">📝 다룬 컨텐츠</h3>
            {content_str}
        </div>
        <div style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #888;">
            이 메일은 자동 생성된 관리자용 보고서입니다.
        </div>
    </div>
    """

    print("📧 이메일 발송 중...")
    send_email_report(sendgrid_key, admin_email, sender_email, subject, html)

if __name__ == "__main__":
    main()
