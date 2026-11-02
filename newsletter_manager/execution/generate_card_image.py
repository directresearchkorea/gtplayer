"""
generate_card_image.py — 에디션 JSON → 인스타그램/링크드인용 이미지 카드 생성

에디션 데이터를 읽어 SEO 최적화된 1080x1080 이미지 카드를 생성합니다.
Playwright로 HTML → PNG 변환합니다. 다국어(한국어, 영어, 일본어)를 지원합니다.

사용법:
  py execution/generate_card_image.py                      # 최신 에디션
  py execution/generate_card_image.py edition_025.json     # 특정 에디션
  py execution/generate_card_image.py edition_025.json --type all   # 모든 카드 생성
  py execution/generate_card_image.py edition_025.json --type news  # 뉴스카드만
  py execution/generate_card_image.py edition_025.json --lang en    # 영어로 카드 생성

출력: web/instagram/edition_NNN/card_news.png, card_news_en.png 등
"""

import os, sys, json, re
from pathlib import Path
from datetime import datetime

def split_epic_comment(comment):
    def _bold(text):
        return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    comment_html = _bold(comment).replace('\n', '<br>')
    
    # Remove epic title
    epic_comment = re.sub(r'<strong>\[이번 주 무료 배포 - 에픽게임즈 스토어\]</strong>(<br>)?', '', comment_html, flags=re.IGNORECASE)
    epic_comment = re.sub(r'\[이번 주 무료 배포 - 에픽게임즈 스토어\](<br>)?', '', epic_comment, flags=re.IGNORECASE)
    epic_comment = re.sub(r'^(<br>|\s)+', '', epic_comment)
    
    # Split steam comment
    steam_comment = ''
    split_pattern = r'[^<>\w\s]*\s*<strong[^>]*>(?:\[?(?:스팀 주말 혜택|스팀 주말 특가|스팀 특가)\]?|\[?Steam Weekend Deals\]?|【?Steam週末セール情報】?|Steam Deal:?)</strong>:?|[^<>\w\s]*\s*(?:\[?(?:스팀 주말 혜택|스팀 주말 특가|스팀 특가)\]?|\[?Steam Weekend Deals\]?|【?Steam週末セール정보】?|Steam Deal:?):?'
    parts = re.split(split_pattern, epic_comment, flags=re.IGNORECASE)
    if len(parts) > 1:
        epic_comment = re.sub(r'(<br>|\s)+$', '', parts[0])
        steam_comment = re.sub(r'^(<br>|\s)+', '', parts[1])
        
    def clean_html(text):
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'\1', text)
        text = text.replace('<br>', '\n')
        return text.strip()
        
    return clean_html(epic_comment), clean_html(steam_comment)

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent
EDITIONS_DIR = BASE_DIR / "web" / "editions"
OUTPUT_DIR = BASE_DIR / "web" / "instagram"

# ── 브랜드 토큰 ──────────────────────────────────────────────
BRAND = {
    "bg": "#ffffff",
    "bg_dark": "#1f2937",
    "border": "#e5e7eb",
    "text": "#111827",
    "text_sub": "#6b7280",
    "accent": "#000000",
}

def get_translated(edition, lang, section, field_key, default_val):
    if lang == "ko" or not lang:
        return default_val
    trans = edition.get("translations", {}).get(lang, {}).get(section, {})
    return trans.get(field_key, default_val)

# ── HTML 템플릿 생성 ─────────────────────────────────────────

def _base_style(lang="ko"):
    font_family = "'Inter', sans-serif" if lang == "en" else "'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
    font_link = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&display=swap" rel="stylesheet">' if lang == "en" else '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap" rel="stylesheet">'
    return f"""
    <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        width: 1080px; height: 1080px; overflow: hidden;
        font-family: {font_family};
        background: {BRAND['bg']};
        color: {BRAND['text']};
    }}
    .card {{
        width: 1080px; height: 1080px;
        display: flex; flex-direction: column;
        position: relative; overflow: hidden;
    }}
    .gradient-bg {{
        /* Removed gradient */
    }}
    .accent-circle {{
        display: none;
    }}
    .logo {{
        font-size: 36px; font-weight: 900; letter-spacing: 1px;
        color: #000;
        text-transform: uppercase;
    }}
    .logo span {{ color: #000; }}
    .tag {{
        display: inline-block;
        background: #f3f4f6;
        color: #111827;
        border: 1px solid #d1d5db;
        font-size: 34px; font-weight: 700;
        padding: 14px 28px; border-radius: 8px;
        letter-spacing: 1px;
    }}
    </style>
    {font_link}
    """


