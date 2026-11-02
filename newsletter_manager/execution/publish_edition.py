"""
publish_edition.py — JSON 에디션 → HTML 렌더링 → Ghost 발행

사용법:
  py execution/publish_edition.py edition_002.json              # Ghost에 발행
  py execution/publish_edition.py edition_002.json --draft      # Ghost 드래프트 저장
  py execution/publish_edition.py edition_002.json --preview    # HTML 미리보기만 (.tmp에 저장)

자동 발행 (스케줄러에서 호출):
  py execution/publish_edition.py edition_002.json --auto
  → JSON의 schedule 정보를 사용하여 예약 시간에 맞춰 발행
  → schedule.languages 에 지정된 언어별로 각각 발행
"""
import os, sys, json, argparse, datetime, requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# ghost_publish is imported lazily when Ghost CLI options are used

P_COLORS = {
    'PC':['#dbeafe','#1d4ed8'],'PS5':['#ede9fe','#6d28d9'],'Xbox':['#ede9fe','#6d28d9'],
    'Mobile':['#dcfce7','#15803d'],'Switch':['#fee2e2','#b91c1c']
}

# ── IMAGE UPLOAD ──
def upload_image_to_ghost(api_url, token, image_path):
    """이미지를 Ghost에 업로드하고 URL을 반환."""
    url = f"{api_url}/ghost/api/admin/images/upload/"
    headers = {"Authorization": f"Ghost {token}"}
    
    p = Path(image_path)
    if not p.exists():
        return None
    
    try:
        with open(p, 'rb') as f:
            files = {'file': (p.name, f, 'image/png')}
            resp = requests.post(url, headers=headers, files=files, timeout=30)
        if resp.status_code == 201:
            img_url = resp.json()['images'][0]['url']
            print(f'  📷 이미지 업로드: {p.name} → {img_url}')
            return img_url
        else:
            print(f'  ⚠ 이미지 업로드 실패 ({resp.status_code})')
            return None
    except Exception as e:
        print(f'  ⚠ 이미지 업로드 오류: {e}')
        return None


def render_newsletter_html(edition, lang='ko', ghost_img_url=None):
    """에디션 JSON → 뉴스레터 HTML. OFF 섹션 제외. 모바일 반응형."""
    s = edition['sections']
    
    # Responsive CSS
    responsive_css = '''<style>
.nl-sec{padding:28px 16px}
.nl-sec-head{padding:32px 16px 28px}
.nl-chart-row{display:flex;gap:8px}
.nl-chart-col{display:inline-block;vertical-align:top;padding:0 4px}
.nl-fb-row{display:flex;justify-content:center;gap:12px}
.nl-fb-btn{flex:1}
.nl-score-box{display:flex;justify-content:space-between;align-items:flex-start;margin-top:10px}
* { word-break: keep-all; overflow-wrap: break-word; }
@media screen and (max-width:480px){
  .nl-sec{padding:14px 0 !important}
  .nl-sec-head{padding:18px 0 14px !important}
  .nl-chart-row{display:block !important}
  .nl-chart-col{display:block !important;width:100% !important;margin-bottom:12px;padding:0 !important}
  .nl-fb-row{display:block !important}
  .nl-fb-btn{display:block !important;width:100% !important;margin-bottom:8px}
  .nl-score-box{display:block !important}
  div, span, p { word-break: keep-all !important; overflow-wrap: break-word !important; }
  div[style*="font-size:20px"]{font-size:26px !important; margin-bottom:24px !important}
  div[style*="font-size:14px"]{font-size:17px !important; line-height:1.6 !important}
  div[style*="font-size:17px"]{font-size:22px !important; line-height:1.4 !important}
  div[style*="font-size:32px"]{font-size:30px !important}
  div[style*="font-size:13px"]{font-size:16px !important; line-height:1.7 !important}
  div[style*="font-size:15px"]{font-size:19px !important; line-height:1.5 !important}
  div[style*="font-size:24px"]{font-size:34px !important}
  div[style*="font-size:11px"]{font-size:14px !important}
  div[style*="font-size:12px"]{font-size:15px !important}
  div[style*="font-size:10px"]{font-size:13px !important}
}
</style>\n'''
    
    global _EDITION_NUM
    _EDITION_NUM = edition.get('num', '000')
    
    wrapper_open = '<div class="gtp-newsletter-container" style="font-family: Pretendard, -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, sans-serif; color: #111827; background-color: #ffffff;">'
    
    parts = [responsive_css, wrapper_open, render_header(edition, lang)]
    
    renderers = [
        ('calendar', render_calendar),
        ('briefing', render_briefing),
        ('feedback', render_feedback),
        ('drk', render_drk),
        ('gamescene', lambda d,l,t: render_gamescene(d,l,t,ghost_img_url)),
        ('meme', render_meme),
        ('soundtrack', render_soundtrack),
        ('trailer', render_trailer),
        ('epic', render_epic),
        ('chart', render_chart),
        ('newsletter_feedback', lambda d,l,t: render_newsletter_feedback(d,l,t, edition.get('num', '000'))),
        ('poll', render_poll),
    ]
    
    all_tr = edition.get('translations', {}).get(lang, {})
    for key, fn in renderers:
        if s.get(key, {}).get('enabled', False):
            sec_tr = all_tr.get(key, {})
            parts.append(fn(s[key], lang, sec_tr))
    
    # Removed duplicate manual footer rendering per user request
    # parts.append(render_footer(lang))
    
    parts.append('</div>')
    
    return '\n'.join(parts)

def tv(translations, lang, sec, field, original):
    import html as _html
    if lang == 'ko': return _html.escape(str(original))
    val = translations.get(lang, {}).get(sec, {}).get(field)
    val = val if (val is not None and str(val).strip() != "") else original
    return _html.escape(str(val))


def render_header(ed, lang):
    def get_style(l):
        bg = "#000" if lang == l else "#fff"
        color = "#fff" if lang == l else "#888"
        border = "" if lang == l else "border:1px solid #e5e7eb;"
        return f"background:{bg};color:{color};font-size:11px;font-weight:800;padding:8px 12px;margin-left:4px;{border}"
    
    i18n = {
        'ko': {'sub': 'DAILY GAME INTELLIGENCE'},
        'en': {'sub': 'DAILY GAME INTELLIGENCE'},
        'ja': {'sub': 'DAILY GAME INTELLIGENCE'}
    }
    t = i18n.get(lang, i18n['ko'])
    
    s_ko = get_style('ko')
    s_en = get_style('en')
    s_ja = get_style('ja')
    sub_title = t['sub']
    
    return f"""<div class="nl-sec-head" style="background:#fff;padding:4px 16px 20px">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td valign="middle" style="font-size:18px;font-weight:900;letter-spacing:1px;color:#000;text-transform:uppercase">{sub_title}</td>
<td align="right" valign="middle" class="gh-email-hide"><span style="{s_ko}">KO</span><span style="{s_en}">EN</span><span style="{s_ja}">JP</span></td>
</tr>
</table>
</div><div style="background:#000;height:4px;margin:0 16px"></div>"""


