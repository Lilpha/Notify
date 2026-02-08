import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from apscheduler.schedulers.blocking import BlockingScheduler
from logger_config import get_logger

# 로거 설정
logger = get_logger("Scraper")

class NoticeMonitor:
    def __init__(self, site_name, url, id_file):
        self.site_name = site_name
        self.url = url
        self.id_file = id_file
        self.options = Options()
        self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)

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

    def scrape_new_notices(self, last_id):
        driver = webdriver.Chrome(options=self.options)
        new_notices = []
        try:
            logger.debug(f"[{self.site_name}] Accessing {self.url}")
            driver.get(self.url)
            
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.board-table tbody tr:not(.notice)")))
            
            rows = driver.find_elements(By.CSS_SELECTOR, "table.board-table tbody tr:not(.notice)")
            
            # 첫 번째 행(최신 공지)의 ID 확인
            if rows and last_id > 0:
                try:
                    first_row = rows[0]
                    first_num_elem = first_row.find_element(By.CLASS_NAME, "td-num")
                    first_num_text = first_num_elem.text.strip()
                    if not first_num_text:
                        first_num_text = first_num_elem.get_attribute('textContent').strip()
                    
                    if first_num_text.isdigit():
                        current_latest_id = int(first_num_text)
                        # 현재 사이트의 최신 ID가 저장된 last_id보다 작으면
                        # (사이트가 리셋되었거나 잘못된 last_id)
                        if current_latest_id < last_id:
                            logger.warning(f"[{self.site_name}] ID reset detected: {last_id} -> {current_latest_id}")
                            print(f"[{self.site_name}] ID reset detected: {last_id} -> {current_latest_id}")
                            self.set_last_id(current_latest_id)
                            return []  # 이번엔 새 공지 없음으로 처리
                except Exception as e:
                    logger.error(f"[{self.site_name}] Failed to check latest ID: {e}")
                    print(f"[{self.site_name}] Failed to check latest ID: {e}")
            
            for row in rows:
                try:
                    num_elem = row.find_element(By.CLASS_NAME, "td-num")
                    num_text = num_elem.text.strip()
                    
                    if not num_text:
                        num_text = num_elem.get_attribute('textContent').strip()
                    
                    if not num_text.isdigit():
                        continue
                        
                    notice_id = int(num_text)
                    
                    if notice_id > last_id:
                        title = row.find_element(By.CSS_SELECTOR, ".td-title strong").text.strip()
                        link = row.find_element(By.CSS_SELECTOR, ".td-title a").get_attribute("href")
                        date = row.find_element(By.CLASS_NAME, "td-date").text.strip()
                        new_notices.append({
                            "id": notice_id, 
                            "title": title, 
                            "link": link, 
                            "date": date,
                            "site": self.site_name  # 사이트 정보 추가
                        })
                    else:
                        break
                except Exception as row_e:
                    print(f"row parsing error: {row_e}")
                    continue
            new_notices.sort(key=lambda x: x['id'])
            if new_notices:
                logger.info(f"[{self.site_name}] Found {len(new_notices)} new notices")
            return new_notices

        except Exception as e:
            logger.error(f"[{self.site_name}] Error during scraping: {e}", exc_info=True)
            print(f"[{self.site_name}] Error during scraping: {e}")
            return []
        finally:
            try:
                driver.quit()
            except:
                pass  # 드라이버 종료 실패는 무시

    def check_for_event(self):
        last_id = self.get_last_id()
        logger.debug(f"[{self.site_name}] Starting check, last_id={last_id}")
        new_notices = self.scrape_new_notices(last_id)
        
        if new_notices:
            latest_notice = new_notices[-1]
            self.set_last_id(latest_notice['id'])
            
            for notice in new_notices:
                logger.info(f"[{self.site_name}] New event: {notice['title']}")
                print(f"[{self.site_name}] New event: {notice['title']}")
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
    )
]

scheduler = BlockingScheduler()

# Discord 전송 콜백 함수 (main.py에서 설정)
notice_callback = None
time_tracker_callback = None
error_logger_callback = None

def set_notice_callback(callback):
    """main.py에서 콜백 함수를 설정"""
    global notice_callback
    notice_callback = callback

def set_time_tracker(callback):
    """시간 추적 콜백 설정"""
    global time_tracker_callback
    time_tracker_callback = callback

def set_error_logger(callback):
    """에러 로깅 콜백 설정"""
    global error_logger_callback
    error_logger_callback = callback

def job_wrapper():
    global time_tracker_callback, error_logger_callback
    all_notices = []
    
    logger.info("Starting scheduled job_wrapper")
    
    # 스캔 시작 시간 기록
    if time_tracker_callback:
        time_tracker_callback()
    
    # 모든 사이트 확인
    for i, monitor in enumerate(monitors):
        try:
            # 첫 번째 사이트가 아니면 3초 대기 (IP 차단 방지)
            if i > 0:
                time.sleep(3)
            
            event_data = monitor.check_for_event()
            if event_data:
                all_notices.extend(event_data)
        except Exception as e:
            error_msg = str(e)
            print(f"[{monitor.site_name}] Error: {error_msg}")
            # 에러 로깅
            if error_logger_callback:
                error_logger_callback(monitor.site_name, error_msg)
            # 에러 발생 시 5초 대기 후 다음 사이트로
            time.sleep(5)
    
    # 새 공지가 있으면 Discord 전송
    if all_notices and notice_callback:
        try:
            logger.info(f"Sending {len(all_notices)} notices to Discord")
            notice_callback(all_notices)
        except Exception as e:
            logger.error(f"Failed to send to Discord: {e}", exc_info=True)
            print(f"Failed to send to Discord: {e}")
    
    logger.info(f"Job completed, found {len(all_notices)} new notices")

def force_scan_single(monitor_index):
    """특정 사이트만 강제로 체크"""
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

# 단독 실행 시 (테스트용)
if __name__ == "__main__":
    print("Scraper started in standalone mode")
    scheduler = BlockingScheduler()
    scheduler.add_job(job_wrapper, 'interval', seconds=10)
    # 운영용: 평일 9-19시 10분마다 실행
    # scheduler.add_job(job_wrapper, 'cron', day_of_week='mon-fri', hour='9-19', minute='*/10')
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scraper stopped")
        scheduler.shutdown()