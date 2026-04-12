# 대학 공지사항 Discord 알림 봇 (Notify)

한림대학교의 주요 공지사항을 실시간으로 수집하여 Discord 채널로 전송하는 파이썬 기반 알림 서비스입니다.

## 주요 기능

- **다중 사이트 모니터링**: 현재 5개 웹사이트를 동시에 감시
  - 소프트웨어학부, SW중심사업단, 학생생활관, 일반공지(대학본부), 산학협력단
- **정밀한 공지 수집**: `requests`와 `BeautifulSoup4`를 이용한 빠르고 정확한 데이터 추출
  - **제목 추출 최적화**: 말머리나 라벨에 구애받지 않고 실제 공지 제목 전체를 정확히 파싱 (ID별 제목 식별력 강화)
- **스마트 통계 시스템**: 실시간으로 오늘/전체 발송 통계 관리 및 자정 자동 초기화 (`/stats` 실행 시 실시간 체크)
- **Discord 알림**: 새 공지 발견 시 임베드(Embed) 형식으로 즉시 전송
- **유연한 설정**: 개별 전송(본문 포함) / 통합 전송(목록형) 모드 지원
- **시스템 모니터링**: 라즈베리파이 또는 서버의 리소스 상태(CPU, 온도, 메모리 등)를 Discord에서 확인

## 파일 구조

```
notify/
├── main.py              # Discord 봇 & 서비스 제어 메인 로직
├── scraper.py           # 공지사항 스크래핑 및 모니터링 모듈
├── logger_config.py     # 로깅 시스템 설정 (bot.log, error.log)
├── raspi_monitor.py     # 라즈베리파이 시스템 상태 측정 모듈
├── server_monitor.py    # 리눅스 서버용 모니터링 모듈
├── .env                 # 환경 변수 (토큰, ID 등) [주의] Git 제외 대상
├── .env.example         # 환경 변수 설정 가이드
├── config.json          # 봇 동작 설정 (자동 생성 및 저장)
├── last_id_*.txt        # 사이트별 마지막 확인 공지 ID 저장 파일
├── logs/                # 로그 파일 디렉토리
└── requirements.txt     # 필요 패키지 목록
```

## 설치 가이드

### 1. 필수 요구사항
- Python 3.8 이상
- Discord Bot Token
- Discord 서버(길드) 관리자 권한

### 2. 패키지 설치
```bash
# 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 필수 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (`.env`)
프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력합니다:
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
DEFAULT_CHANNEL_ID=your_channel_id_here
```
**[주의]**: `.env` 파일은 보안상 절대 공개 저장소에 업로드하지 마세요.

### 4. Discord Bot 설정
1. [Discord Developer Portal](https://discord.com/developers/applications)에서 Application 생성
2. **Bot** 메뉴에서 `Message Content Intent`를 활성화
3. **OAuth2 > URL Generator**에서 `bot`, `applications.commands` 스코프와 필요한 권한(`Send Messages`, `Embed Links` 등)을 선택해 봇을 서버에 초대합니다.

## 실행 방법

### 기본 실행
```bash
python3 main.py
```

### 실행 확인 로그
```
Starting Discord Bot...
[Scraper] Starting notice monitor...
[Scraper] Checking every 15 seconds...
Discord Bot logged in as YourBot#1234
[Queue Monitor] Started
```

## Discord 주요 명령어

| 명령어 | 설명 |
|---|---|
| `/status` | 봇 가동 시간, 스크래퍼 상태, 다음 체크 예정 시간 확인 |
| `/forcescan` | [전체/사이트별] 쿨타임 없이 즉시 공지사항 체크 실행 |
| `/stats` | 오늘/전체 공지 발송 통계 확인 (자정 자동 초기화 로직 적용) |
| `/noticetype` | 알림 방식 변경 (개별 전송: 본문 포함 / 통합 전송: 제목 목록) |
| `/noticesettings` | 현재 설정된 알림 채널 및 전송 모드 확인 |
| `/scaninterval` | 현재 스캔 주기(초) 확인 및 실시간 변경 |
| `/system` | CPU, 메모리, 디스크 등 시스템 전체 리소스 상태 확인 |
| `/hardware` | [라즈베리파이 전용] 온도, 전압, 쓰로틀링 상태 확인 |
| `/errors` | 최근 발생한 스크래핑 에러 로그(최대 5개) 확인 |
| `/ping` | 봇의 응답 속도 및 네트워크 상태 확인 |

## 라즈베리파이 배포 가이드 (systemd)

라즈베리파이에서 24시간 안정적으로 구동하기 위해 `systemd` 서비스를 사용하는 것을 권장합니다.

### 1. 서비스 파일 생성
```bash
sudo nano /etc/systemd/system/discord-notice-bot.service
```

### 2. 내용 입력 (경로 수정 필요)
```ini
[Unit]
Description=Discord Notice Bot
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/notify
Environment="PATH=/home/pi/notify/venv/bin"
ExecStart=/home/pi/notify/venv/bin/python /home/pi/notify/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. 서비스 활성화 및 시작
```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-notice-bot.service
sudo systemctl start discord-notice-bot.service
```

## 작동 원리 및 특징

1. **정확한 데이터 추출**: 기존 `strong` 태그 의존 방식에서 `a` 태그 내부 텍스트 직접 추출 방식으로 개선되어, 게시판의 다양한 말머리나 라벨 속에서도 실제 제목을 정확하게 파싱합니다.
2. **비차단 스케줄링**: `APScheduler`를 이용해 백그라운드 스레드에서 스크래핑을 수행하므로, 봇의 명령어 응답(Slash Commands)이 지연되지 않습니다.
3. **ID 기반 추적**: 각 사이트별로 `last_id_*.txt` 파일을 통해 마지막 확인한 공지를 추적하여, 봇 재시작 시에도 중복 알림이 발생하지 않습니다.
4. **실시간 통계**: `/stats` 호출 시 현재 날짜를 체크하여 날짜가 바뀌었을 경우 "오늘 전송" 카운트를 즉시 초기화하여 데이터의 정확성을 유지합니다.

## 주의사항 및 문제 해결

- **IP 차단 방지**: 너무 짧은 스캔 주기는 대학 서버에서 IP 차단을 유발할 수 있습니다. 기본 15초 이상을 권장하며, 사이트 간 딜레이(2초)가 설정되어 있습니다.
- **Connection Reset**: 사이트 접속이 불안정할 경우 `scraper.py`의 사이트 간 `time.sleep` 시간을 늘려보세요.
- **권한 오류**: 봇이 메시지를 보내지 못한다면 디스코드 채널 설정에서 `메시지 보내기` 및 `링크 임베드` 권한이 있는지 확인하세요.

## 기술 스택
- **언어**: Python 3.8+
- **라이브러리**: `discord.py`, `requests`, `BeautifulSoup4`, `APScheduler`, `psutil`

---
**최근 업데이트**: 2026. 04. 12.  
**버전**: 1.1.0 (산학협력단 추가 및 제목 파싱 엔진 고도화)