def render_footer(lang='ko'):
    i18n = {
        'ko': '게임 산업 인사이트, 매일 아침 7시',
        'en': 'Game Industry Insight, Every Morning at 7 AM',
        'ja': 'ゲーム業界インサイト、毎朝7時配信',
    }
    return f'''<div class="nl-sec" style="background:#fff;border-top:2px solid #000;padding:28px 16px;text-align:center">
<div style="font-size:22px;font-weight:900;color:#000;margin-bottom:4px">GT<span style="color:#000">Player</span></div>
<div style="font-size:11px;color:#888;margin-bottom:16px">{i18n.get(lang, i18n["ko"])}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px"><tr><td align="center">
  <span style="color:#888;font-size:11px;margin:0 10px">한국어</span>
  <span style="color:#ccc;font-size:11px">·</span>
  <span style="color:#888;font-size:11px;margin:0 10px">English</span>
  <span style="color:#ccc;font-size:11px">·</span>
  <span style="color:#888;font-size:11px;margin:0 10px">日本語</span>
</td></tr></table>
<div style="font-size:11px;color:#aaa">© 2026 GTPlayer</div></div>'''

# ⚠️ 아래 URL을 다기능 통합 서버인 Cloudflare Worker 주소로 교체했습니다.
NL_FEEDBACK_URL = 'https://gtplayer-click.gtplayernet.workers.dev'

# ⚠️ 아래 URL을 Google Apps Script 클릭 트래커 웹앱 배포 URL로 교체하세요
CLICK_TRACKER_URL = 'https://gtplayer-click.gtplayernet.workers.dev'
_EDITION_NUM = '000'

def track_url(url, section, label='', lang='ko'):
    """외부 링크를 클릭 트래킹 URL로 래핑. CLICK_TRACKER_URL 미설정 시 원본 반환."""
    if not CLICK_TRACKER_URL or not url or url == '#':
        return url
    from urllib.parse import quote
    safe_label = label[:80] if label else ''
    return f"{CLICK_TRACKER_URL}?edition={_EDITION_NUM}&section={section}&lang={lang}&label={quote(safe_label, safe='')}&url={quote(url, safe='')}"




SEC_TITLES = {
    'ko': {'calendar': '📅 PC·콘솔·모바일 신작 게임 출시일정', 'calendarEvents': '🏆 글로벌 게임쇼 및 e스포츠 대회 일정', 'briefing': '📰 게임 산업 비즈니스 및 최신 이슈 브리핑',
            'feedback': '💬 글로벌 최신 게임 유저 반응 및 리뷰 분석', 'drk': '✍️ 게임 트렌드 및 마켓 인사이트 분석', 'gamescene': '🎬 오늘의 게임 컨셉 아트 갤러리',
            'meme': '🔥 이번 주 해외 게임 커뮤니티 화제의 밈', 'soundtrack': '🎧 명작 게임 OST 플레이리스트 추천',
            'trailer': '🍿 기대작 게임 플레이 영상 및 트레일러', 'epic': '🎮 스팀 할인 및 에픽게임즈 무료 배포 혜택',
            'chart': '📊 오늘 주목받는 스팀·모바일 게임 인기 순위', 'chartCols': ['🖥 PC TOP 3', '🎮 콘솔 TOP 3', '📱 모바일 TOP 3'],
            'score': '종합 점수', 'pos': '긍정적', 'neu': '중립', 'neg': '부정적', 'collected': '수집', 'unit': '건'},
    'en': {'calendar': '📅 Upcoming PC, Console & Mobile Game Releases', 'calendarEvents': '🏆 Global Gaming Events & Esports Schedule', 'briefing': '📰 Global Gaming Industry News & Business Updates',
            'feedback': '💬 Global Player Reviews & Feedback Analysis', 'drk': '✍️ Gaming Industry Trends & Market Insights', 'gamescene': "🎬 Today's Game Concept Art Gallery",
            'meme': '🔥 Trending Memes in Global Gaming Communities', 'soundtrack': '🎧 Recommended Masterpiece Game OST Playlists',
            'trailer': '🍿 Highly Anticipated Game Gameplay & Trailers', 'epic': '🎮 Steam Sales & Free Epic Games Deals',
            'chart': '📊 Trending Steam & Mobile Game Rankings Today', 'chartCols': ['🖥 PC TOP 3', '🎮 Console TOP 3', '📱 Mobile TOP 3'],
            'score': 'Score', 'pos': 'Positive', 'neu': 'Neutral', 'neg': 'Negative', 'collected': 'Collected', 'unit': ''},
    'ja': {'calendar': '📅 PC・スマホ・家庭用ゲーム新作発売カレンダー', 'calendarEvents': '🏆 グローバルゲームショウ＆eスポーツ日程', 'briefing': '📰 グローバルゲーム業界の最新ニュース・トレンド',
            'feedback': '💬 最新ゲームのグローバルユーザー反響＆レビュー分析', 'drk': '✍️ ゲーム市場の変化を読む専門インサイト', 'gamescene': '🎬 高画質AIゲームコンセプトアートギャラリー',
            'meme': '🔥 今週の海外ゲームコミュニティ話題のミーム', 'soundtrack': '🎧 名作ゲームOSTプレイリストおすすめ',
            'trailer': '🍿 期待作のゲームプレイ映像＆トレーラー', 'epic': '🎮 Steamセール・Epic無料配布ゲーム情報',
            'chart': '📊 今日注目のSteam・モバイルゲーム人気ランキング', 'chartCols': ['🖥 PC TOP 3', '🎮 コンソール TOP 3', '📱 モバイル TOP 3'],
            'score': '総合スコア', 'pos': 'ポジティブ', 'neu': 'ニュートラル', 'neg': 'ネガティブ', 'collected': '収集', 'unit': '件'},
}
TAG_I18N = {
    'ko': {}, # identity
    'en': {'출시':'Release','업데이트':'Update','할인':'Sale','이슈':'Issue','인사이동':'Personnel','펀딩':'Funding','인수합병':'M&A','법률':'Legal','행사':'Event', '모바일':'Mobile', '기타':'Other', 'PC':'PC', '콘솔':'Console', '스위치':'Switch', '쇼케이스':'Showcase', '베타 테스트':'Beta Test'},
    'ja': {'출시':'リリース','업데이트':'アップデート','할인':'セール','이슈':'イシュー','인사이동':'人事','펀딩':'ファンディング','인수합병':'M&A','법률':'法律','행사':'イベント', '모바일':'モバイル', '기타':'その他', 'PC':'PC', '콘솔':'コンソール', '스위치':'Switch', '쇼케이스':'ショーケース', '베타 테스트':'ベータテスト'},
}