def generate_news_card_html(edition, lang="ko"):
    """뉴스 헤드라인 카드 (브리핑 기반)"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    subject = edition.get("email_subject", {}).get(lang, edition.get("email_subject", {}).get("ko", ""))
    briefing = edition.get("sections", {}).get("briefing", {})
    items = briefing.get("items", [])[:5]

    tag_label = "📰 Today's Game News" if lang == "en" else "📰 今日のゲームニュース" if lang == "ja" else "📰 오늘의 게임 뉴스"

    # 헤드라인 리스트
    headlines_html = ""
    tag_colors = {
        # KO tags
        "출시": ("#10b981", "#dcfce7"),
        "업데이트": ("#3b82f6", "#dbeafe"),
        "이슈": ("#ec4899", "#fce7f3"),
        "인수합병": ("#14b8a6", "#ccfbf1"),
        "인사이동": ("#f59e0b", "#fef9c3"),
        "펀딩": ("#8b5cf6", "#ede9fe"),
        "법률": ("#6b7280", "#f3f4f6"),
        # EN tags
        "Launch": ("#10b981", "#dcfce7"),
        "Update": ("#3b82f6", "#dbeafe"),
        "Issue": ("#ec4899", "#fce7f3"),
        "M&A": ("#14b8a6", "#ccfbf1"),
        "HR": ("#f59e0b", "#fef9c3"),
        "Funding": ("#8b5cf6", "#ede9fe"),
        "Legal": ("#6b7280", "#f3f4f6"),
    }
    import re
    for idx, item in enumerate(items):
        tag = item.get("tag", "")
        # Translate tags
        if lang == "en":
            tag_translation = {
                "출시": "Launch", "업데이트": "Update", "이슈": "Issue",
                "인수합병": "M&A", "인사이동": "HR", "펀딩": "Funding", "법률": "Legal"
            }
            tag = tag_translation.get(tag, tag)
        elif lang == "ja":
            tag_translation = {
                "출시": "発売", "업데이트": "アプデ", "이슈": "話題",
                "인수합병": "買収", "인사이동": "人事", "펀딩": "資金", "법률": "法律"
            }
            tag = tag_translation.get(tag, tag)

        color, bg = tag_colors.get(tag, ("#7c3aed", "#ede9fe"))
        title = get_translated(edition, lang, "briefing", f"items.{idx}.title", item.get("title", ""))
        title = re.sub(r'\[.*?\]\s*', '', title)  # [단독] 등 괄호 제거
            
        headlines_html += f"""
        <div style="display:flex; gap:20px; align-items:flex-start; margin-bottom:26px; padding-bottom:24px; border-bottom:1px solid {BRAND['border']};">
            <span style="background:{bg};color:{color};font-size:18px;font-weight:800;
                padding:8px 16px;border-radius:4px;white-space:nowrap;flex-shrink:0;margin-top:2px;">{tag}</span>
            <div style="font-size:26px;font-weight:700;color:{BRAND['text']};line-height:1.45;word-break:keep-all;">{title}</div>
        </div>"""

    # Subject 폰트 사이즈 가변 조절 (길이에 따라 자르지 않고 전체 출력)
    subject_font_size = "42px" if len(subject) > 40 else "48px"

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body>
    <div class="card" style="border: 20px solid #f9fafb;">
        <div style="position:relative;z-index:1;padding:50px 60px;display:flex;flex-direction:column;height:100%;background:#ffffff;">
            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:40px;">
                <div class="logo">GT<span>PLAYER</span></div>
                <div style="font-size:34px;color:{BRAND['text_sub']};font-weight:600;">#{num} · {date}</div>
            </div>

            <!-- Edition subject -->
            <div style="margin-bottom:30px;">
                <div class="tag" style="margin-bottom:20px;">{tag_label}</div>
                <div style="font-size:{subject_font_size};font-weight:900;color:{BRAND['text']};line-height:1.35;letter-spacing:-0.5px;word-break:keep-all;">
                    {subject}
                </div>
            </div>

            <!-- Headlines -->
            <div style="flex:1;">
                {headlines_html}
            </div>

            <!-- Footer -->
            <div style="border-top:2px solid {BRAND['accent']};padding-top:24px;
                display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:20px;color:{BRAND['text_sub']};font-weight:600;">gtplayer.net/edition-{num}/</div>
                <div style="font-size:20px;color:{BRAND['text']};font-weight:800;">#gamingnews #GTPlayer</div>
            </div>
        </div>
    </div>
    </body></html>
    """


def generate_calendar_card_html(edition, lang="ko"):
    """이번 주 출시 게임 카드"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    cal = edition.get("sections", {}).get("calendar", {})
    releases = cal.get("releases", [])[:6]

    tag_label = "📅 Today's Featured Games" if lang == "en" else "📅 本日注目のゲーム" if lang == "ja" else "📅 오늘 주목할 게임"

    releases_html = ""
    for idx, r in enumerate(releases):
        game = get_translated(edition, lang, "calendar", f"releases.{idx}.game", r.get("game", ""))
        dev = get_translated(edition, lang, "calendar", f"releases.{idx}.dev", r.get("dev", ""))
        plats = " · ".join(r.get("platforms", []))
        raw_date = r.get("date", "")
        
        # 날짜 축약
        import re
        dm = re.search(r'(\d+)월\s*(\d+)일', raw_date)
        if dm:
            short_date = f"{dm.group(1)}/{dm.group(2)}"
        else:
            short_date = raw_date
        
        releases_html += f"""
        <div style="display:flex;align-items:center;gap:20px;padding:18px 0;
            border-bottom:1px solid {BRAND['border']};">
            <div style="min-width:90px;text-align:center;background:#f3f4f6;
                color:#111827;font-size:20px;font-weight:800;padding:12px 6px;border-radius:4px;border:1px solid #e5e7eb;">
                {short_date}</div>
            <div style="flex:1;">
                <div style="font-size:28px;font-weight:800;color:{BRAND['text']};">{game}</div>
                <div style="font-size:20px;color:{BRAND['text_sub']};margin-top:6px;font-weight:500;">{dev} · {plats}</div>
            </div>
        </div>"""

    if lang == "en":
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            month_day_str = dt.strftime("%B %d")
        except:
            month_day_str = "Today's"
        line_title = f"New Releases Launching {month_day_str} 🎮"
    elif lang == "ja":
        try:
            parts = date.split('-')
            month_day_str = f"{int(parts[1])}月 {int(parts[2])}日"
        except:
            month_day_str = "本日"
        line_title = f"{month_day_str}、本日発売の新作ラインナップ 🎮"
    else:
        try:
            parts = date.split('-')
            month_day_str = f"{int(parts[1])}월 {int(parts[2])}일"
        except:
            month_day_str = "오늘의"
        line_title = f"{month_day_str}, 오늘 출격하는 신작 라인업 🎮"

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body>
    <div class="card" style="border: 20px solid #f9fafb;">
        <div style="position:relative;z-index:1;padding:50px 60px;display:flex;flex-direction:column;height:100%;background:#ffffff;">
            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:40px;">
                <div class="logo">GT<span>PLAYER</span></div>
                <div style="font-size:34px;color:{BRAND['text_sub']};font-weight:600;">#{num} · {date}</div>
            </div>

            <!-- Title -->
            <div style="margin-bottom:30px;border-bottom:2px solid {BRAND['accent']};padding-bottom:24px;">
                <div class="tag" style="margin-bottom:18px;">{tag_label}</div>
                <div style="font-size:52px;font-weight:900;color:{BRAND['text']};line-height:1.3;letter-spacing:-0.5px;">
                    {line_title}
                </div>
            </div>

            <!-- Releases -->
            <div style="flex:1;">
                {releases_html}
            </div>

            <!-- Footer -->
            <div style="padding-top:22px;
                display:flex;justify-content:space-between;align-items:center;margin-top:16px;">
                <div style="font-size:20px;color:{BRAND['text_sub']};font-weight:600;">gtplayer.net/edition-{num}/</div>
                <div style="font-size:20px;color:{BRAND['text']};font-weight:800;">#newreleases #GTPlayer</div>
            </div>
        </div>
    </div>
    </body></html>
    """


