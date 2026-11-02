"""
build_site.py — 에디션 JSON → gtplayer.net 정적 HTML 사이트 빌드 (Ghost 테마 100% 재현)

기존 Ghost 테마(ghost-theme-gtplayer)의 미니멀 B&W 디자인, 다국어 라우팅(/, /en/, /ja/),
포스트 URL(/edition-NNN/, /en/edition-NNN-en/, /ja/edition-NNN-ja/),
검색 모달(/api/search.json), GA4/GTM 및 Cloudflare Worker 클릭 추적기를 모두 포함한
완전한 정적 웹사이트를 dist/ 폴더에 생성합니다.

사용법:
  python newsletter_manager/execution/build_site.py                  # 전체 빌드 (dist/ 생성)
  python newsletter_manager/execution/build_site.py --clean          # dist/ 초기화 후 전체 빌드
  python newsletter_manager/execution/build_site.py --edition 155    # 특정 에디션만 빌드
  python newsletter_manager/execution/build_site.py --preview        # 빌드 후 로컬 서버(8000) 실행
"""

import os
import re
import sys
import html
import json
import math
import shutil
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from publish_edition import render_newsletter_html

# ── 경로 설정 ──
ROOT = Path(__file__).parent.parent.parent
EDITIONS_DIR = ROOT / "web" / "editions"
ASSETS_DIR = ROOT / "web" / "assets"
THEME_DIR = ROOT / "ghost-theme-gtplayer"
DIST_DIR = ROOT / "dist"