def _st(lang, key):
    return SEC_TITLES.get(lang, SEC_TITLES['ko']).get(key, SEC_TITLES['ko'].get(key, ''))

def _tt(lang, tag):
    return TAG_I18N.get(lang, {}).get(tag, tag)

def _tr_val(tr, key, default):
    """Get translated value or default."""
    if tr and key in tr:
        return tr[key]
    return default

def _tr_esc(tr, key, default):
    """Get translated value or default, and HTML escape it."""
    val = _tr_val(tr, key, default)
    if not val:
        return ""
    import html as _html
    return _html.escape(str(val))

def _fmt_text(text):
    """HTML escape (if not already escaped) is done outside. This formats markdown bold and newlines."""
    if not text:
        return ""
    import re
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(text))
    return t.replace('\n', '<br>')


def render_calendar(d, lang, tr):
    h = '<div class="nl-sec" style="background:#fff;padding:36px 16px 28px">'
    h += f'<h2 style="font-size:22px;font-weight:900;color:#000;margin:0 0 20px 0;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{_st(lang,"calendar")}</h2>'
    for i, r in enumerate(d.get('releases', [])):
        platText = ', '.join([_tt(lang, p) for p in r.get('platforms', [])])
        url = track_url(r.get("article_url",""), 'calendar', r.get('game',''), lang)
        wrap_op = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit;display:block;margin-bottom:6px;">' if url else ''
        wrap_cl = '</a>' if url else ''
        note_val = _tr_esc(tr, f"releases.{i}.note", r.get("note",""))
        note = f'<div style="font-size:12px;color:#9ca3af;margin-top:4px">{note_val}</div>' if r.get('note') else ''
        # Date column
        raw = r.get('date', '')
        dTop = raw; dBot = ''
        
        import re
        dm = re.search(r'(\d+)월\s*(\d+)일', raw)
        if dm:
            dTop = f"{dm.group(1)}/{dm.group(2)}"
        elif raw and '/' in raw:
            dTop = raw
        elif raw and '-' in raw:
            parts = raw.split('-')
            if len(parts) >= 3:
                dTop = f'{int(parts[1])}/{parts[2]}'
                
        daym = re.search(r'\(([^)]+)\)', raw)
        if daym:
            tD = daym.group(1)
            dows = {
                'en': {'월':'Mon','화':'Tue','수':'Wed','목':'Thu','금':'Fri','토':'Sat','일':'Sun'},
                'ja': {'월':'月','화':'火','수':'水','목':'木','금':'金','토':'土','일':'日'}
            }
            if lang in dows and tD in dows[lang]:
                dBot = dows[lang][tD]
            else:
                dBot = tD
        
        game_tr = _tr_esc(tr, f"releases.{i}.game", r["game"])
        if url: game_tr += ' &nearr;'
        dev_tr = _tr_esc(tr, f"releases.{i}.dev", r.get("dev",""))
        mb = '0' if url else '6px'
        h += f'''{wrap_op}<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f9fafb;margin-bottom:{mb};border:1px solid #e5e7eb">
<tr>
<td width="56" align="center" valign="middle" style="background:#1f2937;color:#fff;padding:12px 4px;">
<div style="font-size:13px;font-weight:800;line-height:1.2;margin:0">{dTop}</div>
{f'<div style="font-size:11px;font-weight:500;color:#9ca3af;margin-top:4px;line-height:1">{dBot}</div>' if dBot else ''}
</td>
<td valign="middle" style="padding:12px 14px;">
<h3 style="font-size:13px;font-weight:700;color:#111827;line-height:1.3;margin:0">{game_tr} <span style="font-size:11px;font-weight:400;color:#9ca3af;">{dev_tr}</span></h3>
{f'<div style="font-size:11px;color:#6b7280;margin-top:4px;margin-bottom:0">{platText}</div>' if platText else ''}
{note}
</td>
<td width="30" align="right" valign="middle" style="padding:10px 14px 10px 0;">

</td>
</tr>
</table>{wrap_cl}'''

    if d.get('events'):
        h += f'<div style="font-size:12px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:2px;margin:20px 0 12px">{_st(lang,"calendarEvents")}</div>'
        for ei, ev in enumerate(d['events']):
            tag = _tt(lang, ev.get('tag', ''))
            date_str = (ev.get('date','') or '').replace('~', ' ~ ')
            ev_name = _tr_esc(tr, f"events.{ei}.name", ev["name"])
            ev_note = _tr_esc(tr, f"events.{ei}.note", ev.get("note", ""))
            ev_venue = _tr_esc(tr, f"events.{ei}.venue", ev.get("venue",""))
            url = track_url(ev.get("article_url","") or ev.get("website",""), 'calendar_event', ev.get('name',''), lang)
            wrap_op = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit;display:block;margin-bottom:6px;">' if url else ''
            wrap_cl = '</a>' if url else ''
            mb = '0' if url else '6px'
            h += f'''{wrap_op}<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#fff7ed;border-left:2px solid #000;margin-bottom:{mb}">
<tr>
<td valign="middle" style="padding:14px 18px;">
<div style="font-size:13px;font-weight:700;color:#111827;margin:0">{ev_name} <span style="font-size:11px;font-weight:400;color:#6b7280;">{ev_note}</span></div>
<div style="font-size:12px;color:#6b7280;margin-top:4px;margin-bottom:0">{ev_venue} · {date_str}</div>
</td>
<td align="right" valign="middle" style="padding:14px 18px 14px 0; white-space:nowrap;">
<span style="background:#e5e7eb;color:#000;font-size:10px;font-weight:600;padding:4px 8px;border-radius:2px">{tag}</span>

</td>
</tr>
</table>{wrap_cl}'''
    return h + '</div>'


