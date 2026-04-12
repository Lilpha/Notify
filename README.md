# 대학 공지사항 Discord 알림 봇 (Notify)

한림대학교의 주요 공지사항을 실시간으로 수집하여 Discord 채널로 전송하는 파이썬 기반 알림 서비스입니다.

## 주요 기능

- **다중 사이트 모니터링**: 현재 5개 웹사이트를 동시에 감시
  - 소프트웨어학부
  - SW중심사업단
  - 학생생활관
  - 일반공지 (대학본부)
  - 산학협력단 (신규 추가)
- **정밀한 공지 수집**: `requests`와 `BeautifulSoup4`를 이용한 빠르고 정확한 데이터 추출
  - **제목 추출 최적화**: 말머리나 라벨에 구애받지 않고 실제 공지 제목 전체를 정확히 파싱
- **스마트 통계 시스템**: 실시간으로 오늘/전체 발송 통계 관리 및 자정 자동 초기화
- **Discord 알림**: 새 공지 발견 시 임베드(Embed) 형식으로 즉시 전송
- **유연한 설정**: 개별 전송(본문 포함) / 통합 전송(목록형) 모드 지원
- **시스템 모니터링**: 라즈베리파이 또는 서버의 리소스 상태(CPU, 온도, 메모리 등)를 Discord에서 확인

## 파일 구조

```
notify/
├── main.py              # Discord 봇 & 서비스 제어 메인 로직
├── scraper.py           # 공지사항 스크래핑 및 모니터링 모듈
├── logger_config.py     # 로깅 시스템 설정 (bot.log, error.log)
├── raspi_monitor.py     # 라즈베리파이/시스템 상태 측정 모듈
├── server_monitor.py    # 리눅스 서버용 모니터링 모듈 (선택)
├── .env                 # 환경 변수 (토큰, ID 등) - Git 제외 대상
├── .env.example         # 환경 변수 설정 가이드
├── config.json          # 봇 동작 설정 (자동 생성 및 저장)
├── last_id_*.txt        # 사이트별 마지막 확인 공지 ID 저장 파일
├── logs/                # 로그 파일 디렉토리
└── requirements.txt     # 필요 패키지 목록
```

## 설치 및 실행

### 1. 환경 준비
```bash
# 저장소 클론
git clone <repository-url>
cd notify

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 설정 (`.env`)
`.env` 파일을 생성하고 다음 정보를 입력합니다:
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
DEFAULT_CHANNEL_ID=your_channel_id_here
```

### 3. 실행
```bash
python3 main.py
```

## Discord 주요 명령어

| 명령어 | 설명 |
|---|---|
| `/status` | 봇 가동 시간, 스크래퍼 상태, 다음 체크 시간 확인 |
| `/forcescan` | [전체/사이트별] 즉시 공지사항 체크 실행 |
| `/stats` | 오늘/전체 공지 발송 통계 확인 (자정 자동 초기화) |
| `/noticetype` | 알림 전송 방식 변경 (개별 전송 / 통합 전송) |
| `/scaninterval` | 현재 스캔 주기 확인 및 변경 |
| `/system` | CPU, 메모리, 디스크 등 시스템 리소스 확인 |
| `/hardware` | [라즈베리파이] 온도, 전압, 쓰로틀링 상태 확인 |
| `/errors` | 최근 발생한 스크래핑 에러 로그 확인 |

## 작동 원리 및 특징

### 1. 정확한 데이터 추출 (제목 파싱)
기존의 `strong` 태그 의존 방식에서 벗어나, 게시판 목록의 `a` 태그 내부 텍스트를 직접 추출하도록 개선되었습니다. 이를 통해 말머리(`[공지]`, `[모집중]`)가 중복되더라도 실제 제목을 정확하게 구분하여 알림을 보냅니다.

### 2. 실시간 통계 초기화
`/stats` 명령어 실행 시 현재 시간을 체크하여 날짜가 지났을 경우 "오늘 전송" 카운트를 즉시 0으로 초기화합니다. 공지가 없는 날에도 통계 데이터의 정확성을 보장합니다.

### 3. 효율적인 리소스 사용
- **비차단 방식**: `APScheduler`를 이용해 백그라운드에서 스크래핑을 수행하며, Discord 봇의 응답성에 영향을 주지 않습니다.
- **짧은 스캔 주기**: 기본 15초 간격으로 설정되어 있어 신규 공지를 매우 빠르게 전송합니다. (조정 가능)

## 모니터링 대상 상세

- **소프트웨어학부**: `https://sw.hallym.ac.kr/sw/3152/subview.do`
- **SW중심사업단**: `https://www.hallym.ac.kr/hlsw/3971/subview.do`
- **학생생활관**: `https://dorm.hallym.ac.kr/dorm/5150/subview.do`
- **일반공지**: `https://sw.hallym.ac.kr/hallym/1136/subview.do`
- **산학협력단**: `https://www.hallym.ac.kr/sanhak/5063/subview.do`

## 기술 스택
- **언어**: Python 3.8+
- **라이브러리**: 
  - `discord.py` (Discord API 인터페이스)
  - `requests` (웹 페이지 요청)
  - `BeautifulSoup4` (HTML 파싱)
  - `APScheduler` (작업 스케줄링)
  - `psutil` (시스템 모니터링)

---
**Last Updated**: 2026. 04. 12.  
**Version**: 1.1.0 (제목 추출 로직 개선 및 사이트 추가 반영)