def generate_drk_card_html(edition, lang="ko"):
    """Dr. K 인사이트 카드"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    drk = edition.get("sections", {}).get("drk", {})
    
    title = get_translated(edition, lang, "drk", "title", drk.get("title", ""))
    intro = get_translated(edition, lang, "drk", "intro", drk.get("intro", ""))[:200]

    tag_label = "✍️ Dr. K's Insights" if lang == "en" else "✍️ Dr. Kのインサイト" if lang == "ja" else "✍️ Dr. K 인사이트"

    # 핵심 문장 추출 (첫 번째 볼드 텍스트 또는 완전한 첫 문장)
    import re
    bold_matches = re.findall(r'\*\*(.+?)\*\*', intro)
    if bold_matches:
        highlight = bold_matches[0]
    else:
        intro_clean = intro.replace('\n', ' ')
        split_char = '.' if lang == "en" else '다.'
        sentences = [s.strip() + split_char for s in intro_clean.split(split_char) if s.strip()]
        if sentences:
            highlight = sentences[0]
        else:
            highlight = title

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#ffffff;">
    <div class="card" style="border: 20px solid #f9fafb;">
        <div style="position:relative;z-index:1;padding:50px 60px 50px 80px;
            display:flex;flex-direction:column;height:100%;justify-content:space-between;background:#ffffff;">
            
            <!-- 왼쪽 굵은 테두리 강조선 -->
            <div style="position:absolute;top:50px;bottom:50px;left:40px;width:6px;background:#000;"></div>

            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div class="logo">GT<span>PLAYER</span></div>
                <div style="font-size:34px;color:{BRAND['text_sub']};font-weight:600;">#{num} · {date}</div>
            </div>

            <!-- Quote -->
            <div>
                <div class="tag" style="margin-bottom:32px;">{tag_label}</div>
                <div style="font-size:30px;color:{BRAND['text_sub']};margin-bottom:32px;line-height:1.6;font-weight:700;">
                    {title}
                </div>
                <div style="font-size:56px;font-weight:900;color:{BRAND['text']};line-height:1.5;letter-spacing:-0.5px;">
                    "{highlight}"
                </div>
            </div>

            <!-- Footer -->
            <div style="display:flex;justify-content:space-between;align-items:center;
                border-top:2px solid {BRAND['accent']};padding-top:24px;">
                <div style="font-size:26px;color:{BRAND['text']};font-weight:800;font-style:italic;">— Dr. K</div>
                <div style="font-size:22px;color:{BRAND['text_sub']};font-weight:600;">gtplayer.net/edition-{num}/</div>
            </div>
        </div>
    </div>
    </body></html>
    """