def render_briefing(d, lang, tr):
    h = f'<div class="nl-sec" style="background:#fff;padding:28px 16px;border-top:1px solid #e0e0e0">'
    h += f'<h2 style="font-size:22px;font-weight:900;color:#000;margin:0 0 20px 0;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{_st(lang,"briefing")}</h2>'
    for i, item in enumerate(d.get('items', [])):
        tag = _tt(lang, item.get('tag', ''))
        tp_colors = {'출시':('#dcfce7','#15803d'),'업데이트':('#dbeafe','#1e40af'),'할인':('#fee2e2','#b91c1c'),
                     '인사이동':('#fef9c3','#854d0e'),'펀딩':('#ede9fe','#6d28d9'),'이슈':('#fce7f3','#be185d'),
                     '인수합병':('#ccfbf1','#0f766e'),'법률':('#f3f4f6','#374151')}
        bg, tc = tp_colors.get(item.get('tag',''), ('#e5e7eb','#374151'))
        bg = item.get('tagBg', bg); tc = item.get('tagColor', tc)
        url = track_url(item.get("article_url",""), 'briefing', item.get('title',''), lang)
        wrap_op = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit;display:block;margin-bottom:14px;border-bottom:1px solid #e5e7eb;">' if url else ''
        wrap_cl = '</a>' if url else ''
        title_tr = _tr_esc(tr, f"items.{i}.title", item.get("title", ""))
        if url: title_tr += ' &nearr;'
        source_tr = _tr_esc(tr, f"items.{i}.source", item.get("source", ""))
        time_tr = _tr_esc(tr, f"items.{i}.time", item.get("time", ""))
        mb_bb = 'padding-bottom:14px;' if url else 'margin-bottom:14px;border-bottom:1px solid #e5e7eb;padding-bottom:14px;'
        h += f'''{wrap_op}<div style="{mb_bb}display:flex;gap:12px;align-items:flex-start">
<span style="background:{bg};color:{tc};font-size:9px;font-weight:700;padding:3px 0;width:56px;text-align:center;box-sizing:border-box;white-space:nowrap;flex-shrink:0;margin-top:3px">{tag}</span>
<div style="flex:1"><h3 style="font-size:12px;font-weight:600;color:#111827;line-height:1.4;margin:0">{title_tr}</h3>
<div style="font-size:12px;color:#9ca3af;margin-top:4px">{source_tr} · {time_tr}</div></div></div>{wrap_cl}'''
    return h + '</div>'


def render_feedback(d, lang, tr):
    items = d.get('items', [d])
    st = _st(lang, 'feedback')
    html_parts = []
    html_parts.append(f'<div class="nl-sec" style="background:#fff;padding:28px 16px"><h2 style="font-size:22px;font-weight:900;color:#000;margin:0 0 4px 0;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{st}</h2>')
    
    for i, item in enumerate(items):
        sep = 'border-top:1px dashed #e5e7eb;padding-top:20px;margin-top:20px' if i > 0 else ''
        collected = _st(lang, 'collected')
        unit = _st(lang, 'unit')
        score_label = _st(lang, 'score')
        game_key = f"items.{i}.game" if f"items.{i}.game" in tr else "game"
        period_key = f"items.{i}.period" if f"items.{i}.period" in tr else "period"
        sources_key = f"items.{i}.sources" if f"items.{i}.sources" in tr else "sources"
        game_tr = _tr_esc(tr, game_key, item.get("game",""))
        period_tr = _tr_esc(tr, period_key, item.get("period",""))
        sources_raw = item.get("sources","")
        if lang == 'en':
            sources_def = (sources_raw
                .replace('디시인사이드', 'DC Inside')
                .replace('루리웹', 'Ruliweb')
                .replace('인벤', 'Inven')
                .replace('커뮤니티', 'Community'))
        elif lang == 'ja':
            sources_def = (sources_raw
                .replace('디시인사이드', 'DC Inside')
                .replace('루리웹', 'Ruliweb')
                .replace('인벤', 'Inven')
                .replace('커뮤니티', 'コミュニティ'))
        else:
            sources_def = sources_raw
        sources_tr = _tr_esc(tr, sources_key, sources_def)
        h = f'''<div style="{sep}">
<div class="nl-score-box" style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:10px">
<div><h3 style="font-size:16px;font-weight:800;color:#111827;margin:0">{game_tr}</h3>
<div style="font-size:13px;color:#6b7280;margin-top:2px">{period_tr} · {collected} {item.get("count","0")}{unit} ({sources_tr})</div></div>
<div style="background:#fafafa;border:1px solid #e0e0e0;padding:8px 16px;text-align:center">
<div style="font-size:12px;color:#000;font-weight:700;letter-spacing:1px">{score_label}</div>
<div style="font-size:32px;font-weight:900;color:#000;line-height:1.1">{item.get("score","0")}</div>
<div style="font-size:14px;color:#6b7280;margin-top:4px">/5.0</div></div></div>'''
        bars = [(_st(lang,'pos'),'pos','#10b981'),(_st(lang,'neu'),'neu','#f59e0b'),(_st(lang,'neg'),'neg','#ef4444')]
        h += '<div style="margin:18px 0">'
        for label, key, color in bars:
            val = item.get(key, 0)
            h += f'''<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
<span style="font-size:12px;color:#374151;min-width:80px">{label}</span>
<div style="flex:1;background:#e5e7eb;height:9px"><div style="background:{color};width:{val}%;height:9px"></div></div>
<span style="font-size:13px;font-weight:800;color:{color};min-width:32px;text-align:right">{val}%</span></div>'''
        h += '</div><div style="margin-bottom:16px">'
        for ki, kw in enumerate(item.get('keywords', [])):
            kw_text = _tr_esc(tr, f"items.{i}.keywords.{ki}.text", kw["text"])
            bg = '#dcfce7' if kw.get('positive') else '#fee2e2'
            c = '#15803d' if kw.get('positive') else '#b91c1c'
            h += f'<span style="display:inline-block;background:{bg};color:{c};font-size:13px;font-weight:600;padding:4px 10px;margin:3px">{kw_text}</span>'
        h += '</div>'
        for ci, c in enumerate(item.get('comments', [])):
            c_text = _tr_esc(tr, f"items.{i}.comments.{ci}.text", c["text"])
            border = '#10b981' if c.get('positive') else '#ef4444'
            h += f'''<div style="background:#f9fafb;padding:16px 18px;border-left:2px solid {border};margin-bottom:8px">
<div style="font-size:14px;color:#374151;line-height:1.6">"{c_text}"</div>
{f'<div style="font-size:12px;color:#9ca3af;margin-top:6px">{c.get("meta","")}</div>' if c.get("meta") else ''}</div>'''
        html_parts.append(h + '</div>')
    
    html_parts.append('</div>')
    return '\n'.join(html_parts)

def render_newsletter_feedback(d, lang, tr, num="000"):
    base = f'{NL_FEEDBACK_URL}?edition={num}&lang={lang}' if NL_FEEDBACK_URL else '#'
    d["upLink"] = f"{base}&vote=up"
    d["downLink"] = f"{base}&vote=down"
    
    i18n_q = {'ko': '오늘 뉴스레터는 어떠셨나요?', 'en': "How was today's newsletter?", 'ja': '今日のニュースレターはいかがでしたか？'}
    i18n_up = {'ko': '👍 도움이 됐어요', 'en': '👍 Helpful', 'ja': '👍 役に立った'}
    i18n_dn = {'ko': '👎 아쉬워요', 'en': '👎 Not helpful', 'ja': '👎 いまいち'}
    
    q_orig = d.get("question") or i18n_q.get(lang, "")
    up_orig = d.get("upLabel") or i18n_up.get(lang, "")
    dn_orig = d.get("downLabel") or i18n_dn.get(lang, "")
    
    q = _tr_esc(tr, 'question', q_orig)
    up = _tr_esc(tr, 'upLabel', up_orig)
    dn = _tr_esc(tr, 'downLabel', dn_orig)
    
    return f'''<div class="nl-sec" style="background:#fafafa;padding:32px 16px;text-align:center;border-top:1px solid #e0e0e0">
<div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:20px">{q}</div>
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="50%" align="center" style="padding:0 6px 0 0">
<a href="{d["upLink"]}" target="_blank" style="display:block;background:#fff;border:2px solid #e0e0e0;padding:14px 8px;text-decoration:none;color:#111827;font-size:14px;font-weight:600;text-align:center">{up}</a>
</td>
<td width="50%" align="center" style="padding:0 0 0 6px">
<a href="{d["downLink"]}" target="_blank" style="display:block;background:#fff;border:2px solid #e0e0e0;padding:14px 8px;text-decoration:none;color:#111827;font-size:14px;font-weight:600;text-align:center">{dn}</a>
</td>
</tr></table>
</div>'''

