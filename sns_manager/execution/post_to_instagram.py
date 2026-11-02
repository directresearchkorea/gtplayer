"""
post_to_instagram.py — Instagram Graph API 자동 포스팅

이미지 카드와 캡션을 생성하여 Instagram 비즈니스 계정에 자동 게시합니다.

사용법:
  py execution/post_to_instagram.py                          # 최신 에디션
  py execution/post_to_instagram.py edition_025.json        # 특정 에디션
  py execution/post_to_instagram.py edition_025.json --dry-run  # 생성만
  py execution/post_to_instagram.py edition_025.json --type calendar  # 특정 카드만

환경변수 (.env):
  INSTAGRAM_ACCESS_TOKEN  — Meta Graph API Long-Lived Access Token
  INSTAGRAM_ACCOUNT_ID    — Instagram Business Account ID

이미지 호스팅:
  Instagram API는 공개 URL의 이미지만 받습니다.
  이미지 파일은 Ghost에 업로드하거나 별도 CDN에 올려야 합니다.
  현재는 Ghost 이미지 업로드 API를 활용합니다.
"""

import os, sys, json, requests, logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
EDITIONS_DIR = BASE_DIR / "web" / "editions"
INSTAGRAM_DIR = BASE_DIR / "web" / "instagram"

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_to_instagram")

GRAPH_API_URL = "https://graph.instagram.com/v21.0"
SITE_URL = "https://www.gtplayer.net"


# ── 1. 캡션 생성 ──────────────────────────────────────────────

def generate_carousel_caption(edition):
    """Gemini로 3장 슬라이드용 통합 인스타그램 캡션 1개 생성."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 없습니다.")
        return None

    from google import genai
    client = genai.Client(api_key=api_key)

    num = edition.get("num", "000")
    subject = edition.get("email_subject", {}).get("ko", "")
    sections = edition.get("sections", {})
    url = f"{SITE_URL}/edition-{num}/"

    # 카드 타입별 일괄 컨텍스트 추출
    items = sections.get("briefing", {}).get("items", [])[:5]
    news = "\n".join([f"- [{item.get('tag','')}] {item.get('title','')}" for item in items])
    
    releases = sections.get("calendar", {}).get("releases", [])[:6]
    games = "\n".join([f"- {r.get('game','')} ({', '.join(r.get('platforms',[]))})" for r in releases])

    drk = sections.get("drk", {})
    insight = f"{drk.get('title','')}\n{drk.get('intro','')[:200]}"
    
    context = f"[뉴스 헤드라인]\n{news}\n\n[출시 게임]\n{games}\n\n[Dr. K 인사이트]\n{insight}"

    # 날짜 포맷 변환 (YYYY-MM-DD -> M월 D일)
    try:
        dt = datetime.strptime(edition.get("date", ""), "%Y-%m-%d")
        date_str = f"{dt.month}월 {dt.day}일"
    except:
        date_str = "오늘"

    prompt = f"""인스타그램 게임 뉴스레터 계정(@gtplayer)의 포스트 캡션을 1개 작성해주세요.
이 게시물은 뉴스, 출시 캘린더, 인사이트 3장이 포함된 슬라이드(Carousel) 형태입니다.

**에디션**: #{num} ({edition.get("date","")})
**주제**: {subject}

**컨텍스트**:
{context}

**웹페이지 링크**: {url}

**캡션 작성 규칙**:
1. 첫 줄: 반드시 "{date_str} 오늘의 게임 소식 🎮" 또는 이와 유사하게 날짜가 포함된 강력한 한 문장으로 시작하세요.
2. 2-4줄: 각 슬라이드(뉴스, 출시작, Dr.K인사이트)의 핵심 요약을 적되, 반드시 다음 포맷과 이모지로 시작하게 고정하세요:
   - 📰 [뉴스] (요약 내용)
   - 📅 [출시] (요약 내용)
   - ✍️ [인사이트] (요약 내용)
3. 빈 줄
4. "👉 옆으로 넘겨서 카드 뉴스를 확인하세요!" 
5. "🔗 전체 뉴스레터 링크는 프로필에서"
6. 빈 줄
7. 해시태그 20개 (인스타 최적화): 인기 게임 해시태그 + 브랜드 태그
   예시: #게임뉴스 #게임덕후 #게임추천 #인디게임 #신작게임 등