def generate_soundtrack_card_html(edition, lang="ko"):
    """금주의 추천 게임 OST 카드"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    st = edition.get("sections", {}).get("soundtrack", {})
    title = get_translated(edition, lang, "soundtrack", "title", st.get("title", ""))
    channel = st.get("channel", "")
    thumbnail = st.get("thumbnail", "")
    comment = get_translated(edition, lang, "soundtrack", "comment", st.get("comment", ""))
    game = st.get("ai_game_name", "")

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#121212; color:#ffffff;">
    <div class="card" style="border: 20px solid #1a1a1a; background:#121212;">
        <!-- Blurred Background -->
        <div style="position: absolute; top: 0; left: 0; width: 1080px; height: 1080px; 
            background: url('{thumbnail}') no-repeat center center; background-size: cover; 
            filter: blur(50px) brightness(0.25); z-index: 0;"></div>
            
        <div style="position:relative;z-index:1;padding:50px 60px;display:flex;flex-direction:column;height:100%;justify-content:space-between;">
            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div class="logo" style="color:#ffffff;">GT<span style="color:#22c55e;">PLAYER</span></div>
                <div style="font-size:34px;color:#a7a7a7;font-weight:600;">#{num} · {date}</div>
            </div>

            <!-- Music Player Container -->
            <div style="display:flex; flex-direction:column; align-items:center; margin-top:20px;">
                <div style="width: 440px; height: 440px; border-radius: 24px; overflow: hidden; 
                    box-shadow: 0 25px 50px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);">
                    <img src="{thumbnail}" style="width: 100%; height: 100%; object-fit: cover;" />
                </div>
                
                <div style="text-align: center; margin-top: 36px; padding: 0 40px; width: 100%;">
                    <div style="font-size: 36px; font-weight: 900; color: #ffffff; margin-bottom: 8px;
                        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{title}</div>
                    <div style="font-size: 24px; color: #a7a7a7; font-weight: 700; letter-spacing: 0.5px;">{game} · {channel}</div>
                </div>
                
                <!-- Progress Bar & Controls -->
                <div style="width: 720px; margin-top: 36px;">
                    <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; position: relative;">
                        <div style="width: 40%; height: 100%; background: #22c55e; border-radius: 3px;"></div>
                        <div style="position: absolute; left: 40%; top: 50%; transform: translate(-50%, -50%); 
                            width: 16px; height: 16px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 12px #22c55e;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 18px; color: #a7a7a7; margin-top: 10px; font-weight: 500;">
                        <span>1:38</span>
                        <span>3:55</span>
                    </div>
                </div>
            </div>

            <!-- Comment Box -->
            <div style="background: rgba(255, 255, 255, 0.07); border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 18px; padding: 24px 32px; backdrop-filter: blur(10px); margin: 0 20px;">
                <div style="font-size: 20px; font-weight: 900; color: #22c55e; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 22px;">🎧</span> Music Recommendation
                </div>
                <div style="font-size: 23px; line-height: 1.6; color: #e5e7eb; font-weight: 500;">
                    {comment}
                </div>
            </div>

            <!-- Footer -->
            <div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:24px;
                display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:20px;color:#a7a7a7;font-weight:600;">gtplayer.net/edition-{num}/</div>
                <div style="font-size:20px;color:#22c55e;font-weight:800;">#gameOST #GTPlayer</div>
            </div>
        </div>
    </div>
    </body></html>
    """


def generate_epic_card_html(edition, lang="ko"):
    """이번 주 무료 게임 알리미 카드"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    ep = edition.get("sections", {}).get("epic", {})
    
    epic_comment, steam_comment = split_epic_comment(ep.get("comment", ""))
    
    epic_current = ep.get("epic_current", [])
    epic_upcoming = ep.get("epic_upcoming", [])
    
    if not epic_current and epic_upcoming:
        # Use upcoming game details
        title = f"Upcoming Free Game: {epic_upcoming[0].get('title', '')}" if lang == "en" else f"다음 주 무료 예고: {epic_upcoming[0].get('title', '')}"
        thumbnail = epic_upcoming[0].get("thumbnail", "")
        comment = epic_upcoming[0].get("description", "") or epic_comment
        end_date = f"{epic_upcoming[0].get('start_date', '')} 배포 시작"
    else:
        title = get_translated(edition, lang, "epic", "title", ep.get("title", "에픽게임즈 무료 배포 게임"))
        thumbnail = ep.get("thumbnail", "")
        comment = epic_comment if epic_comment else ep.get("comment", "")
        end_date = ep.get("end_date", "")
        if not end_date:
            for eg in epic_current:
                if eg.get("end_date"):
                    end_date = eg.get("end_date")
                    break
        if not end_date:
            end_date = "금주의 배포 기간 내"
            
    # Clean emojis from end_date
    end_date = end_date.replace("⏰", "").strip()
    if not end_date.endswith("부터") and not end_date.endswith("시작"):
        end_date = f"{end_date}까지"
        
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#090d16; color:#ffffff;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div class="logo" style="color:#ffffff;">GT<span style="color:#10b981;">PLAYER</span></div>
                <div style="font-size:34px;color:#64748b;font-weight:600;">#{num} · {date}</div>
            </div>

            <!-- Title Area -->
            <div style="text-align: center; margin-top: 40px;">
                <div style="display: inline-block; border: 1px solid #10b981; padding: 8px 18px; border-radius: 8px;">
                    <span style="font-size: 18px; font-weight: 800; color: #10b981; letter-spacing: 0.5px;">EPIC GAMES</span>
                </div>
            </div>

            <!-- Comment Box -->
            <div style="background: #111827; border: 1px solid #1f2937; border-radius: 18px; padding: 24px 32px; margin: 0 20px;">
                <div style="font-size: 22px; line-height: 1.6; color: #cbd5e1; font-weight: 500; text-align: center;">
                    "{comment}"
                </div>
            </div>

            <!-- Footer -->
            <div style="border-top: 1px solid #1f2937; padding-top: 24px;
                display: flex; justify-content: space-between; align-items: center; margin: 0 20px;">
                <span style="color: #ef4444; font-weight: 900; font-size: 21px; display: flex; align-items: center; gap: 6px;">
                    ⏰ Limit: {end_date}
                </span>
                <span style="font-size: 19px; color: #64748b; font-weight: 600;">🔗 Link in Bio</span>
            </div>
        </div>
    </div>
    </body></html>
    """


