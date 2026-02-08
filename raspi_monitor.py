"""
라즈베리파이 시스템 모니터링 모듈
CPU, 메모리, 온도 등 시스템 상태 확인
"""
import psutil
import os
import platform
import subprocess
from datetime import timedelta
from logger_config import get_logger

logger = get_logger("RaspiMonitor")

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
            load_avg = os.getloadavg()
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

def get_raspi_info():
    """라즈베리파이 전용 정보 (온도, 쓰로틀링 등)"""
    try:
        info = {}
        
        # CPU 온도
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000
                info['cpu_temp'] = round(temp, 1)
                logger.debug(f"CPU temperature: {temp}°C")
        except FileNotFoundError:
            info['cpu_temp'] = None
            logger.warning("CPU temperature file not found (not running on Raspberry Pi?)")
        
        # vcgencmd를 통한 추가 정보
        try:
            # GPU 온도
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                gpu_temp = result.stdout.strip().replace("temp=", "").replace("'C", "")
                info['gpu_temp'] = float(gpu_temp)
            
            # 쓰로틀링 상태
            result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                throttled = result.stdout.strip().replace("throttled=", "")
                info['throttled'] = throttled
                info['throttled_status'] = parse_throttled(throttled)
            
            # 전압
            result = subprocess.run(['vcgencmd', 'measure_volts'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                volts = result.stdout.strip().replace("volt=", "").replace("V", "")
                info['voltage'] = float(volts)
            
            # 클럭 속도
            result = subprocess.run(['vcgencmd', 'measure_clock', 'arm'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                clock = result.stdout.strip().replace("frequency(45)=", "")
                info['clock_mhz'] = int(clock) / 1000000
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"vcgencmd not available: {e}")
            info['vcgencmd_available'] = False
        
        # 라즈베리파이 모델 정보
        try:
            with open('/proc/device-tree/model', 'r') as f:
                info['model'] = f.read().strip('\x00')
        except FileNotFoundError:
            info['model'] = platform.machine()
        
        logger.debug(f"Raspberry Pi info collected: {info}")
        return info
        
    except Exception as e:
        logger.error(f"Failed to get Raspberry Pi info: {e}", exc_info=True)
        return None

def parse_throttled(hex_value):
    """쓰로틀링 상태 해석"""
    try:
        value = int(hex_value, 16)
        states = []
        
        if value & (1 << 0):
            states.append("Under-voltage detected")
        if value & (1 << 1):
            states.append("Arm frequency capped")
        if value & (1 << 2):
            states.append("Currently throttled")
        if value & (1 << 3):
            states.append("Soft temperature limit active")
        if value & (1 << 16):
            states.append("Under-voltage has occurred")
        if value & (1 << 17):
            states.append("Arm frequency capping has occurred")
        if value & (1 << 18):
            states.append("Throttling has occurred")
        if value & (1 << 19):
            states.append("Soft temperature limit has occurred")
        
        return states if states else ["OK"]
    except:
        return ["Unknown"]

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
                if addr.family == 2:  # AF_INET (IPv4)
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

# 라즈베리파이 환경 체크
def is_raspberry_pi():
    """라즈베리파이에서 실행 중인지 확인"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            return 'raspberry pi' in model.lower()
    except:
        return False

# 모듈 로드 시 로그
if is_raspberry_pi():
    logger.info("Running on Raspberry Pi")
else:
    logger.info("Not running on Raspberry Pi (some features may be unavailable)")