POSTS_PER_PAGE = 15
SITE_URL = "https://www.gtplayer.net"
CUSTOM_DOMAIN = "www.gtplayer.net"

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def strip_html_tags(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<script[^>]*>.*?</script>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def format_dates(date_str: str):
    """YYYY-MM-DD 문자열을 한/영/일 포맷 및 MM.DD 포맷으로 변환."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        wd = dt.weekday()
        return {
            "iso": dt.strftime("%Y-%m-%d"),
            "mmdd": dt.strftime("%m.%d"),
            "ymd_dot": dt.strftime("%Y.%m.%d"),
            "ko": f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일 ({WEEKDAYS_KO[wd]})",
            "en": f"{MONTHS_EN[dt.month - 1]} {dt.day:02d}, {dt.year} ({WEEKDAYS_EN[wd]})",
            "ja": f"{dt.year}年 {dt.month:02d}月 {dt.day:02d}日 ({WEEKDAYS_JA[wd]})",
        }
    except Exception:
        return {
            "iso": date_str or "2026-01-01",
            "mmdd": (date_str[5:10].replace("-", ".") if date_str and len(date_str) >= 10 else ""),
            "ymd_dot": (date_str[:10].replace("-", ".") if date_str else ""),
            "ko": date_str,
            "en": date_str,
            "ja": date_str,
        }


def get_post_title(edition: dict, lang: str = "ko") -> str:
    num = edition.get("num", "000")
    subjects = edition.get("email_subject", {})
    subj = subjects.get(lang, "")
    if not subj and lang != "ko":
        subj = subjects.get("ko", "")
    if subj:
        if subj.startswith(f"#{num}") or subj.startswith(f"GTPlayer #{num}"):
            return subj
        return f"#{num}: {subj}"
    fallback = {
        "ko": f"GTPlayer #{num} | 게임 산업 인사이트",
        "en": f"GTPlayer #{num} | Game Intelligence",
        "ja": f"GTPlayer #{num} | ゲームインサイト",
    }
    return fallback.get(lang, fallback["ko"])


def get_post_excerpt(edition: dict, lang: str = "ko") -> str:
    s = edition.get("sections", {})
    all_tr = edition.get("translations", {}).get(lang, {})

    drk = s.get("drk", {})
    if drk.get("enabled"):
        tr_drk = all_tr.get("drk", {})
        title = tr_drk.get("title") or drk.get("title", "")
        intro = tr_drk.get("intro") or drk.get("intro", "")
        combined = f"{title} — {intro}".strip(" —")
        if combined:
            return re.sub(r"\*\*(.+?)\*\*", r"\1", combined)[:160]

    briefing = s.get("briefing", {}).get("items", [])
    if briefing:
        tr_brf = all_tr.get("briefing", {})
        titles = []
        for i, it in enumerate(briefing[:3]):
            t = tr_brf.get(f"items.{i}.title") or it.get("title", "")
            if t:
                titles.append(t)
        if titles:
            return " · ".join(titles)[:160]

    return {
        "ko": "오늘의 게임 출시 캘린더, 업계 브리핑, Dr. K 인사이트를 확인하세요.",
        "en": "Check out today's game release calendar, industry briefing, and Dr. K insights.",
        "ja": "本日のゲーム発売カレンダー、業界ブリーフィング、Dr. Kインサイトをご覧ください。",
    }.get(lang, "")


def get_post_url_path(num: str, lang: str = "ko") -> str:
    if lang == "ko":
        return f"/edition-{num}/"
    return f"/{lang}/edition-{num}-{lang}/"


def inject_lang_links_into_newsletter_html(newsletter_html: str, num: str, available_langs: list) -> str:
    """뉴스레터 본문 상단의 KO / EN / JP 배지를 실제 해당 에디션 언어별 URL 링크로 변환."""
    ko_href = get_post_url_path(num, "ko")
    en_href = get_post_url_path(num, "en") if "en" in available_langs else "/en/"
    ja_href = get_post_url_path(num, "ja") if "ja" in available_langs else "/ja/"

    def repl_badge(match):
        style = match.group(1)
        label = match.group(2)
        href = {"KO": ko_href, "EN": en_href, "JP": ja_href}.get(label, ko_href)
        return f'<a href="{href}" style="{style};text-decoration:none;display:inline-block">{label}</a>'

    return re.sub(
        r'<span style="([^"]+)">(KO|EN|JP)</span>',
        repl_badge,
        newsletter_html,
    )


def render_base_layout(title: str, description: str, lang: str, canonical_path: str, body_class: str, main_html: str) -> str:
    """ghost-theme-gtplayer/default.hbs + header.hbs + footer.hbs + Code Injection 통합 레이아웃."""
    escaped_title = html.escape(title)
    escaped_desc = html.escape(description)
    canonical_url = f"{SITE_URL}{canonical_path}"

    i18n_ui = {
        "ko": {
            "search_btn": "검색...",
            "search_placeholder": "포스트 검색...",
            "sub_btn": "구독하기",
            "footer_desc": "게임 산업 인사이트, 매일 아침 7시",
            "footer_sub": "구독하기",
            "footer_archive": "에디션 아카이브",
            "lang_code": "KO",
        },
        "en": {
            "search_btn": "Search...",
            "search_placeholder": "Search posts...",
            "sub_btn": "Subscribe",
            "footer_desc": "Game Industry Insights, Every Morning at 7 AM",
            "footer_sub": "Subscribe",
            "footer_archive": "Edition Archive",
            "lang_code": "EN",
        },
        "ja": {
            "search_btn": "検索...",
            "search_placeholder": "ポストを検索...",
            "sub_btn": "購読する",
            "footer_desc": "ゲーム業界のインサイト、毎朝7時",
            "footer_sub": "購読する",
            "footer_archive": "エディションアーカイブ",
            "lang_code": "JP",
        },
    }
    ui = i18n_ui.get(lang, i18n_ui["ko"])
    home_href = "/" if lang == "ko" else f"/{lang}/"

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','GTM-M3429V8X');</script>
<!-- End Google Tag Manager -->
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-PNH9SFR5HK"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-PNH9SFR5HK');
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escaped_title}</title>
<meta name="description" content="{escaped_desc}">
<link rel="canonical" href="{canonical_url}">
<link rel="icon" type="image/png" href="/favicon.png">
<meta property="og:site_name" content="GTPlayer">
<meta property="og:title" content="{escaped_title}">
<meta property="og:description" content="{escaped_desc}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:type" content="{'article' if 'post-template' in body_class else 'website'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escaped_title}">
<meta name="twitter:description" content="{escaped_desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/style.css">
<script>
  if (!localStorage.getItem('langSelectBoxSelected')) {{
    const currentPath = window.location.pathname;
    const isBot = /bot|googlebot|crawler|spider|robot|crawling/i.test(navigator.userAgent);
    if (!isBot && currentPath === '/') {{
      fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {{
          const country = data.country_code;
          if (country === 'KR') {{
            // Korean default
          }} else if (country === 'JP') {{
            window.location.replace('/ja/');
          }} else {{
            window.location.replace('/en/');
          }}
        }})
        .catch(error => console.error("Error fetching location data", error));
    }}
  }}
</script>
</head>
<body class="{body_class}">
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-M3429V8X"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->

<header class="site-header">
  <a href="{home_href}" class="logo">
    <img src="/favicon.png" alt="GTPlayer" class="logo-img">
    <span class="logo-text">GT<span>Player</span></span>
  </a>
  <div class="header-right">
    <button class="header-search-btn" id="headerSearchBtn" aria-label="Search">
      <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      <span class="search-text" id="headerSearchText">{ui['search_btn']}</span>
    </button>

    <a href="#subscribe-section" class="btn-sub" id="headerSubBtn">{ui['sub_btn']}</a>

    <div class="lang-selector">
      <button class="lang-btn" id="langToggle">🌐 <span id="currentLang">{ui['lang_code']}</span> ▾</button>
      <div class="lang-dropdown" id="langDropdown">
        <a href="/" class="lang-option" data-lang="ko" onclick="localStorage.setItem('langSelectBoxSelected','ko')">🇰🇷 한국어</a>
        <a href="/en/" class="lang-option" data-lang="en" onclick="localStorage.setItem('langSelectBoxSelected','en')">🇺🇸 English</a>
        <a href="/ja/" class="lang-option" data-lang="ja" onclick="localStorage.setItem('langSelectBoxSelected','ja')">🇯🇵 日本語</a>
      </div>
    </div>
  </div>
</header>

<!-- Search Overlay -->
<div class="search-overlay" id="searchOverlay">
  <div class="search-modal">
    <div class="search-modal-header">
      <input type="text" class="search-input-lg" id="searchInputLg" placeholder="{ui['search_placeholder']}" autofocus>
      <button class="search-close" id="searchClose">
        <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
    <div class="search-body">
      <div class="search-label" id="searchHeaderLabel">POSTS</div>
      <div class="search-results" id="searchResults"></div>
    </div>
  </div>
</div>

<main>
{main_html}
</main>

<footer class="site-footer">
  <div class="foot-logo">GT<span>Player</span></div>
  <div class="foot-sub" id="footerDesc">{ui['footer_desc']}</div>
  <div class="foot-lang">
    <a href="/" class="lbtn" onclick="localStorage.setItem('langSelectBoxSelected','ko')">한국어</a>
    <a href="/en/" class="lbtn" onclick="localStorage.setItem('langSelectBoxSelected','en')">English</a>
    <a href="/ja/" class="lbtn" onclick="localStorage.setItem('langSelectBoxSelected','ja')">日本語</a>
  </div>
  <div class="foot-links">
    <a href="#subscribe-section" id="footerSubBtn">{ui['footer_sub']}</a>
    <a href="{home_href}" id="footerArchiveBtn">{ui['footer_archive']}</a>
  </div>
  <div class="foot-copy">&copy; {datetime.now().year} GTPlayer. All rights reserved.</div>
</footer>

<script>
(function () {{
  var currentLangCode = '{lang}';
  var SEARCH_LOG_URL = 'https://script.google.com/macros/s/AKfycbztDYnHRRoHNpUt07_SOl-COmJ-7A1MAvVMTAD51dL4nvjAF9BEDxgM-SMUxQ5h18mBaQ/exec';
  var SUBSCRIBE_URL = 'https://gtplayer-click.gtplayernet.workers.dev';
  var loggedQueries = {{}};
  var currentLocation = null;

  async function logSearchQuery(query, resultsCount) {{
    if (!SEARCH_LOG_URL || loggedQueries[query]) return;
    loggedQueries[query] = true;
    try {{
      if (!currentLocation) {{
        var response = await fetch('https://ipapi.co/json/');
        currentLocation = await response.json();
      }}
      fetch(SEARCH_LOG_URL, {{
        method: 'POST',
        mode: 'no-cors',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          query: query,
          resultsCount: resultsCount,
          language: currentLangCode || 'ko',
          country: currentLocation.country_name || currentLocation.country_code,
          city: currentLocation.city,
          userAgent: navigator.userAgent
        }})
      }});
    }} catch (e) {{}}
  }}

  var overlay = document.getElementById('searchOverlay');
  var closeBtn = document.getElementById('searchClose');
  var input = document.getElementById('searchInputLg');
  var results = document.getElementById('searchResults');
  var searchTimer = null;
  var allPosts = null;

  function openSearch() {{
    overlay.classList.add('active');
    input.value = '';
    results.innerHTML = '';
    setTimeout(function () {{ input.focus(); }}, 100);
    document.body.style.overflow = 'hidden';
    if (!allPosts) loadAllPosts();
  }}

  function closeSearch() {{
    overlay.classList.remove('active');
    document.body.style.overflow = '';
  }}

  document.addEventListener('DOMContentLoaded', function () {{
    var headerSearch = document.getElementById('headerSearchBtn');
    if (headerSearch) headerSearch.addEventListener('click', openSearch);

    // Subscribe Form Handler
    document.querySelectorAll('form[data-members-form="subscribe"]').forEach(function (form) {{
      form.addEventListener('submit', function (e) {{
        e.preventDefault();
        var emailInput = form.querySelector('input[type="email"]');
        var email = emailInput ? emailInput.value.trim() : '';
        if (!email) return;
        form.classList.remove('error');
        fetch(SUBSCRIBE_URL + '?action=subscribe&lang=' + encodeURIComponent(currentLangCode) + '&email=' + encodeURIComponent(email), {{
          method: 'GET',
          mode: 'no-cors',
          keepalive: true
        }}).catch(function () {{}});
        form.classList.add('success');
      }});
    }});
  }});

  closeBtn.addEventListener('click', closeSearch);
  overlay.addEventListener('click', function (e) {{
    if (e.target === overlay) closeSearch();
  }});
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') closeSearch();
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {{
      e.preventDefault();
      openSearch();
    }}
  }});

  input.addEventListener('input', function () {{
    clearTimeout(searchTimer);
    var q = input.value.trim();
    if (q.length < 2) {{ results.innerHTML = ''; return; }}
    searchTimer = setTimeout(function () {{ filterPosts(q); }}, 200);
  }});

  function loadAllPosts() {{
    fetch('/api/search.json')
      .then(function (r) {{ return r.json(); }})
      .then(function (data) {{
        allPosts = (data.posts || []).filter(function (p) {{
          return !p.lang || p.lang === currentLangCode;
        }});
        var q = input.value.trim();
        if (q.length >= 2) filterPosts(q);
      }})
      .catch(function () {{
        allPosts = [];
        var errMsg = currentLangCode === 'en' ? 'Unable to load search data.' : (currentLangCode === 'ja' ? '検索データを読み込めませんでした。' : '검색 데이터를 불러올 수 없습니다.');
        results.innerHTML = '<div class="search-no-results">' + errMsg + '</div>';
      }});
  }}

  function filterPosts(query) {{
    if (!allPosts) {{ loadAllPosts(); return; }}
    var q = query.toLowerCase();
    var filtered = allPosts.filter(function (p) {{
      return (p.title && p.title.toLowerCase().indexOf(q) !== -1) ||
        (p.excerpt && p.excerpt.toLowerCase().indexOf(q) !== -1) ||
        (p.plaintext && p.plaintext.toLowerCase().indexOf(q) !== -1);
    }});
    renderResults(filtered, query);
    logSearchQuery(query, filtered.length);
  }}

  function escHtml(s) {{
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }}

  function highlightMatch(text, query) {{
    if (!text) return '';
    var safeText = escHtml(text);
    var safeQ = escHtml(query).replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
    var regex = new RegExp('(' + safeQ + ')', 'gi');
    return safeText.replace(regex, '<strong style="color:#000;">$1</strong>');
  }}

  function renderResults(posts, query) {{
    if (posts.length === 0) {{
      var noResMsg = currentLangCode === 'en'
        ? 'No results found for "' + escHtml(query) + '".'
        : (currentLangCode === 'ja'
          ? '「' + escHtml(query) + '」に一致する結果はありません。'
          : '"' + escHtml(query) + '"에 대한 결과가 없습니다.');
      results.innerHTML = '<div class="search-no-results">' + noResMsg + '</div>';
      return;
    }}
    var htmlStr = '';
    posts.slice(0, 30).forEach(function (p) {{
      var excerpt = (p.excerpt || '').substring(0, 110) + '...';
      htmlStr += '<a class="search-result-item" href="' + p.url + '">' +
        '<div class="search-result-title">🔎 ' + highlightMatch(p.title || '', query) + '</div>' +
        '<div class="search-result-excerpt">' + highlightMatch(excerpt, query) + '</div></a>';
    }});
    results.innerHTML = htmlStr;
  }}

  // Language dropdown toggle
  var btn = document.getElementById('langToggle');
  var dd = document.getElementById('langDropdown');
  if (btn && dd) {{
    btn.addEventListener('click', function (e) {{
      e.stopPropagation();
      dd.classList.toggle('show');
    }});
    document.addEventListener('click', function () {{ dd.classList.remove('show'); }});
  }}

  // Web Click Tracker (Cloudflare Worker)
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('a[href*="workers.dev"]').forEach(function(link) {{
      try {{
        var urlObj = new URL(link.href);
        var originalUrl = urlObj.searchParams.get('url');
        if (originalUrl) {{
          var currentSection = urlObj.searchParams.get('section') || 'unknown';
          urlObj.searchParams.set('section', currentSection + '_web');
          var backgroundTrackerUrl = urlObj.toString();
          link.href = originalUrl;
          link.addEventListener('click', function() {{
            fetch(backgroundTrackerUrl, {{
              method: 'GET',
              mode: 'no-cors',
              keepalive: true
            }}).catch(function(){{}});
          }});
        }}
      }} catch (e) {{}}
    }});
  }});
}})();
</script>
</body>
</html>"""


def render_index_page(editions_for_lang: list, lang: str, page_num: int, total_pages: int) -> str:
    """ghost-theme-gtplayer/index-ko.hbs, index-en.hbs, index-ja.hbs와 100% 동일한 홈페이지/목록 생성."""
    hero_i18n = {
        "ko": {
            "site_title": "GTPlayer — 게임 산업 인사이트, 매일 아침 7시",
            "site_desc": "게임 캘린더, 신작 유저 피드백, 업계 뉴스를 매일 아침 7시에 받아보세요.",
            "h1": "게임 인사이트,<br><em>매일 아침 7시</em>",
            "sub": "PC · 콘솔 · 모바일 · 업계 뉴스 · Dr. K 코멘트",
            "btn": "구독하기",
            "success": "구독 신청이 완료되었습니다! 매일 아침 7시에 만나요.",
            "note": "스팸 없음 · 언제든 해지 가능",
            "read_unit": "분 읽기",
            "prev": "← 이전",
            "next": "다음 →",
            "empty": "아직 한국어 에디션이 없습니다.",
        },
        "en": {
            "site_title": "GTPlayer — Game Insights, Every Morning at 7 AM",
            "site_desc": "PC, Console, Mobile, Industry News & Dr. K Commentary delivered every morning.",
            "h1": "Game Insights,<br><em>Every Morning at 7 AM</em>",
            "sub": "PC · Console · Mobile · Industry News · Dr. K Commentary",
            "btn": "Subscribe",
            "success": "Thank you for subscribing! Check your inbox every morning.",
            "note": "No spam · Cancel anytime",
            "read_unit": " min read",
            "prev": "← Prev",
            "next": "Next →",
            "empty": "No English editions available yet.",
        },
        "ja": {
            "site_title": "GTPlayer — ゲームインサイト、毎朝7時にお届け",
            "site_desc": "PC・コンソール・モバイル・業界ニュース・Dr. Kコメントを毎朝お届けします。",
            "h1": "ゲームインサイト、<br><em>毎朝7時にお届け</em>",
            "sub": "PC · コンソール · モバイル · 業界ニュース · Dr. K コメント",
            "btn": "無料購読",
            "success": "ご購読ありがとうございます！毎朝7時にお届けします。",
            "note": "スパムなし · いつでも解約可能",
            "read_unit": "分で読めます",
            "prev": "← 前へ",
            "next": "次へ →",
            "empty": "日本語エディションはまだありません。",
        },
    }
    t = hero_i18n.get(lang, hero_i18n["ko"])

    rows = []
    for ed in editions_for_lang:
        num = ed["num"]
        dates = format_dates(ed["date"])
        title = html.escape(get_post_title(ed["data"], lang))
        excerpt = html.escape(get_post_excerpt(ed["data"], lang))
        url = get_post_url_path(num, lang)
        rows.append(f"""  <article class="edition-row">
    <div class="edition-meta">
      <span class="edition-date">{dates['mmdd']}</span>
      <span class="edition-dot">·</span>
      <span class="edition-reading">3{t['read_unit']}</span>
    </div>
    <a href="{url}" class="edition-link">
      <h3 class="edition-title">{title}</h3>
      <p class="edition-excerpt">{excerpt}</p>
    </a>
  </article>""")

    rows_html = "\n".join(rows) if rows else f'<div class="no-posts"><p>{t["empty"]}</p></div>'

    # Pagination
    base_prefix = "" if lang == "ko" else f"/{lang}"
    pagination_html = ""
    if total_pages > 1:
        prev_btn = ""
        next_btn = ""
        if page_num > 1:
            prev_href = f"{base_prefix}/" if page_num == 2 else f"{base_prefix}/page/{page_num - 1}/"
            prev_btn = f'<a class="page-btn" href="{prev_href}">{t["prev"]}</a>'
        if page_num < total_pages:
            next_href = f"{base_prefix}/page/{page_num + 1}/"
            next_btn = f'<a class="page-btn" href="{next_href}">{t["next"]}</a>'
        pagination_html = f"""  <nav class="pagination">
    {prev_btn}
    <span class="page-num">{page_num} / {total_pages}</span>
    {next_btn}
  </nav>"""

    main_html = f"""<!-- HERO -->
<section class="hero" id="subscribe-section">
  <div class="hero-eyebrow">Daily Game Intelligence</div>
  <h1>{t['h1']}</h1>
  <p class="hero-sub">{t['sub']}</p>
  <div class="hero-subscribe-form">
    <form data-members-form="subscribe">
      <div class="hero-email-wrap">
        <input data-members-email type="email" name="email" class="hero-email-input" placeholder="jamie@example.com" required>
        <button type="submit" class="hero-email-btn">{t['btn']}</button>
      </div>
      <div class="message-success">{t['success']}</div>
      <div class="message-error" data-members-error></div>
    </form>
  </div>
  <p class="hero-note">{t['note']}</p>
</section>

<div class="page">
{rows_html}
{pagination_html}
</div>"""

    canonical_path = (f"{base_prefix}/" if page_num == 1 else f"{base_prefix}/page/{page_num}/") or "/"
    return render_base_layout(
        title=t["site_title"],
        description=t["site_desc"],
        lang=lang,
        canonical_path=canonical_path,
        body_class=f"home-template tag-hash-lang-{lang}",
        main_html=main_html,
    )


def render_post_page(edition_meta: dict, lang: str, prev_ed: dict | None, next_ed: dict | None) -> str:
    """ghost-theme-gtplayer/post.hbs와 100% 동일한 포스트 상세 페이지 생성."""
    data = edition_meta["data"]
    num = edition_meta["num"]
    dates = format_dates(edition_meta["date"])
    title = get_post_title(data, lang)
    excerpt = get_post_excerpt(data, lang)
    canonical_path = get_post_url_path(num, lang)
    full_url = f"{SITE_URL}{canonical_path}"

    # Available languages for this edition
    avail_langs = ["ko"]
    for lc in ("en", "ja"):
        if data.get("translations", {}).get(lc) or data.get("raw_html", {}).get(lc):
            avail_langs.append(lc)

    # Render inner newsletter HTML (use raw_html if recovered from Ghost export, else render from JSON)
    raw_html_for_lang = data.get("raw_html", {}).get(lang)
    if raw_html_for_lang:
        newsletter_html = raw_html_for_lang
    else:
        img_url = data.get("sections", {}).get("gamescene", {}).get("imgUrl", "")
        if img_url and not img_url.startswith("http") and not img_url.startswith("/"):
            img_url = "/" + img_url.lstrip("/")
        newsletter_html = render_newsletter_html(data, lang, ghost_img_url=img_url or None)

    newsletter_html = inject_lang_links_into_newsletter_html(newsletter_html, num, avail_langs)

    post_i18n = {
        "ko": {
            "date": dates["ko"],
            "read": "3분 읽기",
            "share": "공유하기",
            "copied": "링크가 복사되었습니다!",
            "prev": "← 이전",
            "next": "다음 →",
            "sub_title": "GTPlayer 뉴스레터 구독하기",
            "sub_desc": "게임 산업 인사이트를 매일 아침 7시에 받아보세요.",
            "sub_btn": "무료 구독 →",
            "sub_ok": "구독 신청이 완료되었습니다!",
        },
        "en": {
            "date": dates["en"],
            "read": "3 min read",
            "share": "Share",
            "copied": "Link copied!",
            "prev": "← Prev",
            "next": "Next →",
            "sub_title": "Subscribe to GTPlayer Newsletter",
            "sub_desc": "Get game industry insights every morning at 7 AM.",
            "sub_btn": "Subscribe for free →",
            "sub_ok": "Thank you for subscribing!",
        },
        "ja": {
            "date": dates["ja"],
            "read": "3 分 読む",
            "share": "共有する",
            "copied": "リンクをコピーしました！",
            "prev": "← 前へ",
            "next": "次へ →",
            "sub_title": "GTPlayer ニュースレターを購読する",
            "sub_desc": "ゲーム業界のインサイトを毎朝7時にお届けします。",
            "sub_btn": "無料購読 →",
            "sub_ok": "ご購読ありがとうございます！",
        },
    }
    pt = post_i18n.get(lang, post_i18n["ko"])

    from urllib.parse import quote
    encoded_title = quote(title)
    encoded_url = quote(full_url)

    # Prev / Next Navigation
    prev_html = '<a class="post-nav-link prev" href="#" style="visibility:hidden;"></a>'
    next_html = '<a class="post-nav-link next" href="#" style="visibility:hidden;"></a>'
    if prev_ed:
        p_url = get_post_url_path(prev_ed["num"], lang)
        p_title = html.escape(get_post_title(prev_ed["data"], lang))
        prev_html = f"""<a class="post-nav-link prev" href="{p_url}">
      <span class="post-nav-label">{pt['prev']}</span>
      <span class="post-nav-title">{p_title}</span>
    </a>"""
    if next_ed:
        n_url = get_post_url_path(next_ed["num"], lang)
        n_title = html.escape(get_post_title(next_ed["data"], lang))
        next_html = f"""<a class="post-nav-link next" href="{n_url}">
      <span class="post-nav-label">{pt['next']}</span>
      <span class="post-nav-title">{n_title}</span>
    </a>"""

    nav_display = "flex" if (prev_ed or next_ed) else "none"

    main_html = f"""<article class="post-full post">
  <div class="post-header">
    <div class="post-header-inner">
      <div class="post-eyebrow">DAILY GAME INTELLIGENCE</div>
      <h1 class="post-title">{html.escape(title)}</h1>
      <div class="post-meta-bar">
        <time datetime="{dates['iso']}">{pt['date']}</time>
        <span class="meta-sep">·</span><span>{pt['read']}</span>
      </div>
    </div>
  </div>

  <section class="post-content">
    <div class="kg-card kg-html-card">
      {newsletter_html}
    </div>
  </section>

  <!-- POST SHARE -->
  <div class="post-share">
    <span class="share-label">{pt['share']}</span>
    <a href="https://twitter.com/intent/tweet?text={encoded_title}&url={encoded_url}" target="_blank" rel="noopener" class="share-btn share-twitter" title="Share on X">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
    </a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={encoded_url}" target="_blank" rel="noopener" class="share-btn share-facebook" title="Share on Facebook">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M22.675 0H1.325C.593 0 0 .593 0 1.325v21.351C0 23.407.593 24 1.325 24H12.82v-9.294H9.692v-3.622h3.128V8.413c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.313h3.587l-.467 3.622h-3.12V24h6.116c.73 0 1.323-.593 1.323-1.325V1.325C24 .593 23.407 0 22.675 0z"/></svg>
    </a>
    <button class="share-btn share-link" title="Copy Link" id="copyLinkBtn" data-url="{full_url}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
    </button>
  </div>

  <script>
  document.addEventListener('DOMContentLoaded', function() {{
    var copyBtn = document.getElementById('copyLinkBtn');
    if (copyBtn) {{
      copyBtn.addEventListener('click', function() {{
        var url = this.getAttribute('data-url');
        navigator.clipboard.writeText(url).then(function() {{
          alert('{pt['copied']}');
        }});
      }});
    }}
  }});
  </script>

  <!-- POST NAV -->
  <nav class="post-nav" style="display:{nav_display};">
    {prev_html}
    {next_html}
  </nav>

  <div class="post-subscribe" id="subscribe-section">
    <h3>{pt['sub_title']}</h3>
    <p>{pt['sub_desc']}</p>
    <div class="hero-subscribe-form" style="max-width:440px;margin:0 auto;">
      <form data-members-form="subscribe">
        <div class="hero-email-wrap">
          <input data-members-email type="email" name="email" class="hero-email-input" placeholder="jamie@example.com" required>
          <button type="submit" class="hero-email-btn">{pt['sub_btn']}</button>
        </div>
        <div class="message-success">{pt['sub_ok']}</div>
      </form>
    </div>
  </div>
</article>"""

    return render_base_layout(
        title=f"{title} — GTPlayer",
        description=excerpt,
        lang=lang,
        canonical_path=canonical_path,
        body_class=f"post-template tag-hash-lang-{lang}",
        main_html=main_html,
    )


def load_all_editions(only_edition: str | None = None):
    """발행된(published) 에디션 JSON을 로드하고 메타데이터 추출."""
    editions = []
    target_num = str(only_edition).zfill(3) if only_edition else None
    for f in sorted(EDITIONS_DIR.glob("edition_*.json")):
        try:
            with open(f, "r", encoding="utf-8-sig") as fp:
                data = json.load(fp)
            num = str(data.get("num", f.stem.split("_")[1])).zfill(3)
            if target_num and num != target_num:
                continue
            status = data.get("status", "published")
            if not target_num and status in ("draft", "scheduled"):
                continue
            date = data.get("date") or data.get("schedule", {}).get("date") or "2026-03-20"
            editions.append({
                "num": num,
                "date": date,
                "file": f,
                "data": data,
            })
        except Exception as e:
            print(f"  ⚠ {f.name} 로드 실패: {e}")
    # 번호순 오름차순 정렬
    editions.sort(key=lambda x: int(x["num"]) if x["num"].isdigit() else 0)
    return editions


def has_lang(edition_meta: dict, lang: str) -> bool:
    if lang == "ko":
        return True
    data = edition_meta["data"]
    return bool(data.get("translations", {}).get(lang) or data.get("raw_html", {}).get(lang))


def write_html(rel_path: str, content: str):
    out_file = DIST_DIR / rel_path.lstrip("/")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)


