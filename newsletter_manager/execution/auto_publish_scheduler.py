"""auto_publish_scheduler.py — 주기적으로 예약된 에디션을 찾아 자동 발행합니다.
이 스크립트를 Windows 작업 스케줄러에 10분 간격으로 등록해두면 완벽히 자동화됩니다.
"""
import os, sys, json, time, subprocess
from pathlib import Path

WEB_DIR = Path(__file__).parent.parent.parent / 'web' / 'editions'
EXEC_DIR = Path(__file__).parent

def main():
    if not WEB_DIR.exists():
        return
    
    print(f"🔍 예약 대기 중인 에디션 탐색 중... ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # 최근 생성된 에디션 5개를 가져오되, 순서대로 올리기 위해 시간 순(오름차순)으로 정렬하여 스캔
    latest_files = sorted(WEB_DIR.glob('edition_*.json'), reverse=True)[:5]
    for json_file in sorted(latest_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 발송 대기 중인(scheduled) 상태만 타겟 (draft는 발행하지 않음)
            if data.get('status') == 'scheduled' and data.get('schedule', {}).get('date'):
                num = data.get('num', '???')
                print(f"▶ 에디션 {num} ({json_file.name}) 예약 확인. 발행 시도...")
                
                # --auto 플래그를 주어 예약시간에 도달했을 때만 발행되도록 함
                cmd = [sys.executable, str(EXEC_DIR / 'scheduled_publish.py'), str(json_file), '--auto']
                
                # 실행 (아직 시간이 안 된 경우 sys.exit(0) 처리되어 스킵됨)
                subprocess.run(cmd)
        except Exception as e:
            print(f"❌ {json_file.name} 처리 중 오류: {e}")

if __name__ == '__main__':
    main()