def render_poll(d, lang, tr):
    import html as _html
    question = _html.escape(d.get("question",""))
    h = f'''<div class="nl-sec" style="background:#fff;padding:28px 16px;border-top:1px solid #e0e0e0">
<div style="font-size:22px;font-weight:900;color:#000;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{question}</div>'''
    for opt in d.get('options', []):
        opt_text = _html.escape(opt.get("text",""))
        opt_link = track_url(opt.get("link","#"), 'poll', opt.get('text',''), lang)
        h += f'''<a href="{opt_link}" style="display:block;background:#f9fafb;padding:14px 18px;margin-bottom:8px;border:1px solid #e0e0e0;text-decoration:none;color:#000;font-weight:700;text-align:center">
{opt_text}</a>'''
    return h + '</div>'


def render_drk(d, lang, tr):
    import html as _html
    
    title_tr = _tr_esc(tr, "title", d.get("title", ""))
    
    raw_intro = d.get('intro', '')
    intro_val = _tr_val(tr, "intro", raw_intro)
    intro_escaped = _html.escape(str(intro_val))
    intro = _fmt_text(intro_escaped)
    
    raw_points = d.get('points', '')
    points_val = _tr_val(tr, "points", raw_points)
    points_escaped = _html.escape(str(points_val))
    points = _fmt_text(points_escaped)
    
    return f'''<div class="nl-sec" style="background:#fafafa;padding:28px 16px;border-top:2px solid #e0e0e0">
<h2 style="font-size:22px;font-weight:900;color:#000;margin:0 0 20px 0;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{_st(lang,"drk")}</h2>
<h3 style="font-size:16px;font-weight:700;color:#111827;margin:0 0 12px 0">{title_tr}</h3>
<div style="font-size:13px;color:#374151;line-height:1.9;margin-bottom:16px">{intro}</div>
<div style="background:#fff;padding:20px 22px;border:1px solid #e0e0e0">
<div style="font-size:13px;color:#374151;line-height:1.9">{points}</div></div>
<div style="font-size:12px;color:#6b7280;margin-top:14px;text-align:right;font-style:italic">— Dr. K</div></div>'''


def render_gamescene(d, lang, tr, ghost_img_url=None):
    img_url = ghost_img_url or d.get('imgUrl', '')
    img_alt = _tr_esc(tr, "game", d.get("game", "Game Scene"))
    img_tag = f'<img src="{img_url}" alt="{img_alt}" width="100%" style="display:block;margin:0 auto;" onerror="this.style.display=\'none\'">' if img_url else ''
    game_val = _tr_esc(tr, "game", d.get("game",""))
    title_val = _tr_esc(tr, "title", d.get("title",""))
    comment_val = _tr_esc(tr, "comment", d.get("comment",""))
    return f'''<div class="nl-sec" style="background:#1f2937;padding:28px 16px">
<div style="max-width:552px; margin:0 auto;">
<h2 style="font-size:22px;font-weight:900;color:#fff;margin:0 0 16px 0;padding-bottom:14px;border-bottom:1px solid #374151">{_st(lang,"gamescene")}</h2>
{img_tag}
<div style="font-size:13px;color:#9ca3af;margin-top:14px;line-height:1.7">
<strong style="color:#e5e7eb">{game_val}</strong> — {title_val}<br>
"{comment_val}" — Dr. K</div>
</div></div>'''


def render_meme(d, lang, tr):
    """주말 화제의 짤/영상 섹션 렌더링 (단일 밈)"""
    img_url = d.get('preview_img') or d.get('thumbnail') or d.get('url', '')
    if 'v.redd.it' in img_url or img_url.endswith(('.mp4', '.webm')):
        img_url = '' # 영상일 경우 이미지가 깨지므로 숨김 처리
        
    permalink = track_url(d.get('permalink', '#'), 'meme', d.get('title', 'Meme'), lang)
    subreddit = d.get('subreddit', '')
    score = d.get('score', 0)
    author = d.get('author', '')
    what_happened = d.get('what_happened', '')
    one_liner = d.get('one_liner', '')
    
    what_label = {'ko': '무슨 일인가요?', 'en': 'What happened?', 'ja': '何があった？'}.get(lang, '무슨 일인가요?')
    liner_label = {'ko': '오늘의 한마디', 'en': 'One-liner', 'ja': 'ひとこと'}.get(lang, '오늘의 한마디')
    
    img_tag = ''
    if img_url:
        img_tag = f'''<a href="{permalink}" target="_blank" style="display:block;text-decoration:none;margin-bottom:16px">
<img src="{img_url}" alt="Reddit Meme - r/{subreddit}" width="100%" style="display:block;max-width:100%;border-radius:8px" onerror="this.style.display='none'"></a>'''
    
    return f'''<div class="nl-sec" style="background:#fff;padding:28px 16px;border-top:1px solid #e0e0e0">
<h2 style="font-size:22px;font-weight:900;color:#000;margin:0 0 20px 0;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{_st(lang,"meme")}</h2>
{img_tag}
<div style="margin-top:12px">
<div style="font-size:14px;font-weight:700;color:#1f2937;margin-bottom:6px">🤔 {what_label}</div>
<div style="font-size:14px;color:#374151;line-height:1.7;margin-bottom:16px">{_tr_esc(tr, "what_happened", what_happened)}</div>
<div style="font-size:14px;font-weight:700;color:#1f2937;margin-bottom:6px">💬 {liner_label}</div>
<div style="font-size:14px;color:#374151;line-height:1.7;margin-bottom:16px">{_tr_esc(tr, "one_liner", one_liner)}</div>
<div style="font-size:11px;color:#9ca3af;margin-top:12px;padding-top:10px;border-top:1px solid #f3f4f6">📍 r/{subreddit} · 👍 {score:,} · by u/{author} · <a href="{permalink}" target="_blank" style="color:#6366f1;text-decoration:none">원본 보기</a></div>
</div></div>'''