def generate_cover_card_html(edition, lang="ko", title_mode="subject"):
    """뉴스레터 표지 카드 (요일별 메인 이미지 활용) - 밝은 B&W 테마 (중앙 정렬 및 45px 간격)"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    
    sections = edition.get("sections", {})
    
    # 1. 요일별/섹션별 메인 이미지 찾기 (우선순위: gamescene -> meme -> epic -> soundtrack -> trailer)
    img_url = ""
    if sections.get("gamescene", {}).get("enabled", False) and sections.get("gamescene", {}).get("imgUrl"):
        local_path = sections.get("gamescene", {}).get("imgUrl")
        abs_path = (BASE_DIR / "web" / local_path).resolve()
        if abs_path.exists():
            img_url = abs_path.as_uri()
    
    if not img_url and sections.get("meme", {}).get("enabled", False):
        meme_data = sections.get("meme", {})
        img_url = meme_data.get("preview_img") or meme_data.get("url", "")
    
    if not img_url and sections.get("epic", {}).get("enabled", False) and sections.get("epic", {}).get("thumbnail"):
        img_url = sections.get("epic", {}).get("thumbnail")
        
    if not img_url and sections.get("soundtrack", {}).get("enabled", False) and sections.get("soundtrack", {}).get("thumbnail"):
        img_url = sections.get("soundtrack", {}).get("thumbnail")

    if not img_url and sections.get("trailer", {}).get("enabled", False) and sections.get("trailer", {}).get("thumbnail"):
        img_url = sections.get("trailer", {}).get("thumbnail")

    # 2. 동적 카테고리 태그 정보 추출
    tag_label = ""
    if sections.get("gamescene", {}).get("enabled", False):
        game = sections.get("gamescene", {}).get("game", "")
        game_trans = get_translated(edition, lang, "gamescene", "game", game) if game else ""
        if lang == "en":
            tag_label = "🎨 Today's Game Art" if not game_trans else f"🎨 Today's Game Art: {game_trans}"
        elif lang == "ja":
            tag_label = "🎨 今日のゲームアート" if not game_trans else f"🎨 今日のゲームアート: {game_trans}"
        else:
            tag_label = "🎨 오늘의 게임 아트" if not game_trans else f"🎨 오늘의 게임 아트: {game_trans}"
    elif sections.get("meme", {}).get("enabled", False):
        tag_label = "😂 주말 화제의 밈" if lang == "ko" else "😂 Meme of the Weekend" if lang == "en" else "😂 週末の話題ミーム"
    elif sections.get("epic", {}).get("enabled", False):
        tag_label = "🎁 무료 게임 & 특가" if lang == "ko" else "🎁 Free Games & Deals" if lang == "en" else "🎁 無料ゲーム＆セール"
    elif sections.get("soundtrack", {}).get("enabled", False):
        tag_label = "🎧 오늘의 추천 OST" if lang == "ko" else "🎧 Recommended OST" if lang == "en" else "🎧 今日の推奨OST"
    elif sections.get("feedback", {}).get("enabled", False):
        tag_label = "💬 최신 게임 유저 반응" if lang == "ko" else "💬 Community Pulse" if lang == "en" else "💬 最新ゲームユーザー反応"
    elif sections.get("trailer", {}).get("enabled", False):
        tag_label = "🎬 추천 트레일러" if lang == "ko" else "🎬 Featured Trailer" if lang == "en" else "🎬 注目のトレーラー"
    else:
        tag_label = "📰 오늘의 게임 뉴스" if lang == "ko" else "📰 Today's Game News" if lang == "en" else "📰 今日のゲームニュース"

    # 3. 문구 모드 분기 (뉴스레터 제목 vs 요일별 동적 요약 문구 vs 상세 내용 노출 문구)
    subject = edition.get("email_subject", {}).get(lang, edition.get("email_subject", {}).get("ko", ""))
    
    if title_mode == "subject":
        tag_html = ""
        display_text = subject
    elif title_mode == "dynamic":
        tag_html = f"""<div><span style="display: inline-block; background: #000000; color: #ffffff; font-size: 20px; font-weight: 800; padding: 8px 16px; border-radius: 4px; letter-spacing: 1px; margin-bottom: 8px;">{tag_label}</span></div>"""
        display_text = subject
    elif title_mode == "detail":
        tag_html = f"""<div><span style="display: inline-block; background: #000000; color: #ffffff; font-size: 20px; font-weight: 800; padding: 8px 16px; border-radius: 4px; letter-spacing: 1px; margin-bottom: 8px;">{tag_label}</span></div>"""
        if sections.get("gamescene", {}).get("enabled", False):
            title = sections.get("gamescene", {}).get("title", "")
            title_trans = get_translated(edition, lang, "gamescene", "title", title)
            display_text = f"{subject}<span style='font-size:26px; font-weight:700; color:#4b5563; margin-top:10px; display:block; line-height:1.4;'>{title_trans}</span>"
        elif sections.get("epic", {}).get("enabled", False):
            epic_current = sections.get("epic", {}).get("epic_current", [])
            game_titles = [g.get("title", "") for g in epic_current if g.get("title")]
            if not game_titles and sections.get("epic", {}).get("title"):
                game_titles = [sections.get("epic", {}).get("title")]
            games_str = " & ".join(game_titles)
            display_text = f"{subject}<span style='font-size:26px; font-weight:700; color:#4b5563; margin-top:10px; display:block; line-height:1.4;'>{games_str}</span>"
        elif sections.get("soundtrack", {}).get("enabled", False):
            st_title = sections.get("soundtrack", {}).get("title", "")
            st_title_trans = get_translated(edition, lang, "soundtrack", "title", st_title)
            display_text = f"{subject}<span style='font-size:26px; font-weight:700; color:#4b5563; margin-top:10px; display:block; line-height:1.4;'>{st_title_trans}</span>"
        elif sections.get("trailer", {}).get("enabled", False):
            tr_title = sections.get("trailer", {}).get("title", "")
            tr_title_trans = get_translated(edition, lang, "trailer", "title", tr_title)
            display_text = f"{subject}<span style='font-size:26px; font-weight:700; color:#4b5563; margin-top:10px; display:block; line-height:1.4;'>{tr_title_trans}</span>"
        else:
            display_text = subject

    # 4. 매칭 배경용 이미지 태그 생성 (고도화된 블러 처리)
    img_bg_tag = ""
    if img_url:
        img_bg_tag = f"""
        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
            background: url('{img_url}') no-repeat center center; background-size: cover; 
            filter: blur(100px) saturate(1.6); opacity: 0.25; z-index: 0;"></div>
        """

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#ffffff; color:#111827; position:relative;">
    <div class="card" style="border: 24px solid #f9fafb; background:#ffffff; position:relative; overflow:hidden; width:1080px; height:1080px; padding: 40px 50px; display: flex; flex-direction: column; justify-content: space-between;">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center; width: 100%; padding: 0 10px; z-index: 2;">
            <div class="logo" style="font-size:24px; font-weight:900;">GT<span>PLAYER</span></div>
            <div style="font-size:18px; color:{BRAND['text_sub']}; font-weight:600;">#{num} · {date}</div>
        </div>

        {img_bg_tag}

        <!-- Centered Content Wrapper (Title top, Image bottom - 45px gap) -->
        <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 45px; width: 100%; padding: 0 10px; z-index: 2;">
            <!-- Text Box (Word-break keep-all) -->
            <div style="display: flex; flex-direction: column; gap: 8px; width: 940px; margin: 0 auto; word-break: keep-all; flex-shrink: 0;">
                {tag_html}
                <h1 style="font-size: 42px; font-weight: 900; line-height: 1.35; color: #111827; letter-spacing: -1.5px;">
                    {display_text}
                </h1>
            </div>

            <!-- Image Box (Dynamic size) -->
            {f'''
            <div style="width: 940px; flex: 1; min-height: 380px; max-height: 520px; margin: 0 auto; border-radius: 12px; overflow: hidden; 
                box-shadow: 0 15px 35px rgba(0,0,0,0.14); border: 1px solid #e5e7eb; background:#ffffff;">
                <img src="{img_url}" style="width: 100%; height: 100%; object-fit: cover;" />
            </div>
            ''' if img_url else ''}
        </div>

        <!-- Footer -->
        <div style="border-top: 2px solid {BRAND['accent']}; padding-top: 15px; z-index: 2;
            display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 0 10px;">
            <span style="font-size: 20px; color: {BRAND['text_sub']}; font-weight: 600;">👉 Swipe to Read</span>
            <span style="font-size: 18px; color: #111827; font-weight: 800;">gtplayer.net</span>
        </div>
    </div>
    </body></html>
    """



