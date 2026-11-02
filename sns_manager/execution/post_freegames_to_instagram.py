"""
post_freegames_to_instagram.py — 무료 게임 단독 포스팅

무료 게임 카드 이미지들과 전용 캡션을 인스타그램에 별개의 피드로 업로드합니다.
"""

import os, sys, json, logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
EDITIONS_DIR = BASE_DIR / "web" / "editions"
INSTAGRAM_DIR = BASE_DIR / "web" / "instagram"

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_freegames_to_instagram")

GRAPH_API_URL = "https://graph.instagram.com/v21.0"
SITE_URL = "https://www.gtplayer.net"


# ── 1. 무료 게임 전용 캡션 생성 ────────────────────────────────

def generate_freegames_caption(edition):
    """Gemini로 무료 게임 단독 포스팅용 인스타그램 캡션 생성."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 없습니다.")
        return None

    from google import genai
    client = genai.Client(api_key=api_key)

    num = edition.get("num", "000")
    ep = edition.get("sections", {}).get("epic", {})
    
    # 무료 게임 정보 취합
    game_titles = []
    
    epic_current = ep.get("epic_current", [])
    if not epic_current and ep.get("title"):
        epic_current = [{"title": ep.get("title")}]
        
    for g in epic_current:
        game_titles.append(f"- [Epic Games] {g.get('title', '')}")
        
    sd = ep.get("steam_deal", {})
    if sd:
        discount_str = f" ({sd.get('discount_percent')}% 할인)" if sd.get("discount_percent") else ""
        game_titles.append(f"- [Steam] {sd.get('name', '')}{discount_str}")

    if not game_titles:
        log.warning("배포 중인 무료 게임 정보가 없습니다.")
        return None

    games_list = "\n".join(game_titles)
    url = f"{SITE_URL}/edition-{num}/"

    # 날짜 변환
    try:
        dt = datetime.strptime(edition.get("date", ""), "%Y-%m-%d")
        date_str = f"{dt.month}월 {dt.day}일"
    except:
        date_str = "이번 주"

    prompt = f"""인스타그램 게임 소식 계정(@gtplayer)의 무료 게임 단독 안내 포스트 캡션을 1개 작성해주세요.
이 게시물은 무료 배포 소식을 깔끔하게 전하는 피드입니다.

**대상 날짜**: {date_str}
**무료 게임 목록**:
{games_list}

