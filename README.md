# 대학 공지사항 Discord 알림 봇

한림대학교 공지사항을 자동으로 수집하여 Discord로 알림을 전송하는 봇입니다.

## 주요 기능

- **다중 사이트 모니터링**: 3개 웹사이트를 동시에 모니터링
  - 소프트웨어학부
  - SW중심사업단
  - 학생생활관
- **자동 공지 수집**: 60초마다 새로운 공지사항 자동 확인
- **Discord 알림**: 새 공지 발견 시 Discord 채널로 즉시 전송
- **유연한 전송 방식**: 개별 전송 / 통합 전송 선택 가능
- **슬래시 커맨드**: Discord에서 실시간 설정 변경
- **ID 추적**: 사이트별 독립적인 마지막 확인 ID 관리

## 파일 구조

```
notify/
├── main.py              # Discord 봇 메인 파일
├── scraper.py           # 공지사항 스크래핑 모듈
├── logger_config.py     # 로깅 시스템 설정
├── .env                 # 환경 변수 (토큰, ID 등) [주의] Git에 포함 안됨
├── .env.example         # 환경 변수 예제 파일
├── .gitignore           # Git 제외 파일 목록
├── config.json          # 봇 설정 파일 (자동 생성)
├── last_id_sw.txt       # 소프트웨어학부 마지막 ID
├── last_id_hlsw.txt     # SW중심사업단 마지막 ID
├── last_id_dorm.txt     # 학생생활관 마지막 ID
├── logs/                # 로그 파일 디렉토리 (자동 생성)
│   ├── bot.log         # 전체 로그
│   └── error.log       # 에러 전용 로그
├── messageFormat.md     # 메시지 포맷 참고 문서
└── README.md            # 본 문서
```

## 설치 가이드

### 빠른 시작 (Quick Start)

```powershell
# 1. 저장소 클론 또는 다운로드
git clone <repository-url>
cd notify

# 2. 가상환경 설정 및 패키지 설치
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 3. 환경 변수 설정
copy .env.example .env
# .env 파일을 열어 실제 값으로 수정

# 4. 실행
python main.py
```

### 상세 설치 가이드

### 1. 필수 요구사항

- Python 3.8 이상
- Chrome 브라우저 (Selenium용)
- Discord Bot Token
- Discord 서버 관리자 권한

### 2. 패키지 설치

```powershell
# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 필수 패키지 설치
pip install -r requirements.txt

# 또는 수동 설치
# pip install discord.py selenium apscheduler python-dotenv
```

### 3. Chrome WebDriver 설치

Selenium이 자동으로 ChromeDriver를 관리하도록 설정되어 있습니다.
Chrome 브라우저만 설치되어 있으면 자동으로 작동합니다.

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력:

```env
# Discord Bot 설정
DISCORD_TOKEN=여기에_봇_토큰_입력
GUILD_ID=여기에_서버_ID_입력

# 기본 채널 ID (선택사항)
DEFAULT_CHANNEL_ID=여기에_채널_ID_입력
```

**[주의]**: `.env` 파일은 절대 공개 저장소에 업로드하지 마세요!

### 5. Discord Bot 설정

#### 5.1 Bot 생성
1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. "New Application" 클릭
3. 봇 이름 입력 후 생성
4. "Bot" 메뉴로 이동
5. "Add Bot" 클릭
6. TOKEN 복사 후 `.env` 파일의 `DISCORD_TOKEN`에 입력

#### 5.2 Bot 권한 설정
Bot 메뉴에서 다음 권한 활성화:
- Send Messages
- Embed Links
- Read Message History
- Use Slash Commands

#### 5.3 Bot 초대
1. "OAuth2" > "URL Generator" 메뉴
2. Scopes: `bot`, `applications.commands` 선택
3. Bot Permissions: `Send Messages`, `Embed Links` 선택
4. 생성된 URL로 서버에 봇 초대

#### 5.4 ID 확인 방법
**서버 ID (GUILD_ID):**
1. Discord 설정 > 고급 > 개발자 모드 활성화
2. 서버 아이콘 우클릭 > "서버 ID 복사"
3. `.env` 파일의 `GUILD_ID`에 입력

