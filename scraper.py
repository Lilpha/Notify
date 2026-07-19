import time
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from logger_config import get_logger

# 로거 설정
logger = get_logger("Scraper")

class NoticeMonitor:
    def __init__(self, site_name, url, id_file):
        self.site_name = site_name
        self.url = url
        self.id_file = id_file
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def get_last_id(self):
        if os.path.exists(self.id_file):
            with open(self.id_file, "r") as f:
                content = f.read().strip()
                last_id = int(content) if content else 0
                logger.debug(f"[{self.site_name}] Last ID loaded: {last_id}")
                return last_id
        logger.debug(f"[{self.site_name}] No ID file found, starting from 0")
        return 0

    def set_last_id(self, notice_id):
        with open(self.id_file, "w") as f:
            f.write(str(notice_id))
        logger.info(f"[{self.site_name}] Updated last ID to: {notice_id}")

    def get_notice_content(self, detail_url):
        """개별 게시물 페이지에 접속하여 본문 텍스트를 추출하는 함수"""
        try:
            time.sleep(0.5)  # 서버 부하 방지를 위한 짧은 대기
            response = requests.get(detail_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 한림대 게시판 및 일반적인 게시판의 본문 영역 CSS 클래스 후보군
            content_selectors = [
                ".board-contents", ".b-v-con", ".view-con", 
                ".board-view", ".td-content", ".data-view"
            ]
            
            content_area = None
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break
            
            if content_area:
                # 불필요한 스크립트나 스타일 태그 제거
                for script in content_area(["script", "style"]):
                    script.decompose()
                text = content_area.get_text(separator='\n', strip=True)
                return text if text else "본문 내용이 비어있습니다."
            else:
                return "본문 영역을 찾을 수 없습니다. (웹사이트 구조 확인 필요)"

        except Exception as e:
            logger.error(f"[{self.site_name}] 본문 파싱 에러 ({detail_url}): {e}")
            return f"본문을 불러오는 중 에러가 발생했습니다."

    def scrape_new_notices(self, last_id):
        new_notices = []
        try:
            logger.debug(f"[{self.site_name}] Accessing {self.url}")
            
            # 1. 목록 페이지 요청
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. 공지사항이 아닌 일반 게시물 행 추출
            rows = soup.select("table.board-table tbody tr:not(.notice)")
            
            if not rows:
                logger.warning(f"[{self.site_name}] 게시물을 찾을 수 없습니다.")
                return []

            # 3. 최신 ID 리셋 확인
            if last_id > 0:
                first_row = rows[0]
                first_num_elem = first_row.select_one(".td-num")
                if first_num_elem:
                    first_num_text = first_num_elem.text.strip()
                    if first_num_text.isdigit():
                        current_latest_id = int(first_num_text)
                        if current_latest_id < last_id:
                            logger.warning(f"[{self.site_name}] ID reset detected: {last_id} -> {current_latest_id}")
                            self.set_last_id(current_latest_id)
                            return []

            # 4. 각 행 파싱
            for row in rows:
                num_elem = row.select_one(".td-num")
                if not num_elem:
                    continue
                    
                num_text = num_elem.text.strip()
                if not num_text.isdigit():
                    continue

                notice_id = int(num_text)

                if notice_id > last_id:
                    title_elem = row.select_one(".td-title a")
                    # <strong> 태그에서 실제 제목만 추출 (카테고리/새글 뱃지 제외)
                    if title_elem:
                        strong = title_elem.select_one("strong")
                        cate = title_elem.select_one(".cate-name")
                        cate_text = cate.get_text(strip=True) if cate else ""
                        title = strong.get_text(strip=True) if strong else title_elem.get_text(strip=True)
                        if cate_text:
                            title = f"[{cate_text}] {title}"
                    else:
                        title = "제목 없음"
                    
                    link_elem = row.select_one(".td-title a")
                    raw_link = link_elem.get("href") if link_elem else ""
                    full_link = urljoin(self.url, raw_link)
                    
                    date_elem = row.select_one(".td-date")
                    date = date_elem.text.strip() if date_elem else ""
                    
                    # 새 글인 경우 본문 내용까지 추가로 가져오기
                    logger.info(f"[{self.site_name}] 새 글 발견! 본문 파싱 중... ({notice_id})")
                    content_text = self.get_notice_content(full_link)

                    new_notices.append({
                        "id": notice_id,
                        "title": title,
                        "link": full_link,
                        "date": date,
                        "site": self.site_name,
                        "content": content_text  # 본문 데이터 추가!
                    })
                else:
                    break  # 이미 확인한 ID면 탐색 중지

            new_notices.sort(key=lambda x: x['id'])
            if new_notices:
                logger.info(f"[{self.site_name}] Found {len(new_notices)} new notices")
            return new_notices

        except Exception as e:
            logger.error(f"[{self.site_name}] Error during scraping: {e}", exc_info=True)
            return []

    def check_for_event(self):
        last_id = self.get_last_id()
        logger.debug(f"[{self.site_name}] Starting check, last_id={last_id}")
        new_notices = self.scrape_new_notices(last_id)
        
        if new_notices:
            latest_notice = new_notices[-1]
            self.set_last_id(latest_notice['id'])
            
            for notice in new_notices:
                logger.info(f"[{self.site_name}] New event: {notice['title']}")
            return new_notices
            
        return []

# 모니터링할 사이트 설정
monitors = [
    NoticeMonitor(
        site_name="소프트웨어학부",
        url="https://sw.hallym.ac.kr/sw/3152/subview.do",
        id_file="last_id_sw.txt"
    ),
    NoticeMonitor(
        site_name="SW중심사업단",
        url="https://www.hallym.ac.kr/hlsw/3971/subview.do",
        id_file="last_id_hlsw.txt"
    ),
    NoticeMonitor(
        site_name="학생생활관",
        url="https://dorm.hallym.ac.kr/dorm/5150/subview.do",
        id_file="last_id_dorm.txt"
    ),
    NoticeMonitor(
        site_name="일반공지",
        url="https://sw.hallym.ac.kr/hallym/1136/subview.do",
        id_file="last_id_hallym_msg.txt"
    ),
    NoticeMonitor(
        site_name="산학협력단",
        url="https://www.hallym.ac.kr/sanhak/5063/subview.do",
        id_file="last_id_sanhak.txt"
    ),
    NoticeMonitor(
        site_name="장학 공지",
        url="https://www.hallym.ac.kr/hallym/1135/subview.do",
        id_file="last_id_scholarship.txt"
    ),
    NoticeMonitor(
        site_name="학사 공지",
        url="https://www.hallym.ac.kr/hallym/1134/subview.do",
        id_file="last_id_haksa.txt"
    ),
    NoticeMonitor(
        site_name="SW취업정보",
        url="https://www.hallym.ac.kr/hlsw/3973/subview.do",
        id_file="last_id_swjob.txt"
    )
]

scheduler = BlockingScheduler()

notice_callback = None
time_tracker_callback = None
error_logger_callback = None

def set_notice_callback(callback):
    global notice_callback
    notice_callback = callback

def set_time_tracker(callback):
    global time_tracker_callback
    time_tracker_callback = callback

def set_error_logger(callback):
    global error_logger_callback
    error_logger_callback = callback

def job_wrapper():
    global time_tracker_callback, error_logger_callback
    all_notices = []
    
    logger.info("Starting scheduled job_wrapper")
    
    if time_tracker_callback:
        time_tracker_callback()
    
    for i, monitor in enumerate(monitors):
        try:
            if i > 0:
                time.sleep(2)
            
            event_data = monitor.check_for_event()
            if event_data:
                all_notices.extend(event_data)
        except Exception as e:
            error_msg = str(e)
            if error_logger_callback:
                error_logger_callback(monitor.site_name, error_msg)
            time.sleep(3)
    
    if all_notices and notice_callback:
        try:
            logger.info(f"Sending {len(all_notices)} notices to Discord")
            notice_callback(all_notices)
        except Exception as e:
            logger.error(f"Failed to send to Discord: {e}", exc_info=True)

def force_scan_single(monitor_index):
    if monitor_index < 0 or monitor_index >= len(monitors):
        return "잘못된 사이트 인덱스"
    
    monitor = monitors[monitor_index]
    try:
        event_data = monitor.check_for_event()
        if event_data:
            if notice_callback:
                notice_callback(event_data)
            return f"새 공지 {len(event_data)}개 발견"
        else:
            return "새 공지 없음"
    except Exception as e:
        error_msg = str(e)
        if error_logger_callback:
            error_logger_callback(monitor.site_name, error_msg)
        return f"에러 발생: {error_msg}"

if __name__ == "__main__":
    print("Scraper started in standalone mode")
    scheduler = BlockingScheduler()
    scheduler.add_job(job_wrapper, 'cron', day_of_week='mon-fri', hour='9-19', minute='*/10')
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scraper stopped")