def generate_freegame_cover_html(edition, lang="ko"):
    """B&W 무료 게임 표지 카드"""
    num = edition.get("num", "000")
    date = edition.get("date", "")
    
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        date_str = f"{dt.month}월 {dt.day}일"
    except:
        date_str = "이번 주"

    title_text = "Weekly<br>Free Games" if lang == "en" else "今週の<br>無料ゲーム<br>まとめ" if lang == "ja" else "이번 주<br>무료 게임<br>총정리"
    subtitle_text = "Epic Games & Steam Free Distribution Summary" if lang == "en" else "お見逃しなく！Epic Games & Steam無料配布情報" if lang == "ja" else "놓치면 후회할 에픽게임즈 & 스팀 무료 배포 소식"

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#000000; color:#ffffff;">
    <div class="card" style="border: 24px solid #ffffff; background:#000000; padding: 60px 80px; display:flex; flex-direction:column; justify-content:space-between; height:100%;">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="logo" style="color:#ffffff; font-size:36px; font-weight:900;">GTPLAYER</div>
            <div style="font-size:34px; color:#888888; font-weight:600;">#{num} · {date}</div>
        </div>

        <!-- Center Text -->
        <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; margin-top: -40px;">
            <div style="margin-bottom: 24px;">
                <span style="font-size: 24px; font-weight: 900; color: #ffffff; border: 3px solid #ffffff; 
                    padding: 8px 24px; border-radius: 4px; letter-spacing: 2px;">FREE GAMES</span>
            </div>
            <div style="font-size: 84px; font-weight: 900; line-height: 1.1; letter-spacing: -2px; color: #ffffff;">
                {title_text}
            </div>
            <div style="font-size: 28px; color: #888888; margin-top: 30px; font-weight: 700; letter-spacing: -0.5px;">
                {subtitle_text}
            </div>
        </div>

        <!-- Footer -->
        <div style="border-top: 1px solid #333333; padding-top: 30px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size: 22px; color: #888888; font-weight: 600;">👉 Swipe for details</span>
            <span style="font-size: 22px; color: #ffffff; font-weight: 800;">#freegames #GTPlayer</span>
        </div>
    </div>
    </body></html>
    """


def generate_freegame_detail_html(edition, game_data, lang="ko"):
    """B&W 무료 게임 개별 상세 카드"""
    platform = game_data.get("platform", "EPIC GAMES")
    thumbnail = game_data.get("thumbnail", "")
    title = game_data.get("title", "")
    end_date = game_data.get("end_date", "")
    note = game_data.get("note", "")

    # 마크다운 볼드/이탤릭 기호 제거
    note = note.replace("**", "").replace("*", "")

    if not note:
        note = "Get it permanently and play now." if lang == "en" else "ライブラリに追加してプレイしよう。" if lang == "ja" else "지금 바로 라이브러리에 영구 등록하고 플레이하세요."
    if len(note) > 180:
        note = note[:180] + "…"

    if not end_date:
        end_date = "Limit" if lang == "en" else "기한"

    # '~까지' 혹은 '까지' 중복 방지
    if lang == "ko":
        if end_date.endswith("까지"):
            deadline_text = f"⏰ 기한: {end_date}"
        else:
            deadline_text = f"⏰ 기한: {end_date}까지"
    else:
        deadline_text = f"⏰ Limit: {end_date}"

    footer_text = "🔗 Link in Bio" if lang == "en" else "🔗 プロフィールリンクから受け取る" if lang == "ja" else "🔗 프로필 링크에서 받기"

    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">{_base_style(lang)}</head>
    <body style="background:#000000; color:#ffffff;">
    <div class="card" style="border: 24px solid #ffffff; background:#000000; padding: 60px 80px; display:flex; flex-direction:column; justify-content:space-between; height:100%;">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="logo" style="color:#ffffff; font-size:36px; font-weight:900;">GTPLAYER</div>
            <span style="font-size: 24px; font-weight: 800; color: #000000; background: #ffffff; 
                padding: 6px 16px; border-radius: 4px; letter-spacing: 1px;">{platform}</span>
        </div>

        <!-- Content -->
        <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 30px; margin-top: 10px;">
            <!-- Game Image Box in B&W frame -->
            <div style="height: 380px; border-radius: 12px; overflow: hidden; border: 4px solid #ffffff; box-shadow: 0 15px 30px rgba(0,0,0,0.5);">
                <img src="{thumbnail}" style="width: 100%; height: 100%; object-fit: cover;" />
            </div>
            
            <!-- Text info -->
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <div style="font-size: 44px; font-weight: 900; color: #ffffff; line-height: 1.2;">
                    {title}
                </div>
                <div style="font-size: 23px; line-height: 1.6; color: #cccccc; font-weight: 500;">
                    "{note}"
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div style="border-top: 1px solid #333333; padding-top: 30px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size: 21px; color: #ff5555; font-weight: 800;">{deadline_text}</span>
            <span style="font-size: 20px; color: #888888; font-weight: 600;">{footer_text}</span>
        </div>
    </div>
    </body></html>
    """