def render_soundtrack(d, lang, tr):
    """사운드트랙 추천 섹션 렌더링"""
    import html as _html
    title = d.get('title', '')
    channel = _html.escape(d.get('channel', ''))
    thumbnail = d.get('thumbnail', '')
    url = track_url(d.get('url', '#'), 'soundtrack', d.get('title',''), lang)
    comment = d.get('comment', '')
    
    img_tag = ''
    if thumbnail:
        img_tag = f'''<a href="{url}" target="_blank" style="display:block;text-decoration:none">
<img src="{thumbnail}" alt="{_tr_esc(tr, 'title', title)} Soundtrack" width="100%" style="display:block;max-width:100%" onerror="this.style.display='none'">
</a>'''
    
    btn_txt = {'ko': 'YouTube에서 듣기', 'en': 'Listen on YouTube', 'ja': 'YouTubeで聴く'}.get(lang, 'YouTube에서 듣기')
    return f'''<div class="nl-sec" style="background:#111827;padding:28px 16px;border-top:1px solid #374151">
<h2 style="font-size:22px;font-weight:900;color:#fff;margin:0 0 16px 0;padding-bottom:14px;border-bottom:1px solid #374151">{_st(lang,"soundtrack")}</h2>
{img_tag}
<div style="margin-top:14px">
<h3 style="font-size:14px;font-weight:700;color:#e5e7eb;line-height:1.4;margin:0">🎵 {_tr_esc(tr, "title", title)}</h3>
<div style="font-size:12px;color:#9ca3af;margin-top:4px">{channel}</div>
<div style="font-size:13px;color:#d1d5db;margin-top:12px;line-height:1.7">{_tr_esc(tr, "comment", comment)}</div>
<a href="{url}" target="_blank" style="display:inline-block;margin-top:12px;background:#ef4444;color:#fff;font-size:12px;font-weight:700;padding:8px 20px;text-decoration:none">▶ {btn_txt}</a>
</div></div>'''


def render_trailer(d, lang, tr):
    """신작 트레일러 섹션 렌더링"""
    import html as _html
    title = d.get('title', '')
    channel = _html.escape(str(d.get('channel', '')))
    thumbnail = d.get('thumbnail', '')
    url = track_url(d.get('url', '#'), 'trailer', d.get('title',''), lang)
    comment = d.get('comment', '')
    
    title_tr = _tr_esc(tr, "title", title)
    comment_tr = _fmt_text(_tr_esc(tr, "comment", comment))
    
    img_tag = ''
    if thumbnail:
        img_tag = f'''<a href="{url}" target="_blank" style="display:block;text-decoration:none">
<img src="{thumbnail}" alt="{title_tr} Trailer" width="100%" style="display:block;max-width:100%" onerror="this.style.display='none'">
</a>'''
    
    btn_txt = {'ko': 'YouTube에서 시청', 'en': 'Watch on YouTube', 'ja': 'YouTubeで視聴'}.get(lang, 'YouTube에서 시청')
    return f'''<div class="nl-sec" style="background:#1e1b4b;padding:28px 16px;border-top:1px solid #312e81">
<h2 style="font-size:22px;font-weight:900;color:#fff;margin:0 0 16px 0;padding-bottom:14px;border-bottom:1px solid #312e81">{_st(lang,"trailer")}</h2>
{img_tag}
<div style="margin-top:14px">
<h3 style="font-size:14px;font-weight:700;color:#e5e7eb;line-height:1.4;margin:0">🎬 {title_tr}</h3>
<div style="font-size:12px;color:#9ca3af;margin-top:4px">{channel}</div>
<div style="font-size:13px;color:#d1d5db;margin-top:12px;line-height:1.7">{comment_tr}</div>
<a href="{url}" target="_blank" style="display:inline-block;margin-top:12px;background:#ef4444;color:#fff;font-size:12px;font-weight:700;padding:8px 20px;text-decoration:none">▶ {btn_txt}</a>
</div></div>'''