def build_all_posts_and_search(all_editions: list):
    """언어별 포스트 페이지 생성 및 검색 인덱스(/api/search.json) 구축."""
    search_posts = []

    for lang in ("ko", "en", "ja"):
        lang_eds = [e for e in all_editions if has_lang(e, lang)]
        for i, ed in enumerate(lang_eds):
            prev_ed = lang_eds[i - 1] if i > 0 else None
            next_ed = lang_eds[i + 1] if i < len(lang_eds) - 1 else None
            num = ed["num"]
            page_html = render_post_page(ed, lang, prev_ed, next_ed)

            # 1) Ghost routes.yaml 및 SNS 링크와 100% 호환되는 경로들에 생성
            if lang == "ko":
                write_html(f"edition-{num}/index.html", page_html)
                write_html(f"editions/{num}/index.html", page_html)
            else:
                write_html(f"{lang}/edition-{num}-{lang}/index.html", page_html)
                write_html(f"edition-{num}-{lang}/index.html", page_html)
                write_html(f"editions/{num}/{lang}.html", page_html)

            # 2) 검색 인덱스 엔트리 추가
            raw_html = ed["data"].get("raw_html", {}).get(lang) or render_newsletter_html(ed["data"], lang)
            search_posts.append({
                "num": num,
                "lang": lang,
                "title": get_post_title(ed["data"], lang),
                "url": get_post_url_path(num, lang),
                "excerpt": get_post_excerpt(ed["data"], lang),
                "published_at": ed["date"],
                "plaintext": strip_html_tags(raw_html)[:1500],
            })

    # 최신순 정렬 후 /api/search.json 및 /api/editions.json 저장
    search_posts.sort(key=lambda x: (x["published_at"], x["num"]), reverse=True)
    api_dir = DIST_DIR / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    with open(api_dir / "search.json", "w", encoding="utf-8") as f:
        json.dump({"posts": search_posts}, f, ensure_ascii=False)
    with open(api_dir / "editions.json", "w", encoding="utf-8") as f:
        json.dump([p for p in search_posts if p["lang"] == "ko"], f, ensure_ascii=False, indent=2)


