# GTnewsletter Design Guidelines

이 문서는 Ghost 블로그 및 뉴스레터의 디자인 통일성을 유지하기 위한 가이드라인입니다.

## 1. Brand Identity (브랜드 정체성)
- **로고 (Logo):** 
  - 기본 로고: [로고 이미지 링크 또는 파일 경로]
  - 아이콘 (Favicon): `logo_icon_cropped.png` 등 사용
- **핵심 메시지:** [브랜드의 핵심 가치 또는 슬로건]

## 2. Color Palette (색상 팔레트)
통일된 색상 사용은 브랜드 인지도에 중요합니다.

- **Primary Color (주 색상):** 
  - HEX: `#000000` (예시)
  - 용도: 헤더, 주요 버튼, 강조 텍스트
- **Secondary Color (보조 색상):** 
  - HEX: `#000000` (예시)
  - 용도: 서브 헤더, 보조 버튼, 배경 요소
- **Background Color (배경 색상):**
  - HEX: `#FFFFFF` (예시)
- **Text Color (텍스트 색상):**
  - 본문: `#333333` (예시)
  - 링크: `#0000EE` (예시)

## 3. Typography (타이포그래피)
가독성을 높이고 일관된 분위기를 연출합니다.

- **Primary Font (기본 폰트):**
  - 종류: (예: Pretendard, Noto Sans KR)
  - 용도: 본문, 일반 텍스트
- **Secondary Font (보조 폰트 / 헤딩용):**
  - 종류: (예: Gmarket Sans, Noto Serif KR)
  - 용도: 제목 (H1, H2, H3)
- **폰트 크기 및 행간 (Line-height):**
  - 본문 (Body): 16px / 1.6
  - 소제목 (H3): 20px / 1.5
  - 중제목 (H2): 24px / 1.4
  - 대제목 (H1): 32px / 1.3

## 4. Layout & Spacing (레이아웃 및 여백)
- **최대 너비 (Max Width):** (예: 800px) 뉴스레터 최적화 너비는 일반적으로 600px ~ 800px 사이입니다.
- **여백 (Padding/Margin):** 컨텐츠 간의 여백을 일정하게 유지합니다. (예: 섹션 간 margin 40px)

## 5. Image & Media (이미지 및 미디어)
- **비율:** 썸네일 이미지 비율 (예: 16:9, 4:3, 1:1)
- **스타일:** 모서리 둥글기 (Border-radius), 그림자 (Box-shadow) 적용 여부

## 6. Newsletter Specific (뉴스레터 특화 설정)
- **이메일 클라이언트 호환성:** 복잡한 CSS 지양, 인라인 CSS 사용 등
- **헤더/푸터 형식:** 
  - 헤더: 인사말 및 로고 배치
  - 푸터: 수신거부 링크, 저작권, 소셜 미디어 아이콘 등 필수 정보 포함

## 7. Ghost Theme Specific (Ghost 테마 특화 설정)
- **테마 이름:** `ghost-theme-gtplayer`
- **커스텀 CSS 파일 위치:** [경로]
- **주요 템플릿:** `post.hbs`, `index.hbs` 등 변경 사항 기록

---
*참고: 이 문서는 필요에 따라 지속적으로 업데이트되어야 합니다.*