# ── HTML → PNG 변환 ─────────────────────────────────────────

def html_to_png(html_content, output_path):
    """Playwright를 사용하여 HTML을 1080x1080 PNG로 변환."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ playwright가 설치되지 않았습니다.")
        print("   py -m pip install playwright")
        print("   py -m playwright install chromium")
        return False

    temp_html_path = Path(output_path).with_suffix(".temp.html")
    try:
        # 로컬 파일로 임시 저장하여 상대/절대 경로 리소스 로딩 보안 문제 해결
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        file_uri = temp_html_path.resolve().as_uri()

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.goto(file_uri, wait_until="networkidle")
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        print(f"   📸 이미지 저장: {output_path}")
        return True
    except Exception as e:
        print(f"   ❌ PNG 변환 오류: {e}")
        return False
    finally:
        if temp_html_path.exists():
            try:
                temp_html_path.unlink()
            except Exception:
                pass


# ── 메인 ────────────────────────────────────────────────────

def find_latest_edition():
    files = sorted(EDITIONS_DIR.glob("edition_*.json"), reverse=True)
    return files[0] if files else None


def run(edition_file=None, card_types=None, lang="ko"):
    """카드 이미지 생성 실행."""
    if edition_file:
        json_path = EDITIONS_DIR / edition_file
        if not json_path.exists():
            json_path = Path(edition_file)
    else:
        json_path = find_latest_edition()

    if not json_path or not json_path.exists():
        print(f"❌ 에디션 파일을 찾을 수 없습니다: {json_path}")
        return []

    print(f"📄 에디션 로드: {json_path.name} (언어: {lang})")
    with open(json_path, "r", encoding="utf-8") as f:
        edition = json.load(f)

    num = edition.get("num", "000")
    out_dir = OUTPUT_DIR / f"edition_{num}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if card_types is None:
        card_types = ["cover", "news", "calendar", "drk"]

    if "news" in card_types:
        if edition.get("sections", {}).get("epic", {}).get("enabled", False) and "epic" not in card_types:
            card_types.append("epic")

    generators = {
        "cover": (f"card_cover_{lang}.png" if lang != "ko" else "card_cover.png", lambda ed: generate_cover_card_html(ed, lang)),
        "news": (f"card_news_{lang}.png" if lang != "ko" else "card_news.png", lambda ed: generate_news_card_html(ed, lang)),
        "calendar": (f"card_calendar_{lang}.png" if lang != "ko" else "card_calendar.png", lambda ed: generate_calendar_card_html(ed, lang)),
        "drk": (f"card_drk_{lang}.png" if lang != "ko" else "card_drk.png", lambda ed: generate_drk_card_html(ed, lang)),
        "soundtrack": (f"card_soundtrack_{lang}.png" if lang != "ko" else "card_soundtrack.png", lambda ed: generate_soundtrack_card_html(ed, lang)),
        "epic": (f"card_epic_{lang}.png" if lang != "ko" else "card_epic.png", lambda ed: generate_epic_card_html(ed, lang)),
    }

    generated = []
    for card_type in card_types:
        if card_type == "freegame":
            # 1. 표지 카드 생성
            print(f"\n🎨 [FREEGAME] 표지 카드 생성 중...")
            html_cover = generate_freegame_cover_html(edition, lang)
            out_cover = out_dir / (f"freegame_cover_{lang}.png" if lang != "ko" else "freegame_cover.png")
            with open(out_dir / (f"freegame_cover_{lang}.html" if lang != "ko" else "freegame_cover.html"), "w", encoding="utf-8") as f:
                f.write(html_cover)
            if html_to_png(html_cover, out_cover):
                generated.append(str(out_cover))

            # 2. 무료 게임 목록 데이터 파싱
            ep = edition.get("sections", {}).get("epic", {})
            epic_comment, steam_comment = split_epic_comment(ep.get("comment", ""))
            
            free_games = []
            
            # 에픽게임즈 무료
            epic_current = ep.get("epic_current", [])
            epic_upcoming = ep.get("epic_upcoming", [])
            
            if not epic_current and epic_upcoming:
                # Use upcoming game
                free_games.append({
                    "title": epic_upcoming[0].get("title", ""),
                    "platform": "EPIC GAMES (다음 주 예고)" if lang == "ko" else "EPIC GAMES (Upcoming)",
                    "thumbnail": epic_upcoming[0].get("thumbnail", ""),
                    "end_date": f"{epic_upcoming[0].get('start_date', '')} 배포 시작" if lang == "ko" else f"Starts {epic_upcoming[0].get('start_date', '')}",
                    "note": epic_upcoming[0].get("description", "") or epic_comment
                })
            else:
                # If epic_current is empty but title is present (fallback)
                if not epic_current and ep.get("title"):
                    import re
                    comment_text = ep.get("comment", "")
                    date_match = re.search(r'~(\d{4}-\d{2}-\d{2})', comment_text)
                    if not date_match:
                        date_match = re.search(r'(\d+월\s*\d+일)', comment_text)
                    extracted_date = date_match.group(1) if date_match else "배포 기간 내"
                    
                    epic_current = [{
                        "title": ep.get("title"),
                        "thumbnail": ep.get("thumbnail"),
                        "description": epic_comment or ep.get("comment"),
                        "end_date": ep.get("end_date") or extracted_date
                    }]
                for eg in epic_current:
                    free_games.append({
                        "title": eg.get("title", ""),
                        "platform": "EPIC GAMES",
                        "thumbnail": eg.get("thumbnail", ""),
                        "end_date": eg.get("end_date", ""),
                        "note": eg.get("description", "") or epic_comment
                    })
            
            # 스팀 무료/할인 딜
            sd = ep.get("steam_deal", {})
            if sd:
                discount_str = f" ({sd.get('discount_percent')}% 할인)" if sd.get("discount_percent") else ""
                note = steam_comment
                if not note:
                    note = sd.get("note", "")
                if not note:
                    note = f"스팀에서 현재{discount_str} 딜 진행 중입니다." if lang == "ko" else f"Steam weekend deal ongoing: {discount_str}"
                free_games.append({
                    "title": sd.get("name", ""),
                    "platform": f"STEAM{discount_str}",
                    "thumbnail": sd.get("thumbnail", ""),
                    "end_date": sd.get("end_date", "기한 내"),
                    "note": note
                })
            
            # 상세 카드 렌더링
            for idx, game_data in enumerate(free_games):
                print(f"🎨 [FREEGAME] 상세 카드 {idx} 생성 중...")
                html_item = generate_freegame_detail_html(edition, game_data, lang)
                out_item = out_dir / (f"freegame_item_{idx}_{lang}.png" if lang != "ko" else f"freegame_item_{idx}.png")
                with open(out_dir / (f"freegame_item_{idx}_{lang}.html" if lang != "ko" else f"freegame_item_{idx}.html"), "w", encoding="utf-8") as f:
                    f.write(html_item)
                if html_to_png(html_item, out_item):
                    generated.append(str(out_item))
            continue

        if card_type == "cover":
            # Dynamic Title Cover (통일된 표지 디자인)
            fn_cover = f"card_cover_{lang}.png" if lang != "ko" else "card_cover.png"
            out_cover = out_dir / fn_cover
            html_cover = generate_cover_card_html(edition, lang, title_mode="dynamic")
            with open(out_dir / fn_cover.replace(".png", ".html"), "w", encoding="utf-8") as f:
                f.write(html_cover)
            print(f"\n🎨 [COVER] 표지 카드 생성 중 (Dynamic 디자인)...")
            if html_to_png(html_cover, out_cover):
                generated.append(str(out_cover))

            # 하위 호환성을 위해 card_cover_dynamic.png에도 동일 사본 제공
            fn_dyn = f"card_cover_dynamic_{lang}.png" if lang != "ko" else "card_cover_dynamic.png"
            import shutil
            shutil.copy2(out_cover, out_dir / fn_dyn)
            continue

        if card_type not in generators:
            print(f"   ⚠️ 알 수 없는 카드 타입: {card_type}")
            continue

        filename, gen_fn = generators[card_type]
        out_path = out_dir / filename

        print(f"\n🎨 [{card_type.upper()}] 카드 생성 중...")
        html = gen_fn(edition)

        # HTML 미리 저장 (디버깅용)
        html_path = out_dir / filename.replace(".png", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # PNG 변환
        success = html_to_png(html, out_path)
        if success:
            generated.append(str(out_path))

    print(f"\n✅ 생성 완료: {len(generated)}개 카드")
    for p in generated:
        print(f"   → {p}")

    return generated


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    edition_file = None
    card_types = None
    lang = "ko"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i].endswith(".json"):
            edition_file = args[i]
        elif args[i] == "--type" and i + 1 < len(args):
            i += 1
            if args[i] == "all":
                card_types = ["cover", "news", "calendar", "drk"]
            else:
                card_types = [t.strip() for t in args[i].split(",")]
        elif args[i] == "--lang" and i + 1 < len(args):
            i += 1
            lang = args[i]
        i += 1

    run(edition_file=edition_file, card_types=card_types, lang=lang)
