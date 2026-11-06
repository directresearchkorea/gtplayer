"""
post_to_x.py — 에디션 발행 후 X(Twitter) 자동 포스팅

에디션 JSON을 읽어 Gemini로 SEO 최적화된 hook 트윗을 생성하고,
해당 에디션의 웹페이지 링크를 포함하여 X에 자동 게시합니다.

사용법:
  py execution/post_to_x.py                          # 최신 에디션
  py execution/post_to_x.py edition_025.json          # 특정 에디션
  py execution/post_to_x.py edition_025.json --dry-run # 생성만 (포스팅 안 함)
  py execution/post_to_x.py edition_025.json --lang ko # 특정 언어만

환경변수 (.env):
  GEMINI_API_KEY       — Gemini API 키
  X_API_KEY            — X API Key (OAuth 1.0a)
  X_API_SECRET         — X API Secret
  X_ACCESS_TOKEN       — X Access Token
  X_ACCESS_TOKEN_SECRET — X Access Token Secret
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
EDITIONS_DIR = BASE_DIR / "web" / "editions"

load_dotenv(dotenv_path=str(BASE_DIR / ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_to_x")

SITE_URL = "https://www.gtplayer.net"


# ── 1. 에디션에서 컨텍스트 추출 ──────────────────────────────
def extract_context(edition):
    """에디션 JSON에서 포스트 생성에 필요한 핵심 정보를 추출."""
    sections = edition.get("sections", {})
    ctx = {
        "num": edition.get("num", "???"),
        "date": edition.get("date", ""),
        "subject_ko": edition.get("email_subject", {}).get("ko", ""),
        "subject_en": edition.get("email_subject", {}).get("en", ""),
        "subject_ja": edition.get("email_subject", {}).get("ja", ""),
    }

    # 캘린더 - 오늘 출시 게임 목록
    cal = sections.get("calendar", {})
    if cal.get("enabled"):
        games = [
            f"{r['game']} ({', '.join(r.get('platforms', []))})"
            for r in cal.get("releases", [])[:5]
        ]
        ctx["releases"] = games
        ctx["events"] = [e["name"] for e in cal.get("events", [])[:3]]

    # 브리핑 - 뉴스 헤드라인
    briefing = sections.get("briefing", {})
    if briefing.get("enabled"):
        ctx["headlines"] = [
            item["title"] for item in briefing.get("items", [])[:5]
        ]

    # Dr. K 인사이트
    drk = sections.get("drk", {})
    if drk.get("enabled"):
        ctx["drk_title"] = drk.get("title", "")
        ctx["drk_intro"] = drk.get("intro", "")[:200]

    # 유저 피드백 게임명
    fb = sections.get("feedback", {})
    if fb.get("enabled"):
        items = fb.get("items", [fb])
        ctx["feedback_games"] = [item.get("game", "") for item in items if item.get("game")]

    return ctx


def build_post_url(num, lang="ko"):
    """에디션 웹페이지 URL 생성."""
    if lang == "ko":
        return f"{SITE_URL}/edition-{num}/"
    else:
        return f"{SITE_URL}/edition-{num}-{lang}/"


# ── 2. Gemini로 트윗 생성 ────────────────────────────────────
def generate_tweet(ctx, lang="ko"):
    """Gemini API를 호출하여 SEO 최적화 hook 트윗 생성."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY가 .env에 없습니다.")
        return None

    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2] / 'newsletter_manager' / 'execution'))
    from llm_client import genai
    client = genai.Client(api_key=api_key)

    post_url = build_post_url(ctx["num"], lang)

    prompt_map = {
        "ko": f"""아래 게임 뉴스레터 에디션 정보를 바탕으로 X(트위터) 포스트를 작성해주세요.

**규칙:**
1. 총 길이: URL과 해시태그를 제외한 본문 길이를 반드시 **한국어 90자 이내**로 매우 짧게 요약! (트위터 글자수 초과 방지)
2. 말투: X(트위터) 유저들이 좋아하는 친근하고 편안한 대화체 (예: ~네요!, ~인 거 아시나요?, ~해볼까요? 등)
3. 첫 줄: 시선을 확 끄는 흥미로운 한 문장 훅
4. 2번째 줄: 복잡한 사실 나열은 피하고, 가장 핵심적인 뉴스 1개만 골라서 한 문장으로 임팩트 있게 요약
5. 마지막 줄: URL (아래 URL을 그대로 사용)
6. 해시태그 2~3개 (가장 핫한 게임 이름 1개 + #게임소식 + #GTPlayer)
7. 이모지는 너무 과하지 않게 자연스러운 위치에 2~3개만 사용
8. 딱딱한 뉴스 봇 느낌은 절대 금지. 실제 게이머가 흥미로운 소식을 공유하는 듯한 느낌으로 작성.

**에디션 정보:**
- 에디션: #{ctx['num']} ({ctx['date']})
- 제목: {ctx.get('subject_ko', '')}
- 오늘 출시 게임: {', '.join(ctx.get('releases', ['없음']))}
- 뉴스 헤드라인: {'; '.join(ctx.get('headlines', ['없음']))}
- Dr. K 인사이트: {ctx.get('drk_title', '없음')}

**URL:** {post_url}

트윗 텍스트만 출력하세요. 따옴표나 설명 없이.""",

        "en": f"""Write an X (Twitter) post based on this gaming newsletter edition.

**Rules:**
1. Total length: under 250 chars including URL
2. First line: a compelling hook that stops the scroll
3. 2-3 lines: summarize today's key content (use specific game names/numbers)
4. Last line: URL (use the exact URL below)
5. 2-3 hashtags (gaming-related + #GTPlayer)
6. Use 2-3 emojis naturally
7. Include SEO keywords naturally: "game release", "gaming news", etc.
8. Informative tone, NOT promotional.

**Edition info:**
- Edition: #{ctx['num']} ({ctx['date']})
- Subject: {ctx.get('subject_en', '')}
- Today's releases: {', '.join(ctx.get('releases', ['None']))}
- Headlines: {'; '.join(ctx.get('headlines', ['None']))}
- Dr. K Insight: {ctx.get('drk_title', 'None')}

**URL:** {post_url}

Output ONLY the tweet text. No quotes or explanations.""",

        "ja": f"""以下のゲームニュースレターの情報をもとに、X（Twitter）のポストを作成してください。

**ルール:**
1. URL込みで250文字以内
2. 1行目：スクロールを止める強力なフック
3. 2〜3行：本日のハイライト要約（具体的なゲーム名・数字を入れる）
4. 最後の行：URL（以下のURLをそのまま使用）
5. ハッシュタグ2〜3個（ゲーム関連 + #GTPlayer）
6. 絵文字2〜3個を自然に使用
7. SEOキーワード：「ゲーム発売」「ゲームニュース」など自然に含める
8. 情報提供のトーン。宣伝的にしない。

**エディション情報:**
- エディション: #{ctx['num']} ({ctx['date']})
- タイトル: {ctx.get('subject_ja', '')}
- 本日のリリース: {', '.join(ctx.get('releases', ['なし']))}
- ヘッドライン: {'; '.join(ctx.get('headlines', ['なし']))}
- Dr. Kインサイト: {ctx.get('drk_title', 'なし')}

**URL:** {post_url}

ツイートのテキストのみ出力してください。引用符や説明は不要です。""",
    }

    prompt = prompt_map.get(lang, prompt_map["ko"])

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        tweet = response.text.strip()
        # 따옴표 제거
        tweet = tweet.strip('"').strip("'").strip("`")
        log.info(f"   ✅ [{lang.upper()}] 트윗 생성 완료 ({len(tweet)}자)")
        return tweet
    except Exception as e:
        log.error(f"   ❌ [{lang.upper()}] Gemini 오류: {e}")
        return None


