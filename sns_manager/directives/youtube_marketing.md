# YouTube Marketing Automation (게시글 좋아요 및 자동 댓글 봇)

## 1. 목적 (Goal)
- 사전에 수집된 YouTube 타겟 영상 리스트(`youtube_targets.txt`)를 순회하며, 각 영상에 대해 **'좋아요(Like)'**를 누르고, 영상 내용에 걸맞은 **'자연스러운 1줄짜리 댓글'**을 자동으로 작성합니다.
- 타 채널과의 상호작용을 통해 브랜드(또는 계정)의 인지도를 안전한 방식으로 높이는 것이 목표입니다.

## 2. 작업 폴더 구조 및 입출력 (File Organization & I/O)
- **입력 (Inputs)**: `youtube_targets.txt` (명시된 YouTube URL 리스트 최상단 파일)
- **출력 (Outputs)**: 콘솔 실행 로그 및 YouTube 실제 계정 활동
- **설정 파일 (Config)**: 
  - `.env`에 `GEMINI_API_KEY` 설정
  - 프로젝트 폴더 최상단에 `credentials.json` (Google Cloud Platform 
OAuth 2.0 클라이언트 인증서) 필수 포함.
  - 실행 시 `token.json`이 생성되어 향후 재인증을 생략함.
- **실행 스크립트 (Scripts)**: `execution/youtube_automator.py`

## 3. 핵심 규칙 & 스팸 방지 (Core Principles & Anti-Spam)
- **절대 남용 금지**: YouTube의 알고리즘은 반복적이고 패턴화된 작업을 스팸으로 즉각 인식합니다.
- **안전한 시간 지연 (Backoff/Delay)**: 각 영상(1개 타겟) 작업이 성공한 후, **반드시 10분에서 20분 사이의 무작위 대기 시간(time.sleep)을 가져야 합니다.** 
- **맥락 인지 댓글 (Contextual Commenting)**: Gemini AI를 통해 해당 영상의 '제목'과 '설명' 전문을 던져준 뒤, 그에 맞장구치는 형태의 자연스러운 문형 1가지를 생성해 사용합니다.
- **일일 할당량(Quota)**: YouTube Data API v3 기본 일일 한도는 10,000 Quota입니다. 댓글 1건 작성 시 50, 좋아요 1건 시 50이 소모됩니다. 하루 50건 이내의 안전한 작업을 권장합니다.

## 4. 작동 방식 (Operation)
1. 사용자가 타겟 URL들을 `youtube_targets.txt`에 기록.
2. `python execution/youtube_automator.py` 실행.
3. 봇이 `credentials.json`을 읽어 사용자 대신 YouTube API에 접근.
4. 리스트에서 영상을 얻어오고, Gemini를 거쳐 댓글 문구를 생성한 후 전송.
5. 설정된 시간만큼 휴식한 후 다음 타겟을 향해 반복.
