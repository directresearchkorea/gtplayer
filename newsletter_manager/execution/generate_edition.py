"""
generate_edition.py — 뉴스레터 통합 파이프라인 마스터 스크립트
1. 데이터 수집 (collect_news)
2. 분야별 큐레이션 (calendar, briefing, feedback, insight)
3. 에디션 JSON 병합 (web/editions/edition_XXX.json)
"""
import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import argparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
EDITIONS_DIR = SCRIPT_DIR / ".." / ".." / "web" / "editions"
TMP_DIR = SCRIPT_DIR / ".." / ".." / ".tmp"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("generate_edition")

# ---------------------------------------------------------------------------
# Execution Helpers
# ---------------------------------------------------------------------------

def run_script(script_name: str):
    script_path = SCRIPT_DIR / script_name
    log.info(f"▶ [{script_name}] 실행 중...")
    try:
        result = subprocess.run([sys.executable, str(script_path)], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        log.info(f"✅ [{script_name}] 완료")
    except subprocess.CalledProcessError as e:
        log.error(f"❌ [{script_name}] 실패: {e}")
        log.error(e.stderr)

# ---------------------------------------------------------------------------
# JSON Assembly
# ---------------------------------------------------------------------------

def get_next_edition_num() -> str:
    """Determine the next edition number based on existing files."""
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    nums = []
    for f in EDITIONS_DIR.glob("edition_*.json"):
        try:
            num = int(f.stem.split("_")[1])
            nums.append(num)
        except:
            continue
    
    next_num = max(nums or [0]) + 1
    return str(next_num).zfill(3)


def assemble_edition(edition_num: str):
    """Load all tmp outputs and merge into a final edition JSON."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Initialize base structure (matching editor.js makeSample)
    edition = {
        "num": edition_num,
        "date": today,
        "status": "draft",
        "schedule": {
            "date": "",
            "time": "07:00",
            "target": "all",
            "languages": ["ko", "en", "ja"]
        },
        "sections": {
            "calendar": {"enabled": True, "releases": [], "events": []},
            "briefing": {"enabled": True, "items": []},
            "feedback": {"enabled": False, "game": "", "period": "", "count": "0", "sources": "", "score": "0", "pos": 0, "neu": 0, "neg": 0, "keywords": [], "comments": []},
            "drk": {"enabled": True, "title": "", "intro": "", "points": ""},
            "gamescene": {"enabled": False, "game": "", "title": "", "imgUrl": "", "comment": ""},
            "meme": {"enabled": False, "items": []},
            "soundtrack": {"enabled": False, "title": "", "channel": "", "videoId": "", "url": "", "thumbnail": "", "comment": ""},
            "trailer": {"enabled": False, "title": "", "channel": "", "videoId": "", "url": "", "thumbnail": "", "comment": ""},
            "epic": {"enabled": False, "title": "", "url": "", "thumbnail": "", "comment": ""},
            "chart": {"enabled": False, "pc": [], "console": [], "mobile": []},
            "newsletter_feedback": {"enabled": True, "question": "", "upLabel": "", "downLabel": ""}
        },
        "translations": {"en": {}, "ja": {}}
    }

    # 1. Calendar
    cal_file = TMP_DIR / "calendar_output.json"
    if cal_file.exists():
        with open(cal_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            import re
            current_year = int(today.split('-')[0])
            def parse_date(date_str):
                year_match = re.search(r'(\d{4})\s*년', str(date_str))
                if not year_match:
                    year_match = re.search(r'(\d{4})\s*[-./]', str(date_str))
                year = int(year_match.group(1)) if year_match else current_year
                
                m = re.search(r'(\d+)월\s*(\d+)일', str(date_str))
                if m:
                    return (year, int(m.group(1)), int(m.group(2)))
                m2 = re.search(r'(\d+)/(\d+)', str(date_str))
                if m2:
                    return (year, int(m2.group(1)), int(m2.group(2)))
                m3 = re.search(r'(\d+)-(\d+)', str(date_str))
                if m3:
                    return (year, int(m3.group(1)), int(m3.group(2)))
                return (year + 10, 99, 99)

            releases = data.get("calendar_items", [])
            releases.sort(key=lambda x: parse_date(x.get("date", "")))
            edition["sections"]["calendar"]["releases"] = releases
            
            def parse_event_date(date_str):
                m = re.search(r'(\d+)월\s*(\d+)', str(date_str))
                if m:
                    return (int(m.group(1)), int(m.group(2)))
                return (99, 99)
                
            events = data.get("upcoming_events", [])
            events.sort(key=lambda x: parse_event_date(x.get("date", "")))
            edition["sections"]["calendar"]["events"] = events

    # 2. Briefing
    brf_file = TMP_DIR / "briefing_output.json"
    if brf_file.exists():
        with open(brf_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            edition["sections"]["briefing"]["items"] = data.get("briefing_items", [])

    # 3. Feedback (커뮤니티 유저 반응 및 리뷰 분석 — GTcrawling/GTanalysis 연동)
    fdb_file = TMP_DIR / "feedback_output.json"
    if fdb_file.exists():
        with open(fdb_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("items", [])
            if items:
                edition["sections"]["feedback"]["items"] = items
                edition["sections"]["feedback"]["enabled"] = True
                log.info(f"Merged feedback for {len(items)} games")

    # 4. Insight (Dr. K)
    ins_file = TMP_DIR / "insight_output.json"
    if ins_file.exists():
        with open(ins_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            content = data.get("content", {})
            edition["sections"]["drk"].update(content)

    # 5. Scene (오늘의 게임 컨셉 아트 갤러리 — 사용자 요청으로 신규 생성 제외)

    # 6. Meme (단일 밈 구조)
    meme_file = TMP_DIR / "meme_output.json"
    if meme_file.exists():
        with open(meme_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            content = data.get("content", {})
            if content:
                edition["sections"]["meme"].update(content)
                edition["sections"]["meme"]["enabled"] = True
                log.info(f"Merged meme: {content.get('title', '')[:50]}")

    # 7. Soundtrack
    snd_file = TMP_DIR / "soundtrack_output.json"
    if snd_file.exists():
        with open(snd_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            content = data.get("content", {})
            if content:
                edition["sections"]["soundtrack"].update(content)
                edition["sections"]["soundtrack"]["enabled"] = True
                log.info(f"Merged soundtrack: {content.get('title', '')}")

    # 8. Trailer
    trl_file = TMP_DIR / "trailer_output.json"
    if trl_file.exists():
        with open(trl_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            content = data.get("content", {})
            if content:
                edition["sections"]["trailer"].update(content)
                edition["sections"]["trailer"]["enabled"] = True
                log.info(f"Merged trailer: {content.get('title', '')}")

    # 9. Weekend Game Deals (에픽 무료 + 스팀 특가)
    epic_file = TMP_DIR / "epic_output.json"
    if epic_file.exists():
        with open(epic_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("title") or data.get("comment"):
                edition["sections"]["epic"]["title"] = data.get("title", "")
                edition["sections"]["epic"]["url"] = data.get("url", "")
                edition["sections"]["epic"]["thumbnail"] = data.get("thumbnail", "")
                edition["sections"]["epic"]["comment"] = data.get("comment", "")
                edition["sections"]["epic"]["steam_deal"] = data.get("steam_deal")
                edition["sections"]["epic"]["epic_current"] = data.get("epic_current", [])
                edition["sections"]["epic"]["epic_upcoming"] = data.get("epic_upcoming", [])
                edition["sections"]["epic"]["epic_discounted"] = data.get("epic_discounted", [])
                edition["sections"]["epic"]["enabled"] = True
                log.info(f"Merged Weekend Deals: {data.get('title', '')}")

    # 12. Newsletter Email Subject (Hook)
    subj_file = TMP_DIR / "subject_output.json"
    if subj_file.exists():
        with open(subj_file, "r", encoding="utf-8") as f:
            edition["email_subject"] = json.load(f)
            log.info(f"Merged Email Subject: {edition['email_subject'].get('ko')}")

    # Save to editions dir
    output_file = EDITIONS_DIR / f"edition_{edition_num}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)
    
    log.info(f"✨ 최종 에디션 생성 완료: {output_file}")
    return output_file

def main():
    parser = argparse.ArgumentParser(description="GTPlayer Edition Generator")
    parser.add_argument("--target-day", type=int, help="Override target weekday (0=Mon, 4=Fri)")
    parser.add_argument("--tomorrow", action="store_true", help="Generate content for tomorrow's rotation")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("GTPlayer 뉴스레터 자동 생성 파이프라인 시작")
    log.info("=" * 60)

    # 1. Collect & Curate
    pipeline = [
        "collect_news.py",
        "curate_calendar.py",
        "curate_briefing.py",
        "generate_insight.py",
    ]

    for script in pipeline:
        run_script(script)
    
    # 2-1. Daily Media Content (로테이션)
    # 기존 미디어 임시 파일 삭제 (어제 데이터가 병합되는 것 방지)
    media_tmp_files = [
        "meme_output.json",
        "feedback_output.json",
        "scene_output.json",
        "soundtrack_output.json",
        "trailer_output.json",
        "epic_output.json"
    ]
    for m_file in media_tmp_files:
        m_path = TMP_DIR / m_file
        if m_path.exists():
            try:
                m_path.unlink()
            except Exception as e:
                log.warning(f"Failed to delete {m_file}: {e}")

    # Daily rotation logic for Media Sections
    # 월(0): 밈, 화(1): 보조 코너 생략(핵심 3대 섹션 집중), 수(2): BGM, 목(3): 트레일러, 금(4): 에픽무료
    media_scripts = [
        "fetch_meme.py",         # 월 (0)
        None,                    # 화 (1) — 보조 미디어 코너 생략 (캘린더 + 브리핑 + Dr. K 집중)
        "fetch_soundtrack.py",   # 수 (2)
        "fetch_trailer.py",      # 목 (3)
        "fetch_epic.py"          # 금 (4)
    ]
    
    weekday = datetime.now().weekday()
    if args.target_day is not None:
        weekday = args.target_day
    elif args.tomorrow:
        weekday = (weekday + 1) % 7
        
    target_media_script = media_scripts[weekday % 5]
    
    if target_media_script:
        log.info(f"📅 오늘의 요일 인덱스: {weekday} -> 실행할 미디어: {target_media_script}")
        run_script(target_media_script)
    else:
        log.info(f"📅 오늘의 요일 인덱스: {weekday} -> 보조 미디어 코너 생략 (핵심 섹션만 발행)")

    # 뉴스레터 제목(Subject) 생성은 미디어 파일들(.tmp/*_output.json)이 다 모인 직후에 실행
    run_script("generate_subject.py")

    # 3. Assemble
    num = str(get_next_edition_num())
    output_path = assemble_edition(num)

    print(f"\n✅ 파이프라인 정상 종료")
    print(f"   에디션: #{num}")
    print(f"   위치: {output_path}")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    main()