def build_index_and_pagination(all_editions: list):
    """언어별 메인 홈페이지(/, /ko/, /en/, /ja/) 및 페이지네이션(/page/N/) 빌드."""
    for lang in ("ko", "en", "ja"):
        lang_eds = [e for e in reversed(all_editions) if has_lang(e, lang)]
        total_pages = max(1, math.ceil(len(lang_eds) / POSTS_PER_PAGE))

        for page_num in range(1, total_pages + 1):
            start = (page_num - 1) * POSTS_PER_PAGE
            chunk = lang_eds[start : start + POSTS_PER_PAGE]
            html_page = render_index_page(chunk, lang, page_num, total_pages)

            if lang == "ko":
                if page_num == 1:
                    write_html("index.html", html_page)
                    write_html("ko/index.html", html_page)
                    write_html("editions/index.html", html_page)
                else:
                    write_html(f"page/{page_num}/index.html", html_page)
                    write_html(f"ko/page/{page_num}/index.html", html_page)
            else:
                if page_num == 1:
                    write_html(f"{lang}/index.html", html_page)
                else:
                    write_html(f"{lang}/page/{page_num}/index.html", html_page)


def copy_assets():
    """Ghost 테마 CSS, 파비콘, 뉴스레터 에셋 복사."""
    dst_assets = DIST_DIR / "assets"
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, dst_assets, dirs_exist_ok=True)

    # Ghost 테마 CSS 복사
    theme_css = THEME_DIR / "assets" / "css" / "style.css"
    if theme_css.exists():
        css_dst = dst_assets / "css" / "style.css"
        css_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(theme_css, css_dst)

    # 파비콘/로고 아이콘 복사
    favicon_src = ROOT / "logo_icon_cropped.png"
    if favicon_src.exists():
        shutil.copy2(favicon_src, DIST_DIR / "favicon.png")

    # CNAME & .nojekyll
    with open(DIST_DIR / "CNAME", "w", encoding="utf-8") as f:
        f.write(CUSTOM_DOMAIN)
    with open(DIST_DIR / ".nojekyll", "w", encoding="utf-8") as f:
        f.write("")


