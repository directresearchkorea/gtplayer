"""
scheduled_publish.py — 예약 발행 + GitHub Pages 배포 + SendGrid 이메일 전송 + SNS 포스팅

사용법:
  py newsletter_manager/execution/scheduled_publish.py web/editions/edition_156.json
  py newsletter_manager/execution/scheduled_publish.py web/editions/edition_156.json --auto
  py newsletter_manager/execution/scheduled_publish.py web/editions/edition_156.json --test

동작:
  1. (--auto 시) 예약 시간(schedule.date, schedule.time) 확인
  2. 에디션 상태를 'published'로 전환하고 정적 사이트(dist/) 빌드 및 GitHub main 브랜치에 push (GitHub Actions 자동 배포 트리거)
  3. 렌더링된 HTML을 SendGrid로 구독자(subscribers.json) 및 관리자(TO_EMAIL)에게 이메일 발송
  4. X, Instagram, LinkedIn 소셜 미디어 자동 포스팅
"""
import os, sys, json, subprocess, datetime, time, urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

BASE_DIR = Path(__file__).parent.parent.parent
EXEC_DIR = Path(__file__).parent
sys.path.insert(0, str(EXEC_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=str(BASE_DIR / '.env'))

from publish_edition import render_newsletter_html

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
GMAIL_USER = os.getenv('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@gtplayer.net')
FROM_NAME = os.getenv('FROM_NAME', 'GTPlayer 뉴스레터')
TO_EMAIL = os.getenv('TO_EMAIL', 'admin@gtplayer.net')
SUBSCRIBERS_PATH = EXEC_DIR / 'subscribers.json'
SUBSCRIBERS_SYNC_URL = os.getenv('SUBSCRIBERS_SYNC_URL', '')


def sync_remote_subscribers():
    """SUBSCRIBERS_SYNC_URL이 설정된 경우 원격(Worker/Apps Script) 구독자 목록을 subscribers.json에 병합."""
    if not SUBSCRIBERS_SYNC_URL:
        return
    try:
        req = urllib.request.Request(SUBSCRIBERS_SYNC_URL, headers={"User-Agent": "GTPlayer-Publisher/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote_data = json.loads(resp.read().decode('utf-8'))
        remote_list = remote_data.get('subscribers', remote_data if isinstance(remote_data, list) else [])
        if not isinstance(remote_list, list):
            return

        local_data = {"subscribers": []}
        if SUBSCRIBERS_PATH.exists():
            with open(SUBSCRIBERS_PATH, 'r', encoding='utf-8') as f:
                local_data = json.load(f)

        by_email = {s.get('email', '').strip().lower(): s for s in local_data.get('subscribers', []) if s.get('email')}
        for r in remote_list:
            em = (r.get('email') or '').strip().lower()
            if not em or '@' not in em:
                continue
            if em in by_email:
                if 'subscribed' in r:
                    by_email[em]['subscribed'] = bool(r['subscribed'])
                if r.get('lang'):
                    by_email[em]['lang'] = r['lang']
            else:
                by_email[em] = {
                    "email": em,
                    "name": r.get("name", ""),
                    "subscribed": bool(r.get("subscribed", True)),
                    "lang": r.get("lang", "ko"),
                    "created_at": r.get("created_at", datetime.datetime.now().isoformat())
                }
        local_data['subscribers'] = list(by_email.values())
        with open(SUBSCRIBERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(local_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 원격 구독자 동기화 건너뜀: {e}")


def load_active_subscribers(lang='ko'):
    """subscribers.json에서 활성 구독자 이메일 목록을 반환."""
    sync_remote_subscribers()
    emails = set()
    if TO_EMAIL and '@' in TO_EMAIL and TO_EMAIL != 'admin@gtplayer.net':
        emails.add(TO_EMAIL.strip())
    if SUBSCRIBERS_PATH.exists():
        try:
            with open(SUBSCRIBERS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for sub in data.get('subscribers', []):
                if sub.get('subscribed', False) and sub.get('lang', 'ko') == lang:
                    email = sub.get('email', '').strip()
                    if email:
                        emails.add(email)
        except Exception as e:
            print(f"  ⚠️ subscribers.json 로드 실패: {e}")
    return sorted(emails)


def render_unsubscribe_footer(lang='ko', email=''):
    """SendGrid 이메일 하단에 수신거부(Unsubscribe) 안내 푸터 추가."""
    import urllib.parse
    enc_email = urllib.parse.quote(email or '')
    unsub_url = f"https://gtplayer-click.gtplayernet.workers.dev?action=unsubscribe&lang={lang}&email={enc_email}"
    i18n = {
        'ko': ('더 이상 뉴스레터를 받고 싶지 않으시면 ', '수신거부(Unsubscribe)', '를 클릭해 주세요.'),
        'en': ('If you no longer wish to receive this newsletter, ', 'Unsubscribe here', '.'),
        'ja': ('ニュースレターの配信停止をご希望の場合は、', 'こちらから配信停止', 'してください。'),
    }
    pre, link_txt, post = i18n.get(lang, i18n['ko'])
    return (
        f'<div style="max-width:640px;margin:0 auto;padding:20px 16px;text-align:center;'
        f'font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;background:#ffffff">'
        f'© 2026 GTPlayer · <a href="https://www.gtplayer.net/" style="color:#6b7280;text-decoration:underline">gtplayer.net</a><br>'
        f'<span style="display:inline-block;margin-top:6px">{pre}'
        f'<a href="{unsub_url}" target="_blank" style="color:#6b7280;text-decoration:underline">{link_txt}</a>{post}</span>'
        f'</div>'
    )


def send_email(subject, html_content, recipients=None, lang='ko'):
    """Gmail SMTP (우선) 또는 SendGrid로 뉴스레터 이메일 발송."""
    if recipients is None:
        recipients = [TO_EMAIL]
    if isinstance(recipients, str):
        recipients = [recipients]

    # 1) Gmail SMTP 발송 (GMAIL_APP_PASSWORD 설정 시)
    if GMAIL_APP_PASSWORD:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formataddr
        from email.header import Header

        sender_addr = GMAIL_USER or FROM_EMAIL
        display_name = {'ko': 'GTPlayer 뉴스레터', 'en': 'GTPlayer Newsletter', 'ja': 'GTPlayer ニュースレター'}.get(lang, FROM_NAME)
        success_count = 0
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as server:
                server.login(sender_addr, GMAIL_APP_PASSWORD)
                for target_email in recipients:
                    unsub_footer = render_unsubscribe_footer(lang, target_email)
                    personalized_html = html_content.replace('</body>', f'{unsub_footer}</body>')
                    msg = MIMEMultipart('alternative')
                    msg['From'] = formataddr((str(Header(display_name, 'utf-8')), sender_addr))
                    msg['To'] = target_email
                    msg['Subject'] = Header(subject, 'utf-8')
                    msg.attach(MIMEText(personalized_html, 'html', 'utf-8'))
                    try:
                        server.sendmail(sender_addr, [target_email], msg.as_string())
                        print(f"  ✅ Gmail 발송 성공 → {target_email}")
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ Gmail 발송 실패 ({target_email}): {e}")
            return success_count > 0
        except Exception as e:
            print(f"  ❌ Gmail SMTP 연결/로그인 실패: {e}")
            if not SENDGRID_API_KEY:
                return False

    # 2) SendGrid 폴백
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sendgrid"])
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

    if not SENDGRID_API_KEY:
        print("  ❌ GMAIL_APP_PASSWORD 및 SENDGRID_API_KEY가 .env에 없습니다")
        return False

    sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
    success_count = 0
    for target_email in recipients:
        unsub_footer = render_unsubscribe_footer(lang, target_email)
        personalized_html = html_content.replace('</body>', f'{unsub_footer}</body>')
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=target_email,
            subject=subject,
            html_content=personalized_html,
        )
        try:
            resp = sg.send(message)
            print(f"  ✅ 이메일 발송 성공 → {target_email} (status: {resp.status_code})")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 이메일 발송 실패 ({target_email}): {e}")
    return success_count > 0


def check_schedule_window(edition):
    """--auto 모드(10분 주기 스케줄러)일 때 예약 시간을 체크하고 즉시 종료 또는 진행 처리.
    장시간 sleep()으로 인해 다중 프로세스가 중첩 실행되는 문제를 방지합니다.
    """
    if edition.get('status') == 'published':
        print("이미 발행(published) 상태인 에디션입니다. 종료합니다.")
        sys.exit(0)

    schedule = edition.get('schedule', {})
    if not schedule.get('date'):
        return

    sched_dt = datetime.datetime.strptime(
        f"{schedule['date']} {schedule.get('time', '07:00')}",
        '%Y-%m-%d %H:%M'
    )
    now = datetime.datetime.now()

    window_end = sched_dt + datetime.timedelta(hours=12)
    if now > window_end:
        print(f"예약 시간이 12시간 이상 경과했습니다 ({sched_dt}). 종료합니다.")
        sys.exit(0)

    if now < sched_dt:
        diff = (sched_dt - now).total_seconds()
        if diff <= 60:
            print(f"⏳ 예약 시간까지 {int(diff)}초 남음 — 잠시 대기 후 발행합니다...")
            time.sleep(diff)
            print("🚀 예약 시간 도달! 발행을 시작합니다.")
        else:
            print(f"⏳ 아직 예약 시간({sched_dt}, 약 {int(diff // 60)}분 남음)이 아닙니다. 다음 스케줄러 주기까지 종료합니다.")
            sys.exit(0)
    else:
        print("🚀 예약 시간 도달! 즉시 발행합니다.")


def build_and_push_github(json_path, num):
    """정적 사이트 빌드 후 GitHub main 브랜치에 커밋 & 푸시."""
    print("═══ Step 1: 정적 사이트(dist/) 빌드 및 GitHub Pages 배포 ═══")
    try:
        subprocess.run(
            [sys.executable, str(EXEC_DIR / 'build_site.py')],
            cwd=BASE_DIR,
            check=True
        )
        print("  ✅ 정적 사이트(dist/) 로컬 빌드 완료")
    except Exception as e:
        print(f"  ⚠️ 정적 사이트 빌드 오류: {e}")

    commit_and_push_editions(f"Publish Edition #{num}")


def commit_and_push_editions(commit_msg):
    """web/editions/ 및 web/assets/ 변경사항을 GitHub main 브랜치에 커밋 & 푸시."""
    git_dir = BASE_DIR / '.git'
    if not git_dir.exists():
        print("  ℹ️ .git 저장소가 아직 초기화되지 않아 git push를 건너뜁니다.")
        return

    try:
        subprocess.run(['git', 'add', 'web/editions/', 'web/assets/'], cwd=BASE_DIR, check=True)
        status_res = subprocess.run(
            ['git', 'status', '--porcelain', 'web/editions/', 'web/assets/'],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        if status_res.stdout.strip():
            subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                cwd=BASE_DIR, check=True
            )
            remote_res = subprocess.run(
                ['git', 'remote'], cwd=BASE_DIR, capture_output=True, text=True
            )
            if 'origin' in remote_res.stdout.split():
                push_res = subprocess.run(
                    ['git', 'push', 'origin', 'main'],
                    cwd=BASE_DIR, capture_output=True, text=True
                )
                if push_res.returncode == 0:
                    print(f"  ✅ GitHub push 완료 ({commit_msg}) → GitHub Pages 자동 배포 시작")
                else:
                    print(f"  ⚠️ GitHub push 실패 (원격 저장소 설정 확인 필요): {push_res.stderr.strip()}")
            else:
                print("  ℹ️ git remote 'origin'이 아직 등록되지 않아 로컬 커밋만 완료했습니다.")
        else:
            print("  ℹ️ 변경된 에디션 파일이 없어 git commit을 건너뜁니다.")
    except Exception as e:
        print(f"  ⚠️ Git 작업 중 오류 발생: {e}")


def main():
    if len(sys.argv) < 2:
        print("사용법: py newsletter_manager/execution/scheduled_publish.py <edition_json> [--auto] [--test]")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        json_path = BASE_DIR / sys.argv[1]
    if not json_path.exists():
        json_path = BASE_DIR / 'web' / 'editions' / sys.argv[1]
    if not json_path.exists():
        print(f"❌ 파일 없음: {sys.argv[1]}")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        edition = json.load(f)

    if '--auto' in sys.argv:
        check_schedule_window(edition)

    schedule = edition.get('schedule', {})
    languages = schedule.get('languages', ['ko', 'en', 'ja'])
    num = edition.get('num', '???')
    date = edition.get('date', '')

    print(f"📄 에디션 #{num} ({date})")
    print(f"🌐 언어: {', '.join(languages)}")
    print()

    is_test = '--test' in sys.argv

    if not is_test:
        # 에디션 상태를 즉시 published로 전환 후 저장 (중복 실행 방지 및 build_site.py 반영)
        edition['status'] = 'published'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(edition, f, ensure_ascii=False, indent=2)

        # Step 1: 정적 사이트 빌드 + GitHub Pages 푸시
        build_and_push_github(json_path, num)

    # Step 2: SendGrid 이메일 발송 및 HTML 백업 저장
    print("\n═══ Step 2: SendGrid 뉴스레터 이메일 발송 ═══")
    tmp_dir = BASE_DIR / '.tmp'
    tmp_dir.mkdir(exist_ok=True)

    for lang in languages:
        lang_code = 'JP' if lang == 'ja' else lang.upper()
        lang_label = {'ko': '한국어', 'en': 'English', 'ja': '日本語 (JP)'}.get(lang, lang)

        html = render_newsletter_html(edition, lang)
        full_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',sans-serif;margin:0;padding:0}}</style></head>
<body><div style="width:100%;margin:0 auto">{html}</div></body></html>'''

        backup = tmp_dir / f'email_{num}_{lang}.html'
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(full_html)

        subjects = edition.get("email_subject", {})
        if lang == 'ko':
            subject = f'#{num}: {subjects.get("ko", f"게임 산업 인사이트 | {date}")}'
        elif lang == 'en':
            subject = f'#{num}: {subjects.get("en", f"Game Intelligence | {date}")}'
        else:
            subject = f'#{num}: {subjects.get("ja", f"Game Intelligence (JP) | {date}")}'

        if is_test:
            recipients = [TO_EMAIL]
            print(f"\n📧 [{lang_code}] {lang_label} 테스트 발송 중 ({len(recipients)}명)...")
            send_email(subject, full_html, recipients=recipients, lang=lang)
        else:
            recipients = load_active_subscribers(lang)
            if recipients:
                print(f"\n📧 [{lang_code}] {lang_label} 구독자 발송 중 ({len(recipients)}명)...")
                send_email(subject, full_html, recipients=recipients, lang=lang)
            else:
                print(f"\nℹ️ [{lang_code}] {lang_label} 활성 구독자가 없어 발송을 건너뜁니다.")

    if is_test:
        print("\n🏁 테스트 이메일 발송 완료! (--test 모드이므로 SNS 포스팅은 건너뜁니다.)")
        return

    # Step 3: 소셜 미디어 자동 발행 (X, Instagram, LinkedIn)
    print("\n═══ Step 3: 소셜 미디어 자동 발행 (X, Instagram, LinkedIn) ═══")
    try:
        sns_exec_dir = BASE_DIR / 'sns_manager' / 'execution'

        # X (Twitter) 발행
        print("👉 X (Twitter) 브라우저 포스팅 시작")
        subprocess.run([sys.executable, str(sns_exec_dir / 'post_to_x_browser.py'), str(json_path)], cwd=BASE_DIR)

        # Instagram 발행
        print("👉 Instagram 포스팅 시작")
        subprocess.run([sys.executable, str(sns_exec_dir / 'post_to_instagram.py'), str(json_path)], cwd=BASE_DIR)

        # 무료 게임 단독 포스팅 추가 (에픽 무료 게임 활성화 시)
        if edition.get('sections', {}).get('epic', {}).get('enabled', False):
            print("👉 Instagram 무료 게임 단독 포스팅 시작")
            subprocess.run([sys.executable, str(sns_exec_dir / 'post_freegames_to_instagram.py'), str(json_path)], cwd=BASE_DIR)

        # LinkedIn 발행
        print("👉 LinkedIn 영어 브라우저 포스팅 시작")
        subprocess.run([sys.executable, str(sns_exec_dir / 'post_to_linkedin_browser.py'), str(json_path)], cwd=BASE_DIR)

    except Exception as e:
        print(f"❌ 소셜 미디어 포스팅 중 오류: {e}")

    # Re-read edition to preserve any SNS post metadata and ensure published status
    try:
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                edition = json.load(f)
    except Exception as e:
        print(f"⚠️ 에디션 재로딩 실패: {e}")

    edition['status'] = 'published'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    # SNS 발행 결과 메타데이터까지 반영하여 커밋
    commit_and_push_editions(f"Update SNS status for Edition #{num}")

    print(f"\n🏁 에디션 #{num} 발행 완료!")


if __name__ == '__main__':
    main()
