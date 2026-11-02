# 미디어 콘텐츠 자동화 디렉티브

> 마지막 업데이트: 2026-03-25

## 개요
뉴스레터에 삽입하는 시청각 콘텐츠를 자동 생성하는 파이프라인 SOP.

---

## 카테고리 1: 밈 & 하이라이트 (`fetch_meme.py`)

**목적:** 인기 게임 밈/이미지를 수집하고 한국어 코멘트 생성  
**데이터 소스:** Reddit 공개 JSON API (API 키 불필요)  
**대상 서브레딧:** `r/gaming`, `r/GameMemes`, `r/pcmasterrace`  
**AI 모델:** `gemini-flash-latest` (코멘트 생성)  
**출력:** `.tmp/meme_output.json`

### 실행
```bash
python execution/fetch_meme.py          # 일반 실행
python execution/fetch_meme.py --test   # 테스트 (콘솔 출력)
```

### 로직
1. 각 서브레딧에서 이미지 게시물 상위 10개 가져오기
2. NSFW 필터링 후 추천수 기준 상위 3개 선정
3. Gemini로 각 밈에 한국어 코멘트 1~2줄 생성
4. JSON 저장 (당일 중복 실행 시 재사용)

---

## 카테고리 2: AI 아트 / 게임씬 (`generate_scene.py`)

**목적:** 오늘의 화제 게임을 주제로 AI 생성 이미지 제작  
**데이터 소스:** `calendar_output.json`의 게임 목록  
**AI 모델:** `gemini-flash-latest` (프롬프트) + `imagen-4.0-generate-001` (이미지)  
**출력:** `.tmp/scene_output.json` + `web/assets/scenes/`

> 기존 스크립트 활용. 별도 수정 불필요.

---

## 카테고리 3: 사운드트랙 추천 (`fetch_soundtrack.py`)

**목적:** 게임 OST/Lo-Fi 영상을 검색하고 추천 코멘트 생성  
**데이터 소스:** YouTube Data API v3 (`YOUTUBE_API_KEY` 필요)  
**AI 모델:** `gemini-flash-latest` (코멘트 생성)  
**출력:** `.tmp/soundtrack_output.json`

### 실행
```bash
python execution/fetch_soundtrack.py          # 일반 실행
python execution/fetch_soundtrack.py --test   # 테스트 (콘솔 출력)
```

### 로직
1. 요일별 검색 키워드로 YouTube 검색 (10분 이상 영상)
2. 검색 결과 중 상위 1개 선정
3. Gemini로 Dr. K 스타일 추천 코멘트 2~3줄 생성
4. JSON 저장 (영상 제목, 채널, 썸네일, embed URL, 코멘트)

### 검색 키워드 풀 (요일별 로테이션)
| 요일 | 키워드 |
|------|--------|
| 월 | game lofi remix 2026 |
| 화 | video game OST chill playlist |
| 수 | 게임 브금 로파이 |
| 목 | game soundtrack relaxing mix |
| 금 | nintendo lofi beats |
| 토 | RPG ambient music mix |
| 일 | pixel game chiptune lofi |

| 일 | pixel game chiptune lofi |

---

## 카테고리 4: 트레일러 & 티저 (`fetch_trailer.py`)

**목적:** 신작 게임 또는 주요 업데이트 트레일러 소개 및 기대평 생성  
**데이터 소스:** YouTube Data API v3 (`YOUTUBE_API_KEY` 필요)  
**AI 모델:** `gemini-flash-latest` (기대평 생성)  
**출력:** `.tmp/trailer_output.json`

### 로직
1. 유튜브에서 "upcoming video game cinematic trailer" 등 주요 키워드 검색
2. 최근 7일 내 업로드된 조회수 높은 트레일러 선정
3. Gemini 모델로 트레일러에 관한 Dr. K 스타일 코멘트(한국어) 작성
4. JSON 저장 (영상 제목, 채널, 썸네일, embed URL, 코멘트)

---

## 카테고리 5: 팬메이드 & 코스프레 (`fetch_fanmade.py`)

**목적:** Reddit 게임 커뮤니티의 우수 창작물(팬아트, 코스프레) 소개 및 감상평 생성  
**데이터 소스:** Reddit 공개 JSON API (API 키 불필요)  
**대상 서브레딧:** `r/gaming`, `r/gamingcosplay`, `r/FanArt`, `r/ImaginaryGaming`  
**AI 모델:** `gemini-flash-latest` (감상평 생성)  
**출력:** `.tmp/fanmade_output.json`

### 로직
1. 설정된 Reddit 서브레딧에서 최근 1주일간 가장 추천수가 높은 이미지 결과물 추출
2. NSFW 필터링 후 2개의 최고 게시물 선정
3. Gemini 모델로 해당 팬메이드 창작물에 관한 한국어 감상평 작성
4. JSON 저장 (이미지 제목, URL, 썸네일, 추천수, 서브레딧, 코멘트)

---
```
GEMINI_API_KEY=...           # 필수 (전체)
YOUTUBE_API_KEY=...          # 필수 (카테고리 3)
REDDIT_CLIENT_ID=...         # 선택 (카테고리 1, 현재 공개 API 사용)
REDDIT_CLIENT_SECRET=...     # 선택
```

---

## 향후 개선 사항
- [ ] 밈 카테고리에 Reddit OAuth 연동 (rate limit 완화)
- [ ] 사운드트랙에 Spotify API 연동
- [ ] 수집된 미디어를 에디터 UI에서 미리보기
- [ ] `publish_edition.py`에 3개 카테고리 자동 삽입