8. 중요: 절대 글자 주위에 ** 기호(예: **텍스트**)나 * 기호를 붙이지 마세요. 마크다운 기호는 인스타 본문에서 깨져 보이므로 절대로 사용하지 마세요.

캡션만 출력하세요."""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        caption = response.text.strip().strip('"').strip("'")
        caption = caption.replace("**", "").replace("*", "")
        log.info(f"   ✅ 통합 캡션 생성 완료 ({len(caption)}자)")
        return caption
    except Exception as e:
        log.error(f"   ❌ Gemini 오류: {e}")
        return None


# ── 2. Ghost에 이미지 업로드 (공개 URL 확보) ──────────────────

def upload_image_to_ghost(image_path):
    """이미지를 Ghost에 업로드하고 공개 URL 반환."""
    try:
        from ghost_publish import load_env, create_jwt_token
        load_env()
    except ImportError:
        log.error("ghost_publish 모듈을 찾을 수 없습니다.")
        return None

    api_url = os.getenv("GHOST_API_URL", "").rstrip("/")
    api_key = os.getenv("GHOST_ADMIN_API_KEY", "")

    if not api_url or not api_key:
        log.error("Ghost API 정보가 .env에 없습니다.")
        return None

    token = create_jwt_token(api_key)
    url = f"{api_url}/ghost/api/admin/images/upload/"
    headers = {"Authorization": f"Ghost {token}"}

    p = Path(image_path)
    if not p.exists():
        log.error(f"이미지 파일 없음: {image_path}")
        return None

    try:
        with open(p, "rb") as f:
            files = {"file": (p.name, f, "image/png")}
            resp = requests.post(url, headers=headers, files=files, timeout=30)
        if resp.status_code == 201:
            img_url = resp.json()["images"][0]["url"]
            log.info(f"   📷 Ghost 업로드 완료: {img_url}")
            return img_url
        else:
            log.error(f"   ❌ Ghost 업로드 실패 ({resp.status_code}): {resp.text[:100]}")
            return None
    except Exception as e:
        log.error(f"   ❌ Ghost 업로드 오류: {e}")
        return None


# ── 3. Instagram instagrapi 포스팅 ─────────────────────────────

def post_carousel_to_instagram(image_paths, caption):
    """instagrapi를 사용하여 내장된 봇 클라이언트로 Carousel 게시물을 포스팅."""
    from instagrapi import Client
    
    session_file = BASE_DIR / ".tmp" / "instagram_session.json"
    if not session_file.exists():
        log.error("❌ instagram_session.json 파일이 없습니다. instagram_login.py를 먼저 실행하세요.")
        return None

    try:
        cl = Client()
        cl.delay_range = [1, 3]
        # 인스타그램 qe/expose 404 에러 우회 (해당 엔드포인트가 사라짐)
        cl.expose = lambda *args, **kwargs: None

        log.info("   ⏳ 세션 정보를 불러오는 중...")
        cl.load_settings(session_file)
        # 세션 유효성 검증을 위해 가벼운 로그인 호출 시도 
        # (쿠키가 유효하면 네트워크 요청 없이 바로 통과됨)
        try:
            cl.login(cl.settings.get("username", ""), "")
        except Exception as e:
            # 설정된 세션만으로도 포스팅이 되는 경우가 많아 패스하되 로그만 남김
            log.warning(f"   세션 검증 경고 (무시 가능): {e}")

        log.info("   🚀 사진을 인스타그램 서버로 업로드 중... (시간이 조금 걸릴 수 있습니다)")
        
        # instagrapi는 album 썸네일로 PNG 대신 JPG를 요구하므로 변환 처리
        jpg_paths = []
        try:
            from PIL import Image
            for p in image_paths:
                img = Image.open(p)
                jpg_path = p.replace(".png", ".jpg")
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(jpg_path, "JPEG", quality=100)
                jpg_paths.append(jpg_path)
        except Exception as e:
            log.error(f"   ❌ 이미지 JPG 변환 실패: {e}")
            return None

        # instagrapi의 album_upload는 로컬 파일 경로 리스트를 입력받음
        media = cl.album_upload(paths=jpg_paths, caption=caption)
        
        if media:
            post_url = f"https://www.instagram.com/p/{media.code}/"
            log.info(f"   🎉 인스타 Carousel 포스팅 성공! 링크: {post_url}")
            return {"success": True, "id": media.id, "url": post_url, "error": None}
        else:
            err_msg = "알 수 없는 이유로 업로드되지 않았습니다."
            log.error(f"   ❌ 게시 실패: {err_msg}")
            return {"success": False, "id": None, "url": None, "error": err_msg}

    except Exception as e:
        err_msg = f"Instagram (instagrapi) 업로드 실패: {e}"
        log.error(f"   ❌ {err_msg}")
        import traceback
        traceback.print_exc()
        return {"success": False, "id": None, "url": None, "error": err_msg}


# ── 4. 메인 ─────────────────────────────────────────────────

def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None


def run(edition_file=None, dry_run=False, card_types=None):
    """인스타 포스팅 실행."""
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
    log.info(f"📄 에디션 #{num} 인스타그램 포스팅 프로세스 시작")

    # 중복 발행 방지: 이미 성공적으로 인스타그램에 발행된 기록이 있는지 검사
    if not dry_run:
        social_ig = edition.get("social", {}).get("instagram", {})
        results_saved = social_ig.get("results", {})
        if results_saved.get("carousel", {}).get("posted"):
            log.info(f"ℹ️ 에디션 #{num}은 이미 인스타그램에 성공적으로 포스팅되었습니다. (스킵)")
            return results_saved

    if card_types is None:
        card_types = ["cover", "news", "calendar", "drk"]

    card_dir = INSTAGRAM_DIR / f"edition_{num}"
    
    # 통합 캡션 생성
    log.info("\n🔄 통합 마스터 캡션 생성 중...")
    caption = generate_carousel_caption(edition)
    if not caption:
        log.error("❌ 캡션 생성 실패. 중단합니다.")
        return
        
    print(f"\n{'='*50}")
    print(f"[CAROUSEL] 생성된 캡션:")
    print(f"{'='*50}")
    print(caption)
    print(f"{'='*50}\n")

    if dry_run:
        log.info("   🏷️ [DRY RUN] 포스팅 건너뜀")
        results = {"carousel": {"caption": caption, "posted": False, "error": "Dry run"}}
    else:
        # Ghost 업로드 불필요, 로컬 파일 경로들을 모아서 통째로 넘김
        image_paths = []
        for card_type in card_types:
            card_path = card_dir / f"card_{card_type}.png"
            if not card_path.exists():
                log.warning(f"   ⚠️ 카드 이미지가 없습니다: {card_path}")
                continue
            image_paths.append(str(card_path))

        if not image_paths:
            log.error("❌ 전송할 이미지가 없습니다. 포스팅 취소.")
            return

        # Carousel 포스팅 실행
        log.info("\n🔄 Instagram에 Carousel 포스팅 중...")
        result = post_carousel_to_instagram(image_paths, caption)
        
        posted = result.get("success", False) if result else False
        err_msg = result.get("error") if result else "알 수 없는 오류"
        
        results = {"carousel": {
            "caption": caption,
            "image_paths": image_paths,
            "posted": posted,
            "data": result,
            "error": err_msg
        }}

    # 결과 저장 (에디션 JSON 파일에 직접 기록)
    if "social" not in edition:
        edition["social"] = {}
    if "instagram" not in edition["social"]:
        edition["social"]["instagram"] = {}
        
    edition["social"]["instagram"]["results"] = results
    edition["social"]["instagram"]["updated_at"] = datetime.now().isoformat()
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)
        
    log.info(f"💾 인스타그램 발행 결과 에디션 파일에 저장: {json_path.name}")

    # 레거시 tmp 파일 유지
    tmp_dir = BASE_DIR / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    out_path = tmp_dir / "instagram_posts.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "edition": num,
            "generated_at": datetime.now().isoformat(),
            "results": {k: {kk: vv for kk, vv in v.items() if kk != "data"} for k, v in results.items()},
        }, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    edition_file = None
    dry_run = False
    card_types = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i].endswith(".json"):
            edition_file = args[i]
        elif args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--type" and i + 1 < len(args):
            i += 1
            card_types = [t.strip() for t in args[i].split(",")]
        i += 1

    run(edition_file=edition_file, dry_run=dry_run, card_types=card_types)