def render_epic(d, lang, tr):
    """주말 게임 혜택 섹션 렌더링 (에픽 무료 + 스팀 특가)"""
    import html as _html
    import re
    
    def _bold(text):
        if not text: return ""
        # Convert **text** to <strong>text</strong>
        return re.sub(r'\*\*(.*?)\*\*', r'<strong style="font-weight:900;color:#fff">\1</strong>', text)

    epic_current = d.get('epic_current', [])
    epic_title = _tr_val(tr, 'title', d.get('title', ''))
    epic_title = _html.escape(str(epic_title))
    if not epic_current and epic_title and d.get('thumbnail'):
        epic_current = [{'title': epic_title, 'thumbnail': d.get('thumbnail'), 'url': d.get('url', '#')}]
    epic_upcoming = d.get('epic_upcoming', [])
    steam_deal = d.get('steam_deal')
    comment = _tr_val(tr, 'comment', d.get('comment', ''))
    comment = _html.escape(str(comment))
    
    # 텍스트 마크다운 처리
    comment_html = _bold(comment).replace('\n', '<br>')
    
    # 불필요한 에픽 타이틀 제거
    epic_comment = re.sub(r'<strong style="font-weight:900;color:#fff">\[이번 주 무료 배포 - 에픽게임즈 스토어\]<\/strong>(<br>)?', '', comment_html, flags=re.IGNORECASE)
    epic_comment = re.sub(r'\[이번 주 무료 배포 - 에픽게임즈 스토어\](<br>)?', '', epic_comment, flags=re.IGNORECASE)
    epic_comment = re.sub(r'^(<br>|\s)+', '', epic_comment)
    
    # 스팀 코멘트 분리
    steam_comment = ''
    split_pattern = r'[^<>\w\s]*\s*<strong[^>]*>(?:\[?(?:스팀 주말 혜택|스팀 주말 특가|스팀 특가)\]?|\[?Steam Weekend Deals\]?|【?Steam週末セール情報】?|Steam Deal:?)<\/strong>:?|[^<>\w\s]*\s*(?:\[?(?:스팀 주말 혜택|스팀 주말 특가|스팀 특가)\]?|\[?Steam Weekend Deals\]?|【?Steam週末セール情報】?|Steam Deal:?):?'
    parts = re.split(split_pattern, epic_comment, flags=re.IGNORECASE)
    if len(parts) > 1:
        epic_comment = re.sub(r'(<br>|\s)+$', '', parts[0])
        steam_comment = re.sub(r'^(<br>|\s)+', '', parts[1])
    
    # 에픽게임즈 카드 생성
    epic_cards_html = ''
    for game in epic_current:
        g_title = _tr_esc(tr, 'title', game.get('title', ''))
        g_thumb = game.get('thumbnail', '')
        g_url = track_url(game.get('url', '#'), 'epic', g_title, lang)
        
        epic_cards_html += f'''
        <div style="flex:1; min-width:200px; background:#1a1a1a;border-radius:12px;overflow:hidden;border:1px solid #333">
            <a href="{g_url}" target="_blank" style="display:block;text-decoration:none">
                <img src="{g_thumb}" alt="{g_title}" style="width:100%;display:block;aspect-ratio:16/9;object-fit:cover;">
            </a>
            <div style="padding:16px">
                <div style="font-size:14px;font-weight:800;color:#fff;margin-bottom:8px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-overflow:ellipsis">{g_title}</div>
                <a href="{g_url}" target="_blank" style="display:inline-block;background:#fff;color:#000;font-size:12px;font-weight:800;padding:8px 16px;text-decoration:none;border-radius:6px">FREE GET</a>
            </div>
        </div>'''
        
    epic_cards_container = f'<div style="display:flex; flex-wrap:wrap; gap:16px; margin-bottom:24px">{epic_cards_html}</div>'

    # 스팀 특가 영역
    steam_tag = ''
    if steam_deal:
        s_title = _html.escape(str(steam_deal.get('name', 'Steam Deal')))
        s_thumb = steam_deal.get('thumbnail', '')
        s_url = track_url(steam_deal.get('url', '#'), 'epic_steam', s_title, lang)
        s_discount = steam_deal.get('discount_percent', 0)
        s_price = steam_deal.get('final_price', '')
        steam_comment_html = f'<div style="font-size:13px;color:#cbd5e1;line-height:1.6;margin-bottom:16px;white-space:pre-line">⚔️ {steam_comment}</div>' if steam_comment else ''
        
        steam_tag = f'''
        <div style="margin-top:40px; padding-top:32px; border-top:1px dashed #4b5563;">
            <div style="background:#0e1c2f;border-radius:12px;padding:16px;border:1px solid #1e3a5f">
                <div style="font-size:12px;font-weight:800;color:#66c0f4;text-transform:uppercase;margin-bottom:12px;letter-spacing:1px">🔥 STEAM WEEKEND DEAL</div>
                <a href="{s_url}" target="_blank" style="display:block;text-decoration:none;margin-bottom:14px">
                    <img src="{s_thumb}" alt="{s_title}" width="100%" style="display:block;max-width:100%;border-radius:8px">
                </a>
                {steam_comment_html}
                <div style="display:flex;justify-content:flex-end;align-items:center;margin-top:4px">
                    <span style="background:#4c6b22;color:#a3d200;padding:6px 10px;font-weight:900;border-radius:4px;font-size:13px;margin-right:12px">-{s_discount}%</span>
                    <a href="{s_url}" target="_blank" style="background:#1b2838;color:#fff;border:1px solid #66c0f4;font-size:12px;font-weight:800;padding:10px 32px;text-decoration:none;border-radius:4px;display:inline-block;letter-spacing:0.5px">VIEW ON STEAM</a>
                </div>
            </div>
        </div>'''
    
    return f'''<div class="nl-sec" style="background:#000;padding:32px 16px;color:#fff">
<div style="font-size:22px;font-weight:900;color:#fff;margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid #333">{_st(lang,"epic")}</div>
{epic_cards_container}
<div style="font-size:14px;color:#9ca3af;margin-top:12px;line-height:1.7;white-space:pre-line">{epic_comment}</div>
{steam_tag}
</div>'''





def render_chart(d, lang, tr):
    cols = SEC_TITLES.get(lang, SEC_TITLES['ko']).get('chartCols', SEC_TITLES['ko']['chartCols'])
    def col(title, data, width):
        h = f'<div class="nl-chart-col" style="width:100%;display:block;margin-bottom:12px"><div style="overflow:hidden;border:1px solid #e5e7eb">'
        h += f'<div style="background:#1f2937;padding:12px 16px;font-size:14px;font-weight:800;color:#fff;white-space:nowrap">{title}</div><div style="padding:12px 14px">'
        for i, r in enumerate(data):
            rank = i + 1; rc = '#f59e0b' if rank == 1 else '#9ca3af'
            change = f' <span style="color:#10b981;font-size:10px;font-weight:700">{r["change"]}</span>' if r.get('change') else ''
            border = 'border-bottom:1px solid #f3f4f6;' if i < len(data) - 1 else ''
            h += f'<div style="font-size:14px;padding:10px 0;{border}color:#111827"><span style="color:{rc};font-weight:800;margin-right:6px">{rank}</span>{r["game"]}{change}</div>'
        return h + '</div></div></div>'
    return f'''<div class="nl-sec" style="background:#fff;padding:28px 16px">
<div style="font-size:22px;font-weight:900;color:#000;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid #e0e0e0">{_st(lang,"chart")}</div>
<div class="nl-chart-row" style="display:block">
{col(cols[0], d.get('pc',[]), '100%')}{col(cols[1], d.get('console',[]), '100%')}{col(cols[2], d.get('mobile',[]), '100%')}</div></div>'''


def _lazy_ghost():
    from ghost_publish import load_env, create_jwt_token, test_connection, publish_post
    return load_env, create_jwt_token, test_connection, publish_post

def publish_for_lang(edition, lang, api_url, token, newsletter_slug, draft=False, scheduled=False, published_at=None, feature_image=None):
    """한 언어 버전을 Ghost에 발행."""
    # 게임씬 이미지 업로드
    ghost_img_url = None
    img_path = edition['sections'].get('gamescene', {}).get('imgUrl', '')
    if img_path and not img_path.startswith('http'):
        local = Path(__file__).parent.parent.parent / 'web' / img_path
        if local.exists():
            ghost_img_url = upload_image_to_ghost(api_url, token, local)
    elif img_path.startswith('http'):
        ghost_img_url = img_path
    
    html = render_newsletter_html(edition, lang, ghost_img_url)
    
    # Newsletter title (Post title)
    # Using AI generated subject if available, otherwise fallback
    subjects = edition.get("email_subject", {})
    if lang == 'ko':
        title = f'#{edition["num"]}: {subjects.get("ko", "게임 산업 인사이트")}'
    elif lang == 'en':
        title = f'#{edition["num"]}: {subjects.get("en", "Game Intelligence")}'
    else:
        title = f'#{edition["num"]}: {subjects.get("ja", "ゲームインサイト")}'
    
    tags = [f'#lang-{lang}', f'#edition-{edition["num"]}']
    status = 'scheduled' if scheduled else ('draft' if draft else 'published')
    slug_map = {
        'ko': 'default-newsletter',
        'en': 'gtplayer-english',
        'ja': 'gtplayer-ri-ben-yu'
    }
    nl_slug = slug_map.get(lang, newsletter_slug) if (not draft) else None
    if scheduled: nl_slug = slug_map.get(lang, newsletter_slug)
    edition_slug = f'edition-{edition["num"]}'
    if lang != 'ko':
        edition_slug = f'edition-{edition["num"]}-{lang}'
    
    print(f'\n🚀 [{lang.upper()}] Ghost {"드래프트" if draft else "발행"} 중...')
    _, _, _, publish_post = _lazy_ghost()
    result = publish_post(api_url, token, title, html, tags, nl_slug, status, slug=edition_slug, published_at=published_at, feature_image=feature_image)
    
    if result:
        print(f'  ✅ [{lang.upper()}] 완료: {result.get("url", "N/A")}')
    else:
        print(f'  ❌ [{lang.upper()}] 실패')
    return result