**캡션 작성 규칙**:
1. 첫 줄: 반드시 "{date_str} 🎁 놓치면 손해인 이번 주 무료 게임 소식!" 또는 이와 유사한 강렬한 문구로 시작.
2. 본문: 이번 주에 풀린 무료 게임들의 라인업을 친절하게 소개하고, 영구 소장 기한을 꼭 챙기라는 점을 이모지와 함께 전달.
3. 빈 줄
4. "👉 옆으로 넘겨서 상세 무료 게임 목록을 확인해 보세요!"
5. "🔗 무료 게임 다운로드 링크는 프로필 링크에서 확인하세요"
6. 빈 줄
7. 인기 해시태그 20개 (예: #무료게임 #스팀무료게임 #에픽게임즈무료게임 #게임뉴스 #스팀게임추천 등)
8. 중요: 절대 글자 주위에 ** 기호(예: **텍스트**)나 * 기호를 붙이지 마세요. 마크다운 기호는 인스타 본문에서 깨져 보이므로 절대로 사용하지 마세요.

캡션만 출력하세요."""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        caption = response.text.strip().strip('"').strip("'")
        # 볼드 기호 강제 제거
        caption = caption.replace("**", "").replace("*", "")
        log.info(f"   ✅ 무료 게임 전용 캡션 생성 완료 ({len(caption)}자)")
        return caption
    except Exception as e:
        log.error(f"   ❌ Gemini 오류: {e}")
        return None


# ── 2. Instagram 포스팅 ───────────────────────────────────────

def post_carousel_to_instagram(image_paths, caption):
    """instagrapi를 사용하여 Carousel 게시물을 포스팅."""
    from instagrapi import Client
    
    session_file = BASE_DIR / ".tmp" / "instagram_session.json"
    if not session_file.exists():
        log.error("❌ instagram_session.json 파일이 없습니다. instagram_login.py를 먼저 실행하세요.")
        return None

    try:
        cl = Client()
        cl.delay_range = [1, 3]
        log.info("   ⏳ 세션 정보를 불러오는 중...")
        cl.load_settings(session_file)
        try:
            cl.login(cl.settings.get("username", ""), "")
        except Exception as e:
            log.warning(f"   세션 검증 경고 (무시 가능): {e}")

        log.info("   🚀 사진을 인스타그램 서버로 업로드 중...")
        
        # PNG → JPG 변환
        jpg_paths = []
        try:
            from PIL import Image
            for p in image_paths:
                p_path = Path(p)
                img = Image.open(p_path)
                jpg_path = p_path.with_suffix(".jpg")
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(jpg_path, "JPEG", quality=100)
                jpg_paths.append(str(jpg_path))
        except Exception as e:
            log.error(f"   ❌ 이미지 JPG 변환 실패: {e}")
            return None

        # Carousel 업로드
        media = cl.album_upload(paths=jpg_paths, caption=caption)
        
        if media:
            post_url = f"https://www.instagram.com/p/{media.code}/"
            log.info(f"   🎉 무료 게임 단독 피드 포스팅 성공! 링크: {post_url}")
            return {"success": True, "id": media.id, "url": post_url, "error": None}
        else:
            err_msg = "알 수 없는 이유로 업로드되지 않았습니다."
            log.error(f"   ❌ 게시 실패: {err_msg}")
            return {"success": False, "id": None, "url": None, "error": err_msg}

    except Exception as e:
        err_msg = f"Instagram 업로드 실패: {e}"
        log.error(f"   ❌ {err_msg}")
        return {"success": False, "id": None, "url": None, "error": err_msg}


# ── 3. 메인 실행부 ───────────────────────────────────────────

def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None


def run(edition_file=None, dry_run=False):
    if edition_file:
        json_path = EDITIONS_DIR / edition_file
        if not json_path.exists():
            json_path = Path(edition_file)
    else:
        json_path = find_latest_edition()

    if not json_path or not json_path.exists():
        log.error(f"에디션 파일 없음: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        edition = json.load(f)

    num = edition.get("num", "000")
    ep = edition.get("sections", {}).get("epic", {})
    if not ep.get("enabled", False):
        log.info("무료 게임(epic) 섹션이 활성화되어 있지 않습니다. 포스팅을 건너뜁니다.")
        return

    log.info(f"📄 에디션 #{num} 무료 게임 단독 포스팅 프로세스 시작")

    # 중복 발행 방지: 이미 성공적으로 무료 게임 단독 피드가 발행된 기록이 있는지 검사
    if not dry_run:
        social_ig = edition.get("social", {}).get("instagram", {})
        results_saved = social_ig.get("freegames_results", {})
        if results_saved.get("success"):
            log.info(f"ℹ️ 에디션 #{num} 무료 게임 피드는 이미 인스타그램에 성공적으로 포스팅되었습니다. (스킵)")
            return results_saved

    card_dir = INSTAGRAM_DIR / f"edition_{num}"
    
    # 카드 파일 검색 (freegame_cover.png, freegame_item_*.png)
    image_paths = []
    cover_path = card_dir / "freegame_cover.png"
    if cover_path.exists():
        image_paths.append(str(cover_path))
        
    items = sorted(card_dir.glob("freegame_item_*.png"))
    for item in items:
        image_paths.append(str(item))

    if not image_paths:
        log.error("❌ 업로드할 무료 게임 카드 이미지가 없습니다. 포스팅을 취소합니다.")
        return

    # 캡션 생성
    caption = generate_freegames_caption(edition)
    if not caption:
        log.error("❌ 캡션 생성 실패. 중단합니다.")
        return

    print(f"\n{'='*50}")
    print(f"[FREE GAMES] 생성된 단독 포스팅 캡션:")
    print(f"{'='*50}")
    print(caption)
    print(f"{'='*50}\n")

    if dry_run:
        log.info("   🏷️ [DRY RUN] 포스팅 건너뜀")
        results = {"posted": False, "error": "Dry run"}
    else:
        log.info("🔄 Instagram에 무료 게임 단독 Carousel 포스팅 중...")
        results = post_carousel_to_instagram(image_paths, caption)

    # 에디션 JSON에 결과 기록
    if "social" not in edition:
        edition["social"] = {}
    if "instagram" not in edition["social"]:
        edition["social"]["instagram"] = {}
        
    edition["social"]["instagram"]["freegames_results"] = results
    edition["social"]["instagram"]["freegames_updated_at"] = datetime.now().isoformat()
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    edition_file = None
    dry_run = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i].endswith(".json"):
            edition_file = args[i]
        elif args[i] == "--dry-run":
            dry_run = True
        i += 1

    run(edition_file=edition_file, dry_run=dry_run)