# ── 3. X API로 포스팅 ──────────────────────────────────────
def post_tweet(text):
    """X API v2를 사용하여 트윗 포스팅."""
    try:
        import requests
        from requests_oauthlib import OAuth1
    except ImportError:
        print("❌ 오류: 'requests-oauthlib' 라이브러리가 설치되지 않았습니다. 'py -m pip install requests-oauthlib' 명령어로 설치해주세요.")
        return None

    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("❌ 오류: .env 파일에 X API 키 4개가 모두 설정되지 않았습니다.")
        return None

    auth = OAuth1(api_key, api_secret, access_token, access_secret)

    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}

    try:
        resp = requests.post(url, json=payload, auth=auth, timeout=30)
        if resp.status_code == 201:
            data = resp.json()
            tweet_id = data["data"]["id"]
            print(f"✅ 포스팅 성공! https://x.com/i/status/{tweet_id}")
            return {"success": True, "data": data, "error": None}
        else:
            err_msg = f"X API 오류 ({resp.status_code}): {resp.text}"
            print(f"❌ {err_msg}")
            return {"success": False, "data": None, "error": err_msg}
    except Exception as e:
        err_msg = f"X API 요청 중 예외 발생: {e}"
        print(f"❌ {err_msg}")
        import traceback
        traceback.print_exc()
        return {"success": False, "data": None, "error": err_msg}


