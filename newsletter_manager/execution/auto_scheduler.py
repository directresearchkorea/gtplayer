"""
auto_scheduler.py — 예약된 에디션을 자동 발행 (scheduled_publish.py 위임 래퍼)

Windows Task Scheduler에서 실행 시 auto_publish_scheduler.py와 동일하게
scheduled_publish.py --auto 를 호출하여 GitHub Pages 빌드/배포 + SendGrid 이메일 + SNS 발행을 수행합니다.
"""
import sys, subprocess
from pathlib import Path

if __name__ == '__main__':
    target = Path(__file__).parent / 'auto_publish_scheduler.py'
    sys.exit(subprocess.call([sys.executable, str(target)]))