def main():
    parser = argparse.ArgumentParser(description='에디션 JSON → Ghost 발행')
    parser.add_argument('json_file', help='에디션 JSON 파일 경로')
    parser.add_argument('--draft', action='store_true', help='Ghost 드래프트 저장')
    parser.add_argument('--schedule-ghost', action='store_true', help='Ghost 네이티브 스케줄러로 전송')
    parser.add_argument('--preview', action='store_true', help='HTML 미리보기만')
    parser.add_argument('--auto', action='store_true', help='JSON의 schedule 정보 사용 (자동 발행)')
    parser.add_argument('--lang', default=None, help='발행 언어 (미지정시 schedule.languages 사용)')
    args = parser.parse_args()
    
    # Load JSON
    json_path = Path(args.json_file)
    if not json_path.exists():
        json_path = Path(__file__).parent.parent.parent / 'web' / 'editions' / args.json_file
    if not json_path.exists():
        print(f'파일을 찾을 수 없습니다: {args.json_file}')
        sys.exit(1)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        edition = json.load(f)
    
    schedule = edition.get('schedule', {})
    print(f'에디션 #{edition["num"]} ({edition["date"]})')
    
    if schedule.get('date'):
        print(f'예약: {schedule["date"]} {schedule.get("time","07:00")} | 타겟: {schedule.get("target","all")} | 언어: {", ".join(schedule.get("languages",["ko"]))}')
    
    if args.lang:
        languages = [l.strip() for l in args.lang.split(',')]
    elif schedule.get('languages'):
        languages = schedule['languages']
    else:
        languages = ['ko']
    
    if args.auto:
        load_env, create_jwt_token, _, _ = _lazy_ghost()
        load_env()
        api_url = os.environ.get('GHOST_API_URL', '').rstrip('/')
        api_key = os.environ.get('GHOST_ADMIN_API_KEY', '')
        if api_url and api_key:
            try:
                import requests
                token = create_jwt_token(api_key)
                edition_slug = f'edition-{edition["num"]}'
                check_url = f"{api_url}/ghost/api/admin/posts/slug/{edition_slug}/"
                resp = requests.get(check_url, headers={"Authorization": f"Ghost {token}"}, timeout=10)
                if resp.status_code == 200:
                    existing_post = resp.json()["posts"][0]
                    if existing_post.get("status") == "published":
                        print(f"이미 Ghost에 발행(published)되어 있습니다.")
                        sys.exit(0)
            except Exception as e:
                pass

    if args.auto and schedule.get('date'):
        sched_dt = datetime.datetime.strptime(f'{schedule["date"]} {schedule.get("time","07:00")}', '%Y-%m-%d %H:%M')
        now = datetime.datetime.now()
        
        window_end = sched_dt + datetime.timedelta(hours=12)
        if now > window_end:
            print(f'예약 시간이 12시간 이상 경과했습니다 ({sched_dt}).')
            sys.exit(2)
            
        if now < sched_dt:
            diff = (sched_dt - now).total_seconds()
            if diff <= 3600:
                import time
                print(f'예약 발송을 위해 대기합니다... ({int(diff//60)}분 남음)')
                time.sleep(diff)
                print(f'예약 시간 도달! 발행을 시작합니다')
            else:
                print(f'아직 예약 시간이 아닙니다. 종료합니다.')
                sys.exit(2)
        else:
            print(f'예약 시간 도달! 즉시 발행합니다.')
    
    if args.preview:
        tmp_dir = Path(__file__).parent.parent.parent / '.tmp'
        tmp_dir.mkdir(exist_ok=True)
        for lang in languages:
            html = render_newsletter_html(edition, lang)
            out = tmp_dir / f'edition_{edition["num"]}_{lang}.html'
            full = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Edition #{edition["num"]} ({lang})</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>body{{font-family:'Inter',sans-serif;background:#f0f4f8;display:flex;justify-content:center;padding:40px;margin:0}}.wrap{{width:640px;max-width:100%;background:#fff}}@media(max-width:480px){{body{{padding:0}}.wrap{{width:100%}}}}</style></head>
<body><div class="wrap">{html}</div></body></html>'''
            with open(out, 'w', encoding='utf-8') as f:
                f.write(full)
            print(f'[{lang.upper()}] 미리보기: {out}')
        return
    
    load_env, create_jwt_token, test_connection, _ = _lazy_ghost()
    load_env()
    api_url = os.environ.get('GHOST_API_URL', '').rstrip('/')
    api_key = os.environ.get('GHOST_ADMIN_API_KEY', '')
    newsletter_slug = os.environ.get('GHOST_NEWSLETTER_SLUG', '')
    
    if not api_url or not api_key:
        print('.env에 GHOST_API_URL / GHOST_ADMIN_API_KEY 필요')
        sys.exit(1)
    
    token = create_jwt_token(api_key)
    if not test_connection(api_url, token):
        sys.exit(1)
        
    feature_img_url = None
    card_path = Path(__file__).parent.parent.parent / "web" / "instagram" / f"edition_{edition['num']}" / "card_news.png"
    if card_path.exists():
        print(f"인스타그램 카드를 Ghost feature_image로 업로드 중...")
        feature_img_url = upload_image_to_ghost(api_url, token, str(card_path))
    
    for lang in languages:
        published_at = None
        if args.schedule_ghost and schedule.get('date'):
            dt_str = f"{schedule['date']} {schedule.get('time','07:00')}"
            try:
                dt_obj = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                kst_tz = datetime.timezone(datetime.timedelta(hours=9))
                dt_kst = dt_obj.replace(tzinfo=kst_tz)
                
                now_kst = datetime.datetime.now(datetime.timezone.utc).astimezone(kst_tz)
                if dt_kst <= now_kst:
                    print(f"예약 시간({dt_kst})이 지났으므로 즉시 발행으로 전환합니다.")
                    args.schedule_ghost = False
                else:
                    published_at = dt_kst.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            except Exception as e:
                print(f"시간 파싱 오류: {e}")
                
        if lang != 'ko':
            if not edition.get('translations', {}).get(lang):
                print(f"[{lang.upper()}] 번역 데이터가 비어 있습니다! 해당 언어 발행을 건너뜁니다.")
                continue
        
        publish_for_lang(edition, lang, api_url, token, newsletter_slug, draft=args.draft, scheduled=args.schedule_ghost, published_at=published_at, feature_image=feature_img_url)
    
    print(f'\n전체 완료! ({len(languages)}개 언어)')

if __name__ == '__main__':
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    main()