# ── 4. 메인 ────────────────────────────────────────────────
def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None


def run(edition_file=None, dry_run=False, langs=None):
    """메인 실행 함수."""
    if edition_file:
        json_path = EDITIONS_DIR / edition_file
        if not json_path.exists():
            json_path = Path(edition_file)
    else:
        json_path = find_latest_edition()

    if not json_path or not json_path.exists():
        log.error(f"에디션 파일을 찾을 수 없습니다: {json_path}")
        return

    log.info(f"📄 에디션 로드: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as f:
        edition = json.load(f)

    ctx = extract_context(edition)
    log.info(f"   #{ctx['num']} | 출시 {len(ctx.get('releases', []))}건 | 헤드라인 {len(ctx.get('headlines', []))}건")

    if langs is None:
        langs = ["ko"]

    results = {}
    for lang in langs:
        log.info(f"\n🔄 [{lang.upper()}] 트윗 생성 중...")
        tweet = generate_tweet(ctx, lang)
        if not tweet:
            continue

        # URL이 포함되어 있는지 확인
        expected_url = build_post_url(ctx["num"], lang)
        if expected_url not in tweet:
            tweet = tweet.rstrip() + f"\n{expected_url}"

        print(f"\n{'='*50}")
        print(f"[{lang.upper()}] 생성된 트윗 ({len(tweet)}자):")
        print(f"{'='*50}")
        print(tweet)
        print(f"{'='*50}\n")

        if dry_run:
            log.info(f"   🏷️ [DRY RUN] 포스팅 건너뜀")
            results[lang] = {"tweet": tweet, "posted": False, "error": "Dry run"}
        else:
            result = post_tweet(tweet)
            posted = result.get("success", False) if result else False
            err_msg = result.get("error") if result else "알 수 없는 오류"
            results[lang] = {"tweet": tweet, "posted": posted, "data": result.get("data") if result else None, "error": err_msg}

    # 결과 저장 (에디션 JSON 파일에 직접 기록)
    if "social" not in edition:
        edition["social"] = {}
    if "x" not in edition["social"]:
        edition["social"]["x"] = {}
        
    edition["social"]["x"]["results"] = results
    edition["social"]["x"]["updated_at"] = datetime.now().isoformat()
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(edition, f, ensure_ascii=False, indent=2)
        
    log.info(f"💾 X 발행 결과 에디션 파일에 저장: {json_path.name}")
    
    # 레거시 tmp 파일도 유지 (호환성 목적)
    output = {
        "edition": ctx["num"],
        "date": ctx["date"],
        "generated_at": datetime.now().isoformat(),
        "results": results,
    }
    tmp_dir = BASE_DIR / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    out_path = tmp_dir / "x_posts.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    edition_file = None
    dry_run = False
    langs = ["ko"]

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i].endswith(".json"):
            edition_file = args[i]
        elif args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--lang" and i + 1 < len(args):
            i += 1
            langs = [l.strip() for l in args[i].split(",")]
        i += 1

    run(edition_file=edition_file, dry_run=dry_run, langs=langs)