def main():
    parser = argparse.ArgumentParser(description="GTPlayer 정적 사이트 빌드 (Ghost 테마 호환)")
    parser.add_argument("--edition", help="특정 에디션만 확인 (예: 155)")
    parser.add_argument("--preview", action="store_true", help="빌드 후 로컬 서버 실행")
    parser.add_argument("--clean", action="store_true", help="dist/ 삭제 후 클린 빌드")
    args = parser.parse_args()

    print("=" * 55)
    print("  GTPlayer — GitHub Pages 정적 사이트 빌드 (B&W Theme)")
    print("=" * 55)

    if args.clean and DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print("🗑  dist/ 정리 완료")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    print("\n📂 에디션 로드 중...")
    all_editions = load_all_editions(args.edition)
    if not all_editions:
        print("   ⚠ 빌드할 에디션이 없습니다.")
        return
    print(f"   총 {len(all_editions)}개 에디션 발견 (#{all_editions[0]['num']} ~ #{all_editions[-1]['num']})")

    print("\n🔨 포스트 페이지 및 검색 인덱스 빌드 중...")
    build_all_posts_and_search(all_editions)
    print("   ✅ KO / EN / JA 포스트 및 /api/search.json 생성 완료")

    print("\n🏠 언어별 홈페이지 및 페이지네이션 빌드 중...")
    build_index_and_pagination(all_editions)
    print("   ✅ /, /en/, /ja/ 및 페이지네이션 생성 완료")

    print("\n📦 테마 CSS, 에셋, CNAME 복사 중...")
    copy_assets()
    print(f"   ✅ 에셋 및 CNAME ({CUSTOM_DOMAIN}) 생성 완료")

    print(f"\n{'=' * 55}")
    print(f"  ✅ 정적 사이트 빌드 완료! 출력 경로: {DIST_DIR}")
    print(f"{'=' * 55}")

    if args.preview:
        import http.server
        import socketserver
        port = 8000
        os.chdir(DIST_DIR)
        print(f"\n🌐 로컬 서버: http://localhost:{port}")
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            httpd.serve_forever()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