**채널 ID (DEFAULT_CHANNEL_ID):**
1. 알림받을 채널 우클릭 > "채널 ID 복사"
2. `.env` 파일의 `DEFAULT_CHANNEL_ID`에 입력

## 실행 방법

### 기본 실행
```powershell
python main.py
```

### 백그라운드 실행 (Windows)
```powershell
Start-Process -NoNewWindow python main.py
```

### 실행 확인
정상 실행 시 다음과 같은 로그가 출력됩니다:
```
Starting Discord Bot...
Bot will stay active and process notices from scraper
[Scraper] Starting notice monitor...
[Scraper] Checking every 60 seconds...
Discord Bot logged in as YourBot#1234
Current mode: Individual
[Queue Monitor] Started
```

## 설정 (config.json)

첫 실행 시 자동으로 생성되며, 수동 수정 가능합니다.

```json
{
  "send_individually": false,
  "channel_id": 952828252911706153
}
```

| 키 | 설명 | 값 |
|---|---|---|
| `send_individually` | 전송 방식 | `true`: 개별 전송<br>`false`: 통합 전송 |
| `channel_id` | 알림 채널 ID | Discord 채널 ID (숫자) |

## Discord 슬래시 커맨드

봇 실행 중 Discord에서 다음 명령어 사용 가능:

### 기본 설정 명령어

#### `/noticetype`
공지사항 전송 방식 변경
- **통합 전송**: 여러 공지를 한 메시지에 표시
- **개별 전송**: 공지 하나당 메시지 하나씩 전송

#### `/noticesettings`
현재 알림 설정 확인
- 전송 방식 (개별/통합)
- 알림 채널 정보

### 모니터링 & 디버깅 명령어

#### `/status`
봇의 전체 상태를 확인
- 봇 가동 시간
- 스크래퍼 활성화 상태
- 큐 상태 (대기 중인 공지 수)
- 마지막 체크 시간
- 다음 체크 예정 시간

#### `/lastcheck`
최근 스크래핑 정보 확인
- 마지막 체크 시간 (몇 분 전)
- 각 사이트별 마지막 확인 공지 ID

#### `/forcescan`
즉시 사이트 체크 실행 (60초 대기 없이)
- **전체 사이트**: 모든 사이트 체크
- **개별 사이트**: 소프트웨어학부, SW중심사업단, 학생생활관 중 선택

#### `/stats`
공지사항 전송 통계 확인
- 총 전송한 공지 수
- 오늘 전송한 공지 수
- 사이트별 전송 공지 수

#### `/errors`
최근 발생한 에러 확인
- 최근 5개 에러 로그 표시
- 발생 시간, 사이트, 에러 내용

#### `/ping`
봇 응답 시간 확인
- 지연시간 (ms)
- 네트워크 상태 표시

#### `/logs`
최근 로그 파일 내용 확인
- **lines**: 읽을 라인 수 (1-100, 기본 30)
- **log_type**: 전체 로그 또는 에러만
- Discord에서 직접 로그 확인 가능

## 작동 원리

### 1. 공지 수집 (scraper.py)
- Selenium으로 대학 공지사항 페이지 접속
- 최신 공지 ID와 저장된 마지막 ID 비교
- 새로운 공지 발견 시 데이터 수집
  - 공지 번호
  - 제목
  - 링크
  - 작성일
  - 사이트 이름

### 2. Discord 전송 (main.py)
- scraper에서 큐(Queue)에 공지 추가
- Discord 봇이 큐 모니터링
- 새 공지 발견 시 설정에 따라 전송

### 3. ID 추적
- 각 사이트별 `last_id_*.txt` 파일에 마지막 확인 ID 저장
- 재시작 후에도 중복 알림 방지
- ID 리셋 자동 감지 (사이트 새 학기 초기화 등)

## 모니터링 대상 사이트

### 소프트웨어학부
- URL: `https://sw.hallym.ac.kr/sw/3152/subview.do`
- ID 파일: `last_id_sw.txt`

