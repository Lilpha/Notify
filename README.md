# 대학 공지사항 Discord 알림 봇 (Notify)

한림대학교의 주요 공지사항을 실시간으로 수집하여 Discord 채널로 전송하는 파이썬 기반 알림 서비스입니다.

## 주요 기능

- **다중 사이트 모니터링**: 현재 8개 웹사이트를 동시에 감시
  - 소프트웨어학부, SW중심사업단, 학생생활관, 일반공지, 산학협력단, 장학 공지, 학사 공지, SW취업정보
- **정밀한 공지 수집**: `requests`와 `BeautifulSoup4`를 이용한 빠르고 정확한 데이터 추출
  - **제목 추출 최적화**: 말머리나 라벨에 구애받지 않고 실제 공지 제목 전체를 정확히 파싱 (ID별 제목 식별력 강화, `[카테고리]` 접두사 자동 추가)
- **비동기 큐 기반 전송**: 백그라운드 스크래퍼가 수집한 새 공지는 Discord 전송 큐(`Queue`)에 적재된 후 순차적으로 전송되어, Discord API 전송 제한(Rate Limit)을 유연하게 방지합니다.
- **다중 채널 브로드캐스트**: `config.json` 설정을 통해 여러 Discord 채널(`channel_ids`)에 동시에 알림을 보낼 수 있습니다.
- **스마트 통계 시스템**: 실시간으로 오늘/전체 발송 통계 관리 및 자정 자동 초기화 (`/stats` 실행 시 실시간 체크)
- **Discord 알림**: 새 공지 발견 시 임베드(Embed) 형식으로 즉시 전송
- **유연한 설정**: 개별 전송(본문 포함) / 통합 전송(목록형) 모드 지원
- **시스템 모니터링**: 서버/라즈베리파이의 리소스 상태(CPU 사용량, 온도, 메모리, 프로세스 상태 등)를 Discord 슬래시 명령어로 실시간 확인

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
├── install-service.sh   # systemd 서비스 자동 설치 스크립트
├── notify-bot.service   # systemd 서비스 설정 템플릿 파일
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
| `/status` | 봇 가동 시간, 스크래퍼 상태, 대기 중인 큐 개수, 마지막/다음 체크 예정 시간 확인 |
| `/forcescan` | [전체/사이트 선택] 쿨타임 없이 즉시 공지사항 체크 실행 (전체, 소프트웨어학부, SW중심사업단, 학생생활관, 일반공지, 산학협력단, 장학 공지, 학사 공지, SW취업정보 중 선택 가능) |
| `/stats` | 오늘/전체 공지 발송 통계 확인 (자정 자동 초기화 로직 적용) |
| `/noticetype` | 알림 방식 변경 (개별 전송: 본문 일부 요약 및 개별 임베드 / 통합 전송: 새 공지 제목 링크 목록) |
| `/noticesettings` | 현재 설정된 알림 채널 목록 및 전송 모드 확인 |
| `/scaninterval` | 현재 스캔 주기(초) 확인 및 실시간 변경 (최소 30초 ~ 최대 3600초) |
| `/system` | CPU 사용률/코어, 메모리 사용량, 디스크 용량, 부하 평균(Load Average) 확인 |
| `/hardware` | [라즈베리파이/서버 전용] 온도, 전압, 클럭 및 쓰로틀링 상태 확인 |
| `/process` | 봇 프로세스의 PID, 메모리 점유(MB), CPU 사용률, 스레드 개수, 가동 시간 확인 |
| `/network` | 로컬 IP, 인터페이스 종류, 데이터 송수신량 확인 |
| `/errors` | 최근 발생한 스크래핑 에러 로그(최대 5개) 확인 |
| `/ping` | 봇의 응답 속도 및 네트워크 지연 상태(Latency) 확인 |

## 서버/라즈베리파이 배포 가이드 (systemd)

백그라운드에서 24시간 안정적으로 구동하고 시스템 재부팅 시 자동 시작하기 위해 `systemd` 서비스를 설정합니다. 리포지토리에 포함된 설치 스크립트를 사용하여 간편하게 설치할 수 있습니다.

### 1. 서비스 자동 설치
```bash
# 스크립트 실행 권한 부여
chmod +x install-service.sh

# 서비스 설치 및 자동 실행 등록 스크립트 작동
./install-service.sh
```

### 2. 수동 관리 명령어
```bash
# 서비스 상태 확인
sudo systemctl status notify-bot.service

# 서비스 재시작 (소스 코드 수정 후 반영 시 필요)
sudo systemctl restart notify-bot.service

# 서비스 정지
sudo systemctl stop notify-bot.service

# 서비스 로그(출력 및 에러) 실시간 확인
tail -f logs/bot_nohup.log
# 또는 systemd 저널 확인
journalctl -u notify-bot.service -n 50 -f
```

## 작동 원리 및 특징

1. **정확한 데이터 추출**: 게시판의 다양한 말머리나 라벨(`.cate-name`)이 존재하더라도 `strong` 및 `a` 태그 내부 텍스트를 정밀하게 파싱하여 `[카테고리] 공지제목` 형태로 깔끔하게 정보를 가공합니다.
2. **비차단 스케줄링**: `APScheduler`를 백그라운드 스레드에서 운용하므로 봇의 명령어 응답(Slash Commands)이나 시스템 통계 조회가 지연되지 않습니다.
3. **ID 기반 추적**: 각 사이트별로 `last_id_*.txt` 파일을 통해 마지막으로 전송 완료된 공지의 고유 ID를 관리함으로써 봇이 재시작되더라도 중복 메시지가 발송되지 않습니다.
4. **API Rate Limit 예방**: 비동기 전송 큐 및 사이트별 요청 딜레이(2초)를 통해 디스코드 서버 및 대학교 웹사이트에 부하를 주지 않도록 정교하게 설계되었습니다.
5. **실시간 통계**: `/stats` 호출 시 현재 날짜를 실시간 체크하여 날짜가 변경되었을 경우 "오늘 전송 공지 수" 카운트를 즉시 초기화하여 항상 올바른 현황을 유지합니다.

## 주의사항 및 문제 해결

- **IP 차단 방지**: 너무 짧은 스캔 주기는 대학 서버 측에서 봇의 IP를 차단하는 원인이 됩니다. 기본적으로 30초 이상의 간격을 권장합니다.
- **오류 모니터링**: 대학 홈페이지 구조가 바뀌거나 일시적인 접속 오류가 발생하면 `/errors` 명령어를 통해 에러 로그를 손쉽게 추적할 수 있으며, 관련 사항은 `logs/error.log` 파일에 로깅됩니다.
- **Discord 권한 오류**: 봇이 채널에 알림 메시지를 보내지 못하는 경우, 해당 디스코드 채널 권한 설정에서 `메시지 보내기(Send Messages)`, `링크 첨부(Embed Links)` 권한이 부여되어 있는지 확인하세요.

## 기술 스택
- **언어**: Python 3.8+
- **라이브러리**: `discord.py`, `requests`, `BeautifulSoup4`, `APScheduler`, `psutil`

---
**최근 업데이트**: 2026. 07. 19.  
**버전**: 1.2.0 (장학 공지, 학사 공지, SW취업정보 스크래핑 추가 및 forcescan 명령어 기능 보완, README 최신화)
