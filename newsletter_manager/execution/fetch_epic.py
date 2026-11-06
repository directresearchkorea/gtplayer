"""
fetch_weekend_deals.py — 금요일 섹션: 주말 게임 혜택
에픽게임즈 무료 배포(필수) + 스팀 주말 무료/특가(선택)를 수집하고
Gemini로 뉴스레터용 코멘트를 생성합니다.
"""
import os
import sys
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 한국 시간대 (KST) 정의
KST = timezone(timedelta(hours=9))

from dotenv import load_dotenv
from llm_client import genai

SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".." / ".." / ".env"
load_dotenv(str(ENV_PATH))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_PATH = SCRIPT_DIR / ".." / ".." / ".tmp" / "epic_output.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_weekend_deals")


# 1. 에픽게임즈 무료 배포 (필수)
def _fetch_epic_free_games() -> list:
    """에픽게임즈 스토어 API에서 현재 무료 배포 + 다음 주 예고 게임 목록 수집"""
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=ko&country=KR&allowCountries=KR"
    headers = {"User-Agent": "Mozilla/5.0 (GTPlayer Newsletter Bot)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    games = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
    now = datetime.now(timezone.utc)
    
    current_free = []
    upcoming_free = []
    discounted_games = []

    for game in games:
        promotions = game.get("promotions")
        if not promotions or not isinstance(promotions, dict):
            continue
        
        title = game.get("title", "")
        desc = game.get("description", "")
        
        # 슬러그/URL 추출
        slug = game.get("productSlug")
        if not slug:
            mappings = game.get("catalogNs", {}).get("mappings", [])
            if mappings and isinstance(mappings, list):
                slug = mappings[0].get("pageSlug")
        if not slug:
            slug = game.get("urlSlug")
        
        game_url = f"https://store.epicgames.com/ko/p/{slug}" if slug and slug != "dummy" else "https://store.epicgames.com/ko/free-games"
        
        # 썸네일 추출
        images = game.get("keyImages", [])
        thumbnail = ""
        for img in images:
            if img.get("type") in ["OfferImageWide", "DieselStoreFrontWide"]:
                thumbnail = img.get("url", "")
                break
        if not thumbnail and images:
            thumbnail = images[0].get("url", "")
        
        # 현재 무료/할인인 게임
        for offer in promotions.get("promotionalOffers", []):
            for o in offer.get("promotionalOffers", []):
                try:
                    start = datetime.fromisoformat(o["startDate"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(o["endDate"].replace("Z", "+00:00"))
                    discount = o.get("discountSetting", {}).get("discountPercentage", 0)
                    if start <= now <= end:
                        end_kst = end.astimezone(KST)
                        game_data = {
                            "title": title, "description": desc, "url": game_url,
                            "thumbnail": thumbnail,
                            "end_date": end_kst.strftime("%Y-%m-%d %H:%M"),
                        }
                        if discount == 0:
                            current_free.append(game_data)
                        else:
                            game_data["discount_percent"] = discount
                            discounted_games.append(game_data)
                except: pass
        
        # 다음 주 예고 게임
        for offer in promotions.get("upcomingPromotionalOffers", []):
            for o in offer.get("promotionalOffers", []):
                try:
                    start = datetime.fromisoformat(o["startDate"].replace("Z", "+00:00"))
                    discount = o.get("discountSetting", {}).get("discountPercentage", 0)
                    if discount == 0:
                        start_kst = start.astimezone(KST)
                        upcoming_free.append({
                            "title": title, "description": desc, "url": game_url,
                            "thumbnail": thumbnail,
                            "start_date": start_kst.strftime("%Y-%m-%d %H:%M"),
                        })
                except: pass

    return current_free, upcoming_free, discounted_games


# 2. 스팀 주말 특가/무료 (선택)
def _fetch_steam_deals() -> dict | None:
    """
    Steam Store API(featuredcategories)에서 specials 목록을 가져와서:
    1) 무료(100% 할인) 게임이 있으면 그것 반환
    2) 없으면 할인율 80% 이상 중 가장 할인율 큰 게임 반환
    3) 80%도 없으면 None
    """
    url = "https://store.steampowered.com/api/featuredcategories?cc=kr&l=koreana"
    headers = {"User-Agent": "Mozilla/5.0 (GTPlayer Newsletter Bot)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning(f"Steam API 호출 실패: {e}")
        return None

    specials = data.get("specials", {}).get("items", [])
    if not specials:
        return None
    
    # 1) 무료 게임 (100% 할인) 있는지 확인
    free_games = [g for g in specials if g.get("discount_percent", 0) == 100]
    if free_games:
        g = free_games[0]
        exp = datetime.fromtimestamp(g.get("discount_expiration", 0), tz=timezone.utc)
        return {
            "type": "free",
            "name": g.get("name", ""),
            "app_id": g.get("id"),
            "url": f"https://store.steampowered.com/app/{g.get('id')}",
            "thumbnail": g.get("header_image", ""),
            "discount_percent": 100,
            "original_price": g.get("original_price", 0),
            "final_price": 0,
            "end_date": exp.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        }
    
    # 2) 80% 이상 할인 중 최고 할인율
    big_deals = [g for g in specials if g.get("discount_percent", 0) >= 80]
    if not big_deals:
        # 75% 이상으로 한 단계 완화
        big_deals = [g for g in specials if g.get("discount_percent", 0) >= 75]
    if not big_deals:
        # 50% 이상으로 추가 완화 (무료/초특가가 없는 주간 대비)
        big_deals = [g for g in specials if g.get("discount_percent", 0) >= 50]
    
    if big_deals:
        big_deals.sort(key=lambda x: x.get("discount_percent", 0), reverse=True)
        g = big_deals[0]
        exp = datetime.fromtimestamp(g.get("discount_expiration", 0), tz=timezone.utc)
        return {
            "type": "deal",
            "name": g.get("name", ""),
            "app_id": g.get("id"),
            "url": f"https://store.steampowered.com/app/{g.get('id')}",
            "thumbnail": g.get("header_image", ""),
            "discount_percent": g.get("discount_percent", 0),
            "original_price": g.get("original_price", 0),
            "final_price": g.get("final_price", 0),
            "end_date": exp.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        }
    return None


# 3. AI 코멘트 생성
def _generate_comment(epic_current, epic_upcoming, steam_deal, epic_discounted=None) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 에픽 정보 정리
    epic_info = ""
    for g in epic_current:
        epic_info += f"- 게임명: {g['title']}\n  설명: {g['description']}\n  배포 종료: {g['end_date']}\n"
    
    epic_discount_info = ""
    if epic_discounted:
        for g in epic_discounted[:3]:
            epic_discount_info += f"- 게임명: {g['title']}\n  설명: {g['description']}\n  할인율: {g['discount_percent']}% 할인\n  할인 종료: {g['end_date']}\n"

    upcoming_info = ""
    for g in epic_upcoming:
        upcoming_info += f"- 게임명: {g['title']}\n  설명: {g['description']}\n  배포 시작: {g['start_date']}\n"
    
    steam_info = ""
    if steam_deal:
        if steam_deal["type"] == "free":
            steam_info = f"스팀 무료 플레이: {steam_deal['name']} (무료 기간: ~{steam_deal['end_date']})"
        else:
            steam_info = f"스팀 주말 특가: {steam_deal['name']} {steam_deal['discount_percent']}% 할인 (기간: ~{steam_deal['end_date']})"
    
    prompt = f"""당신은 이번 주말 독자들이 돈 한 푼 안 쓰고(또는 최소 비용으로) 즐길 수 있는 최고의 게임 혜택을 정리하는 큐레이터입니다.
아래 정보를 바탕으로 뉴스레터 '주말 게임 혜택' 섹션의 코멘트를 작성해 주세요.

[에픽게임즈 이번 주 무료 배포]
{epic_info if epic_info else "현재 무료 배포 정보 없음"}

[에픽게임즈 이번 주 할인 상품 (무료 상품이 없을 때 대체 추천)]
{epic_discount_info if epic_discount_info else "할인 상품 정보 없음"}

[에픽게임즈 다음 주 예고]
{upcoming_info if upcoming_info else "다음 주 예고 정보 없음"}

[스팀 주말 혜택]
{steam_info if steam_info else "해당 없음"}

작성 규칙:
1. 한국어, 간결하고 핵심만.
2. 에픽게임즈 무료 배포 게임이 있다면: 배포 기간 언제까지인지 명시, 게임 정보(장르, 스팀 평가가 있다면 언급, 혹은 "킬링타임으로 최고", "수작 인디 게임" 등 2줄 요약).
3. 만약 이번 주 에픽게임즈 무료 배포 게임이 하나도 없다면, 대신에 제공된 '에픽게임즈 할인 상품' 중에서 가장 매력적인 할인 딜을 대안으로 콤팩트하게 소개해 주세요.
4. 'Next Week' 다음 주 예고도 함께 한 줄로 작성.
5. 스팀 혜택이 있다면 무료 혹은 할인 기간을 포함하여 추천 1문장 추가.
6. **가격(원화 등)은 UI에서 별도로 표시되므로 코멘트 텍스트에는 직접 언급하지 마세요.**
7. 느낌표/이모지 적절히 사용. 과장된 표현 피하고 핵심 재미 요소나 특징만.
8. 이 뉴스레터는 영어·일본어로도 번역 배포되므로, 한국 특유의 속어·관용구·드립은 피하고 전 세계 게이머라면 누구나 공감할 수 있는 보편적인 정서로 작성할 것.
9. 전체가 뉴스레터 한 섹션에 딱 맞는 분량으로 콤팩트하게.

출력: 완성된 코멘트 텍스트만 (JSON 등 다른 포맷 금지)"""

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        log.warning(f"Gemini 코멘트 생성 실패: {e}")
        if epic_current:
            return f"🎁 이번 주 에픽게임즈 무료 배포: {epic_current[0]['title']}! 놓치지 마세요."
        return "🎁 이번 주 에픽게임즈 스토어에서 무료 게임을 확인하세요!"


# 4. 메인 실행
def run(test_mode: bool = False):
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY not found in .env")
        return

    # 오늘 이미 생성했으면 재사용
    today_str = datetime.now().strftime("%Y-%m-%d")
    if OUTPUT_PATH.exists() and not test_mode:
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("generation_time", "")[:10] == today_str:
                log.info("오늘 이미 생성된 주말 혜택 데이터 재사용")
                return
        except: pass

    # Step 1: 에픽게임즈 (필수)
    log.info("에픽게임즈 무료 배포 정보 수집 중...")
    try:
        epic_current, epic_upcoming, epic_discounted = _fetch_epic_free_games()
        log.info(f"에픽 현재 무료: {len(epic_current)}건, 다음 주 예고: {len(epic_upcoming)}건, 할인 중: {len(epic_discounted)}건")
    except Exception as e:
        log.error(f"에픽게임즈 API 실패: {e}")
        epic_current, epic_upcoming, epic_discounted = [], [], []

    # Step 2: 스팀 (선택)
    log.info("스팀 주말 혜택 확인 중...")
    steam_deal = _fetch_steam_deals()
    if steam_deal:
        log.info(f"스팀 혜택 발견: {steam_deal['name']} ({steam_deal['type']}, {steam_deal['discount_percent']}% off)")
    else:
        log.info("스팀 주말 혜택: 해당 없음 (50%+ 할인 없음)")

    # Step 3: AI 코멘트 생성
    log.info("AI 코멘트 생성 중...")
    comment = _generate_comment(epic_current, epic_upcoming, steam_deal, epic_discounted)
    log.info(f"AI 코멘트:\n{comment}")

    # Step 4: 결과 저장
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 대표 에픽 게임 정보 (에디션 JSON용)
    if epic_current:
        epic_main = epic_current[0]
    elif epic_discounted:
        # 무료가 없으면 가장 할인율이 높은 게임을 대표로 설정
        epic_discounted.sort(key=lambda x: x.get("discount_percent", 0), reverse=True)
        epic_main = epic_discounted[0]
    else:
        epic_main = {
            "title": "에픽게임즈 주간 무료 게임",
            "url": "https://store.epicgames.com/ko/free-games",
            "thumbnail": "",
        }
    
    output = {
        "title": epic_main.get("title", "에픽게임즈 주간 무료 게임"),
        "url": epic_main.get("url", "https://store.epicgames.com/ko/free-games"),
        "thumbnail": epic_main.get("thumbnail", ""),
        "comment": comment,
        "epic_current": epic_current,
        "epic_upcoming": epic_upcoming,
        "epic_discounted": epic_discounted,
        "steam_deal": steam_deal,
        "generation_time": datetime.now().isoformat(),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f"주말 혜택 데이터 저장 완료: {OUTPUT_PATH}")

    if test_mode:
        print("\n===== 테스트 결과 =====")
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    
    run(test_mode=args.test)