### SW중심사업단
- URL: `https://www.hallym.ac.kr/hlsw/3971/subview.do`
- ID 파일: `last_id_hlsw.txt`

### 학생생활관
- URL: `https://dorm.hallym.ac.kr/dorm/5150/subview.do`
- ID 파일: `last_id_dorm.txt`

## 커스터마이징

### 사이트 추가/제거

`scraper.py`의 `monitors` 리스트 수정:

```python
monitors = [
    NoticeMonitor(
        site_name="표시될_이름",
        url="공지사항_페이지_URL",
        id_file="last_id_파일명.txt"
    ),
    # 추가 사이트...
]
```

### 검사 주기 변경

`main.py` 200번 줄 근처:

```python
scheduler.add_job(
    job_wrapper, 
    'interval', 
    seconds=60,  # 원하는 초 단위로 변경
    max_instances=1,
    coalesce=True
)
```

### 사이트 간 딜레이 조정

`scraper.py` 158번 줄 근처:

```python
if i > 0:
    time.sleep(3)  # 원하는 초 단위로 변경
```

## 주의사항

### 1. 환경 변수 보안
- **`.env` 파일을 절대 공개 저장소에 업로드 금지**
- `.gitignore`에 `.env`가 포함되어 있는지 확인
- 토큰이 노출되면 즉시 Discord Developer Portal에서 재생성
- `.env` 파일은 로컬에만 보관
- Git에 실수로 추가했다면 즉시 제거:
  ```bash
  git rm --cached .env
  git commit -m "Remove .env file"
  ```

### 2. 웹사이트 변경
- 대학 웹사이트 구조 변경 시 scraper 수정 필요
- CSS 선택자가 변경될 수 있음

### 3. 접속 제한
- 과도한 요청은 IP 차단 가능
- 기본 60초 간격 권장
- 사이트 간 3초 딜레이 설정됨

### 4. 프로세스 관리
- Ctrl+C로 정상 종료 가능
- 비정상 종료 시 zombie 프로세스 확인
- Windows 서비스 등록 권장 (24시간 운영 시)

## 문제 해결

### 봇이 로그인하지 못함
- Discord Token 확인
- 인터넷 연결 확인
- Discord API 상태 확인

### 공지가 수집되지 않음
- 웹사이트 접속 가능 여부 확인
- Chrome 브라우저 설치 확인
- 방화벽/보안 프로그램 확인

### Discord 메시지가 전송되지 않음
- 채널 ID 확인
- 봇 권한 확인 (Send Messages)
- 봇이 해당 채널에 접근 가능한지 확인

### 중복 알림 발생
- `last_id_*.txt` 파일 삭제 후 재시작
- 파일 권한 확인 (읽기/쓰기 가능)

### Connection Reset Error
- 사이트 접속 간격 늘리기 (60초 → 120초)
- 사이트 간 딜레이 늘리기 (3초 → 5초)

## 개발 정보

### 기술 스택
- **Python 3.8+**
- **discord.py**: Discord Bot API
- **Selenium**: 웹 스크래핑
- **APScheduler**: 주기적 작업 스케줄링
- **python-dotenv**: 환경 변수 관리
- **asyncio**: 비동기 처리
- **threading**: 멀티스레딩
- **logging**: 파일 기반 로깅 시스템

### 아키텍처
```
┌─────────────────┐
│   Discord Bot   │ ← asyncio event loop
│   (main.py)     │
└────────┬────────┘
         │ Queue (thread-safe)
         │
┌────────▼────────┐
│   Scraper       │ ← background thread
│  (scraper.py)   │
└────────┬────────┘
         │ APScheduler (60s)
         │
    ┌────▼─────┐
    │ Selenium │
    │ Chrome   │
    └──────────┘
```

## 라이센스

본 프로젝트는 교육 및 개인 사용 목적으로 제작되었습니다.

## 기여

버그 리포트 및 개선 제안은 언제든 환영합니다.

---

**제작일**: 2026년 2월  
**버전**: 1.0.0  
**문의**: 프로젝트 관리자
