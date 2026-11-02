"""
auto_sns_pipeline.py - SNS 인게이지먼트 자동화 파이프라인

윈도우 작업 스케줄러(Windows Task Scheduler)에 등록하여
X(트위터)와 인스타그램의 좋아요/팔로우 자동화 스크립트를 순차적으로 안전하게 실행합니다.

사용법:
  py sns_manager/execution/auto_sns_pipeline.py
"""

import sys
import subprocess
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("auto_sns_pipeline")

SCRIPT_DIR = Path(__file__).parent
X_SCRIPT = SCRIPT_DIR / "x_browser_automator.py"
INSTA_SCRIPT = SCRIPT_DIR / "instagram_browser_automator.py"

def run_script(script_path, args=[]):
    """지정된 파이썬 스크립트를 서브프로세스로 실행합니다."""
    log.info(f"▶️ 실행 시작: {script_path.name}")
    try:
        # sys.executable 을 사용하여 현재 활성화된 파이썬(가상환경 등) 경로로 실행
        cmd = [sys.executable, str(script_path)] + args
        result = subprocess.run(cmd, check=True)
        log.info(f"✅ 실행 완료: {script_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"❌ 실행 실패 ({script_path.name}): {e}")
        return False
    except Exception as e:
        log.error(f"⚠️ 예상치 못한 오류 발생 ({script_path.name}): {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 SNS 자동화 파이프라인 시작 (X -> Instagram)")
    print("=" * 60)

    # 1. X(트위터) 자동화 실행 (예: 하루 5개 좋아요)
    if X_SCRIPT.exists():
        run_script(X_SCRIPT, ["--max-likes", "5"])
    else:
        log.error(f"스크립트를 찾을 수 없습니다: {X_SCRIPT}")

    print("-" * 60)

    # 2. 인스타그램 자동화 실행 (하루 최대 5개 팔로우/좋아요)
    if INSTA_SCRIPT.exists():
        run_script(INSTA_SCRIPT)
    else:
        log.error(f"스크립트를 찾을 수 없습니다: {INSTA_SCRIPT}")

    print("=" * 60)
    print("🏁 SNS 자동화 파이프라인 종료")
    print("=" * 60)

if __name__ == "__main__":
    main()
