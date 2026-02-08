"""
로깅 설정 모듈
모든 활동을 파일과 콘솔에 기록
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 로그 디렉토리 생성
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 로그 파일 경로
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")

def setup_logger(name="NotifyBot"):
    """로거 설정"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 기존 핸들러 제거 (중복 방지)
    if logger.handlers:
        logger.handlers.clear()
    
    # 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러 (INFO 이상)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 파일 핸들러 (모든 로그, 최대 5MB, 5개 백업)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 에러 전용 파일 핸들러 (ERROR 이상)
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    return logger

def get_logger(name="NotifyBot"):
    """로거 가져오기"""
    return logging.getLogger(name)

def get_recent_logs(lines=50, log_type="all"):
    """최근 로그 가져오기
    
    Args:
        lines: 읽을 라인 수
        log_type: "all", "error"
    """
    log_file = ERROR_LOG_FILE if log_type == "error" else LOG_FILE
    
    if not os.path.exists(log_file):
        return "로그 파일이 없습니다."
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)
    except Exception as e:
        return f"로그 읽기 실패: {e}"

def clear_old_logs(days=7):
    """오래된 로그 파일 삭제
    
    Args:
        days: 보관 일수
    """
    if not os.path.exists(LOG_DIR):
        return
    
    now = datetime.now()
    for filename in os.listdir(LOG_DIR):
        filepath = os.path.join(LOG_DIR, filename)
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if (now - file_time).days > days:
                try:
                    os.remove(filepath)
                    print(f"Old log deleted: {filename}")
                except Exception as e:
                    print(f"Failed to delete {filename}: {e}")
