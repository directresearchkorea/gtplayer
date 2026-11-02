# GTPlayer 뉴스레터 아웃라인 (Directive)

## 개요
- **이름**: GTPlayer (`https://www.gtplayer.net`)
- **발행 주기**: 평일 오전 7시
- **언어**: 한국어 (`ko`) / English (`en`) / 日本語 (`ja`)
- **타깃**: 게임업계 종사자, 학생, 게이머
- **에디터 페르소나**: Dr. K (AI 생성, 게임 업계 인사이더 스타일)
- **호스팅**: GitHub Pages 정적 사이트 (`newsletter_manager/execution/build_site.py` → `dist/`)

---

## 뉴스레터 섹션 구성

### [HEADER]
- GTPlayer 로고 + 에디션 번호 (예: #155)
- 발행 날짜 / 예상 읽기 시간
- 언어 선택 버튼 (KO / EN / JP)

---

### [섹션 1] 📅 PC·콘솔·모바일 신작 게임 출시일정
- 오늘 기준 3일 이내 출시/업데이트/베타 테스트 예정 게임 목록 (`curate_calendar.py`)
- 플랫폼 태그 (PC / PS5 / Xbox / Mobile / Switch)
- 글로벌 게임쇼 및 e스포츠 대회 일정 (`events_calendar.json` + 동적 이벤트 추출)

---

### [섹션 2] 📰 게임 산업 비즈니스 및 최신 이슈 브리핑
- 뉴스 6~7개 (`curate_briefing.py`)
- 카테고리 태그: `출시` / `업데이트` / `할인` / `인사이동` / `펀딩` / `이슈`
- **데이터 소스**: 인벤, 게임메카, IGN, PC Gamer, GamesIndustry.biz, 4Gamer, Famitsu, Dengeki RSS/스크래핑 (`collect_news.py`)

---

### [섹션 3] ✍️ 게임 트렌드 및 마켓 인사이트 분석 (Dr. K)
- 오늘 주요 뉴스를 종합한 핵심 인사이트 1개 (`generate_insight.py`)
- 2줄 Hook (`intro`) + 4문단 본론 (`points`)

---

### [섹션 4] 요일별 스페셜 로테이션 코너 (월~금)
- **월요일 (0)**: 🔥 이번 주 해외 게임 커뮤니티 화제의 밈 (`fetch_meme.py` — Reddit 인기 밈)
- **화요일 (1)**: 💬 글로벌 최신 게임 유저 반응 및 리뷰 분석 (`generate_feedback.py` — `GTcrawling` + `GTanalysis` SQLite DB 연동, 2개 게임 감성 비율/키워드/유저 3줄 반응) *(구 `🎬 오늘의 게임 컨셉 아트 갤러리` 삭제 후 대체)*
- **수요일 (2)**: 🎧 명작 게임 OST 플레이리스트 추천 (`fetch_soundtrack.py` — YouTube Data API)
- **목요일 (3)**: 🍿 기대작 게임 플레이 영상 및 트레일러 (`fetch_trailer.py` — YouTube Data API)
- **금요일 (4)**: 🎮 스팀 할인 및 에픽게임즈 무료 배포 혜택 (`fetch_epic.py` — Epic Games & Steam API)

---

### [FOOTER & 피드백]
- 오늘 뉴스레터 피드백 투표 (`👍 도움이 됐어요` / `👎 아쉬워요` — Cloudflare Worker 연동)
- © GTPlayer / 다국어 전환 / 구독하기 및 아카이브 링크

---

## 기술 스택
| 항목 | 도구 |
|------|------|
| AI 요약/번역/코멘트 | Gemini API (`gemini-flash-latest`) |
| 유저 피드백 데이터 | `GTcrawling` (`crawling_*.db`) + `GTanalysis` (`processed_*.db`) |
| 웹 호스팅 및 아카이브 | GitHub Pages (`build_site.py` → `dist/`, 도메인: `www.gtplayer.net`) |
| 이메일 발송 | SendGrid (`scheduled_publish.py` + `subscribers.json`) |
| SNS 자동 발행 | X (`post_to_x_browser.py`), Instagram (`post_to_instagram.py`), LinkedIn (`post_to_linkedin_browser.py`) |
| 스케줄링 | Windows Task Scheduler (`auto_morning_pipeline.py`, `auto_publish_scheduler.py`) |
