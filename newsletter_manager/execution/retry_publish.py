import os
import sys
import json
import logging
import subprocess
import argparse
from pathlib import Path

# auto_morning_pipeline에서 필요한 함수 가져오기
from auto_morning_pipeline import translate_edition

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
NEWSLETTER_EXEC_DIR = BASE_DIR / 'newsletter_manager' / 'execution'
SNS_EXEC_DIR = BASE_DIR / 'sns_manager' / 'execution'
EDITIONS_DIR = BASE_DIR / 'web' / 'editions'

def main():
    parser = argparse.ArgumentParser(description="에디션의 누락된 번역을 복구하고 Ghost에 다시 발행합니다.")
    parser.add_argument('json_name', help='web/editions 폴더에 있는 에디션 파일 이름 (예: edition_024.json)')
    parser.add_argument('--draft', action='store_true', help='Ghost에 예약/발행 대신 Draft(초안)로만 밀어넣기')
    args = parser.parse_args()

    json_path = EDITIONS_DIR / args.json_name
    if not json_path.exists():
        log.error(f"파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)

    log.info(f"🔄 에디션 복구 작업 시작: {args.json_name}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        edition = json.load(f)

    existing_tr = edition.get('translations', {})
    missing_langs = []
    
    for lang in ['en', 'ja']:
        if not existing_tr.get(lang):
            missing_langs.append(lang)

    if not missing_langs:
        log.info("✅ 모든 언어의 번역이 이미 존재합니다.")
        log.info("재발행(Republish)만 진행하시겠습니까? (새로 번역되지 않음)")
        # 터미널 환경이 아닐 경우 프롬프트 없이 진행하도록 처리하거나, --force 옵션을 두어도 됨
    else:
        log.info(f"⚠️ 누락된 번역 언어 발견: {missing_langs}")
        log.info("번역 재시도 중...")
        
        # translate_edition 실행 (내부적으로 존재하는 언어는 스킵함)
        edition = translate_edition(edition)
        
        # 성공적으로 채워졌는지 다시 확인
        new_missing = []
        for lang in ['en', 'ja']:
            if not edition.get('translations', {}).get(lang):
                new_missing.append(lang)
                
        if new_missing:
            log.error(f"❌ 번역 재시도 후에도 여전히 실패한 언어: {new_missing}")
            sys.exit(1)
            
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(edition, f, ensure_ascii=False, indent=2)
            
        log.info("✅ 번역 복구 및 파일 저장 완료!")

    # 누락되었던 언어들에 대해서만 발송할지, 전체를 발송할지 결정
    # 이미 publish_edition.py 는 기존에 올라간 글이라면 slug가 겹쳐서 새로 올라가거나 수정됨
    # 하지만 ghost_publish.py의 동작상 동일한 slug가 있으면 생성 실패하거나 새 글로 추가될 수 있음.
    # 안전하게 누락되었던 언어 위주로만 발송하거나, 사용자가 의도적으로 덮어씌울 수 있음.
    
    # 쉼표 구분으로 발행 대상 언어 문자열 조립
    langs_to_publish = missing_langs if missing_langs else ['en', 'ja']
    lang_arg = ",".join(langs_to_publish)
    
    cmd_args = [sys.executable, str(NEWSLETTER_EXEC_DIR / 'publish_edition.py'), args.json_name, '--lang', lang_arg]
    
    if args.draft:
        cmd_args.append('--draft')
    else:
        cmd_args.append('--schedule-ghost')

    log.info(f"🚀 Ghost 전송 스크립트 실행 중... 대상 언어: {langs_to_publish}")
    try:
        subprocess.run(cmd_args, cwd=BASE_DIR, check=True)
        log.info("🎉 복구 및 재발행 파이프라인 작동 완료!")
    except subprocess.CalledProcessError as e:
        log.error(f"Ghost 발행 중 오류 발생: {e}")

if __name__ == '__main__':
    main()
