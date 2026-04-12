"""
리눅스 서버(데스크탑/서버 OS) 모니터링 모듈
CPU, 메모리, 온도 등 시스템 상태 확인
"""
import psutil
import os
import platform
from datetime import timedelta
from logger_config import get_logger

logger = get_logger("ServerMonitor")

def get_system_info():
    """시스템 전체 상태 정보"""
    try:
        # CPU 정보
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # 메모리 정보
        memory = psutil.virtual_memory()
        
        # 디스크 정보
        disk = psutil.disk_usage('/')
        
        # 시스템 부팅 시간
        boot_time = psutil.boot_time()
        uptime = timedelta(seconds=int(psutil.time.time() - boot_time))
        
        # 로드 평균
        try:
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
            else:
                load_avg = (0, 0, 0)
        except (OSError, AttributeError):
            load_avg = (0, 0, 0)
        
        info = {
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count,
                'freq_current': cpu_freq.current if cpu_freq else 0,
                'freq_max': cpu_freq.max if cpu_freq else 0,
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used,
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent,
            },
            'uptime': str(uptime),
            'load_avg': load_avg,
        }
        
        logger.debug(f"System info collected: CPU={cpu_percent}%, MEM={memory.percent}%")
        return info
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}", exc_info=True)
        return None

def get_server_info():
    """리눅스 서버 전용 정보 (온도, 기본 OS 모델 등)"""
    try:
        info = {}
        
        # CPU 온도 (Linux 환경 범용)
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                info['cpu_temp'] = None
                logger.warning("No temperature sensors found.")
            else:
                # 일반적으로 coretemp, acpitz 혹은 hwmon 등을 탐색
                for name, entries in temps.items():
                    if entries:
                        # 첫 번째 항목의 현재 온도를 기본으로 가져옴
                        info['cpu_temp'] = round(entries[0].current, 1)
                        logger.debug(f"CPU temperature: {info['cpu_temp']}°C ({name})")
                        break
        except Exception as e:
            info['cpu_temp'] = None
            logger.warning(f"Error reading temperature sensors: {e}")
            
        # 서버 명/OS 모델 정보
        try:
            info['model'] = f"{platform.system()} {platform.release()} ({platform.machine()})"
        except Exception:
            info['model'] = platform.machine()
            
        logger.debug(f"Server info collected: {info}")
        return info
        
    except Exception as e:
        logger.error(f"Failed to get Server info: {e}", exc_info=True)
        return None

def get_process_info():
    """현재 봇 프로세스 정보"""
    try:
        process = psutil.Process(os.getpid())
        
        # 프로세스 메모리
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # CPU 사용률 (1초간 측정)
        cpu_percent = process.cpu_percent(interval=1)
        
        # 스레드 수
        num_threads = process.num_threads()
        
        # 프로세스 실행 시간
        create_time = process.create_time()
        runtime = timedelta(seconds=int(psutil.time.time() - create_time))
        
        # Python 정보
        import sys
        python_version = sys.version.split()[0]
        
        info = {
            'memory_mb': round(memory_mb, 2),
            'memory_percent': round(process.memory_percent(), 2),
            'cpu_percent': cpu_percent,
            'threads': num_threads,
            'runtime': str(runtime),
            'python_version': python_version,
            'pid': os.getpid(),
        }
        
        logger.debug(f"Process info collected: MEM={memory_mb:.2f}MB, CPU={cpu_percent}%")
        return info
        
    except Exception as e:
        logger.error(f"Failed to get process info: {e}", exc_info=True)
        return None

def format_bytes(bytes_value):
    """바이트를 읽기 쉬운 형식으로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def get_network_info():
    """네트워크 정보"""
    try:
        info = {}

        # 네트워크 주소
        addrs = psutil.net_if_addrs()
        for interface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family == getattr(psutil.socket, 'AF_INET', 2):  # AF_INET (IPv4)
                    if not addr.address.startswith('127.'):
                        info['local_ip'] = addr.address
                        info['interface'] = interface
                        break

        # 네트워크 통계
        net_io = psutil.net_io_counters()
        info['bytes_sent'] = format_bytes(net_io.bytes_sent)
        info['bytes_recv'] = format_bytes(net_io.bytes_recv)

        logger.debug(f"Network info collected: {info}")
        return info

    except Exception as e:
        logger.error(f"Failed to get network info: {e}", exc_info=True)
        return None

# 범용 리눅스 환경 체크
def is_linux_server():
    """현재 시스템이 리눅스 구동 환경인지 확인"""
    return platform.system() == 'Linux'

# 모듈 로드 시 로그
if is_linux_server():
    logger.info("Running on Linux Server")
else:
    logger.info("Not running on Linux (some features may behave differently)")