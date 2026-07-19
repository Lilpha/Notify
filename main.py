import discord
import asyncio
import json
import os
from discord import app_commands
from queue import Queue, Empty
from threading import Thread
from datetime import datetime, timedelta
import time
from logger_config import setup_logger, get_logger, get_recent_logs
from dotenv import load_dotenv

# 시스템 모니터링 (서버 또는 라즈베리파이)
try:
    from server_monitor import (
        get_system_info, get_server_info as get_hardware_info, get_process_info,
        get_network_info, format_bytes, is_linux_server as is_target_os
    )
    MONITOR_AVAILABLE = True
    MONITOR_TYPE = "Server"
    logger_temp = get_logger("NotifyBot")
    logger_temp.info("Server monitoring module loaded")
except ImportError:
    try:
        from raspi_monitor import (
            get_system_info, get_raspi_info as get_hardware_info, get_process_info,
            get_network_info, format_bytes, is_raspberry_pi as is_target_os
        )
        MONITOR_AVAILABLE = True
        MONITOR_TYPE = "Raspberry Pi"
        logger_temp = get_logger("NotifyBot")
        logger_temp.info("Raspberry Pi monitoring module loaded")
    except ImportError as e:
        MONITOR_AVAILABLE = False
        MONITOR_TYPE = "None"
        logger_temp = get_logger("NotifyBot")
        logger_temp.warning(f"Monitoring generic/raspi modules unavailable: {e}")

# .env 파일 로드
load_dotenv()

# 로거 설정
logger = setup_logger("NotifyBot")

# 설정
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
CONFIG_FILE = "config.json"

# 스크래퍼 실행 주기 설정 (초 단위)
SCAN_INTERVAL_SECONDS = 15  # 15초마다 스크래핑

# 환경 변수 검증
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN not found in .env file")
    raise ValueError("DISCORD_TOKEN is required in .env file")
if not GUILD_ID:
    logger.error("GUILD_ID not found in .env file")
    raise ValueError("GUILD_ID is required in .env file")

logger.info("="*50)
logger.info("Notify Bot Starting...")
logger.info(f"Guild ID: {GUILD_ID}")
logger.info("="*50)

# 공지 큐 (scraper가 여기에 공지를 넣음)
notice_queue = Queue()

# 모니터링용 전역 변수
bot_start_time = None
last_scan_time = None
next_scan_time = None
scraper_thread = None
scraper_scheduler = None
error_log = []  # 최근 에러 로그 (최대 10개)
stats = {
    "total_notices": 0,
    "site_notices": {},  # 사이트별 공지 수
    "today_notices": 0,
    "today_date": datetime.now().date()
}

def load_config():
    """설정 파일 로드"""
    default_channel = os.getenv('DEFAULT_CHANNEL_ID', '')
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 기존 단일 channel_id를 channel_ids 리스트로 변환 (호환성)
            if "channel_id" in config and "channel_ids" not in config:
                config["channel_ids"] = [config["channel_id"]]
                del config["channel_id"]
                save_config(config)
            logger.debug(f"Config loaded: {config}")
            return config
    logger.warning("Config file not found, using defaults")
    return {"send_individually": False, "channel_ids": [int(default_channel)]}

def save_config(config):
    """설정 파일 저장"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(f"Config saved: {config}")

class NoticeBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config = load_config()
    
    async def setup_hook(self):
        # 슬래시 커맨드 동기화
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
    
    async def on_ready(self):
        logger.info(f"Discord Bot logged in as {self.user}")
        logger.info(f"Current mode: {'Individual' if self.config['send_individually'] else 'Combined'}")
        print(f'Discord Bot logged in as {self.user}')
        print(f'Current mode: {"Individual" if self.config["send_individually"] else "Combined"}')
        
        # 공지 큐 모니터링 시작
        logger.info("Starting notice queue monitor...")
        asyncio.create_task(self.process_notice_queue())
    
    async def process_notice_queue(self):
        """큐에서 공지를 가져와 전송"""
        logger.info("Queue monitor started")
        print('[Queue Monitor] Started')
        while True:
            try:
                try:
                    notices = notice_queue.get_nowait()
                    logger.info(f"Processing {len(notices)} notices from queue")
                    print(f"[Queue] Processing {len(notices)} notices...")
                    await self.send_notices(notices)
                    logger.info(f"Successfully sent {len(notices)} notices")
                    print(f"[Queue] Successfully sent {len(notices)} notices")
                    notice_queue.task_done()
                except Empty:
                    pass
            except Exception as e:
                logger.error(f"Queue processing error: {e}", exc_info=True)
                print(f"[Queue] Error: {e}")
                import traceback
                traceback.print_exc()
            await asyncio.sleep(1)
    
    def update_daily_stats():
        """날짜가 바뀌었는지 확인하고 오늘 통계 초기화"""
        global stats
        today = datetime.now().date()
        if stats["today_date"] != today:
            logger.info(f"Date changed: {stats['today_date']} -> {today}, resetting today's count")
            stats["today_date"] = today
            stats["today_notices"] = 0
            return True
        return False

    async def send_notices(self, notices):
        """공지사항을 Discord에 전송"""
        global stats
        
        # 날짜 변경 체크 및 초기화
        NoticeBot.update_daily_stats()
        
        # 통계 업데이트
        stats["total_notices"] += len(notices)
        stats["today_notices"] += len(notices)
        for notice in notices:
            site = notice.get('site', '알 수 없음')
            stats["site_notices"][site] = stats["site_notices"].get(site, 0) + 1
            logger.info(f"Notice from {site}: [{notice['id']}] {notice['title']}")
        
        self.config = load_config()
        channel_ids = self.config.get("channel_ids", [])
        
        if not channel_ids:
            logger.error("No channel IDs configured")
            print("[Error] No channel IDs configured")
            return
        
        # 각 채널에 공지 전송
        for channel_id in channel_ids:
            channel = self.get_channel(channel_id)
            
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                print(f"[Error] Channel {channel_id} not found")
                continue
            
            logger.debug(f"Sending to channel: {channel.name} (ID: {channel.id})")
            
            if self.config["send_individually"]:
                # 방식 1: 공지 하나당 메시지 1개
                for notice in notices:
                    site_name = notice.get('site', '알 수 없음')
                    
                    # 본문 내용 요약 (디스코드 Embed 필드 글자수 제한: 1024자)
                    content = notice.get('content', '본문 내용이 없습니다.')
                    if len(content) > 300:
                        content = content[:300] + "\n\n...(이하 생략)"

                    embed = discord.Embed(
                        title=f"새 공지사항 #{notice['id']}",
                        description=f"**{notice['title']}**\n\n{content}",
                        color=discord.Color.blue(),
                        url=notice['link']
                    )
                    embed.add_field(name="사이트", value=site_name, inline=True)
                    embed.add_field(name="작성일", value=notice['date'], inline=True)
                    embed.add_field(name="번호", value=str(notice['id']), inline=True)
                    await channel.send(embed=embed)
                    await asyncio.sleep(0.5)  # API 제한 방지
            else:
                # 방식 2: 여러 공지를 한번에 통합 (통합 모드일 땐 본문 생략)
                embed = discord.Embed(
                    title=f"새 공지사항 {len(notices)}개",
                    color=discord.Color.green()
                )
                
                for notice in notices:
                    site_name = notice.get('site', '알 수 없음')
                    embed.add_field(
                        name=f"[{site_name}] #{notice['id']} - {notice['date']}",
                        value=f"[{notice['title']}]({notice['link']})",
                        inline=False
                    )
                
                await channel.send(embed=embed)
            
            logger.info(f"Notices sent to channel {channel.name} (ID: {channel_id})")
# Bot 인스턴스 생성
client = NoticeBot()

# ============================================
# 슬래시 커맨드
# ============================================

@client.tree.command(name="noticetype", description="공지사항 전송 방식을 변경합니다")
@app_commands.describe(
    mode="전송 방식 선택"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="통합 전송 (여러 공지를 한 번에)", value="combined"),
    app_commands.Choice(name="개별 전송 (공지 하나당 메시지 하나)", value="individual")
])
async def noticetype(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    logger.info(f"User {interaction.user} changed notice type to {mode.value}")
    config = load_config()
        
    if mode.value == "individual":
        config["send_individually"] = True
        msg = "공지사항 전송방식 변경, 개별 상태.."
    else:
        config["send_individually"] = False
        msg = "공지사항 전송방식 변경, 통합 상태."
    
    save_config(config)
    client.config = config
    
    await interaction.response.send_message(msg, ephemeral=True)

@client.tree.command(name="noticesettings", description="현재 공지 알림 설정을 확인합니다")
async def noticesettings(interaction: discord.Interaction):
    config = load_config()
    
    mode_text = "개별 전송" if config["send_individually"] else "통합 전송"
    
    # 여러 채널을 표시
    channel_ids = config.get("channel_ids", [])
    channels_text = "\n".join([f"<#{ch_id}>" for ch_id in channel_ids]) if channel_ids else "설정된 채널이 없습니다"
    
    embed = discord.Embed(
        title="공지 알림 설정",
        color=discord.Color.blue()
    )
    embed.add_field(name="전송 방식", value=mode_text, inline=False)
    embed.add_field(name="알림 채널", value=channels_text, inline=False)
    embed.set_footer(text="변경하려면 /noticetype 명령어를 사용하세요")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="status", description="봇의 전체 상태를 확인합니다")
async def status(interaction: discord.Interaction):
    global bot_start_time, last_scan_time, next_scan_time, scraper_thread
    
    # 가동 시간 계산
    uptime = datetime.now() - bot_start_time if bot_start_time else timedelta(0)
    uptime_str = str(uptime).split('.')[0]  # 마이크로초 제거
    
    # 스크래퍼 상태
    scraper_status = "활성" if scraper_thread and scraper_thread.is_alive() else "비활성"
    
    # 큐 상태
    queue_size = notice_queue.qsize()
    queue_status = f"{queue_size}개 대기 중" if queue_size > 0 else "비어있음"
    
    # 시간 정보
    last_scan_str = last_scan_time.strftime("%Y-%m-%d %H:%M:%S") if last_scan_time else "아직 없음"
    next_scan_str = next_scan_time.strftime("%Y-%m-%d %H:%M:%S") if next_scan_time else "계산 중..."
    
    embed = discord.Embed(
        title="봇 상태",
        color=discord.Color.green()
    )
    embed.add_field(name="가동 시간", value=uptime_str, inline=False)
    embed.add_field(name="스크래퍼", value=scraper_status, inline=True)
    embed.add_field(name="큐 상태", value=queue_status, inline=True)
    embed.add_field(name="마지막 체크", value=last_scan_str, inline=False)
    embed.add_field(name="다음 체크", value=next_scan_str, inline=False)
    embed.set_footer(text=f"봇 시작: {bot_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="lastcheck", description="최근 스크래핑 정보를 확인합니다")
async def lastcheck(interaction: discord.Interaction):
    global last_scan_time
    
    embed = discord.Embed(
        title="최근 스크래핑 정보",
        color=discord.Color.blue()
    )
    
    # 마지막 체크 시간
    if last_scan_time:
        time_ago = datetime.now() - last_scan_time
        minutes_ago = int(time_ago.total_seconds() / 60)
        embed.add_field(
            name="마지막 체크",
            value=f"{last_scan_time.strftime('%H:%M:%S')} ({minutes_ago}분 전)",
            inline=False
        )
    
    # 각 사이트별 마지막 ID
    try:
        from scraper import monitors
        for monitor in monitors:
            last_id = monitor.get_last_id()
            embed.add_field(
                name=f"{monitor.site_name}",
                value=f"마지막 ID: {last_id}",
                inline=True
            )
    except Exception as e:
        embed.add_field(name="오류", value=f"정보 로드 실패: {e}", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="forcescan", description="즉시 모든 사이트를 체크합니다")
@app_commands.describe(
    site="체크할 사이트 (선택 안하면 전체)"
)
@app_commands.choices(site=[
    app_commands.Choice(name="전체 사이트", value="all"),
    app_commands.Choice(name="소프트웨어학부", value="sw"),
    app_commands.Choice(name="SW중심사업단", value="hlsw"),
    app_commands.Choice(name="학생생활관", value="dorm"),
    app_commands.Choice(name="일반공지", value="hallym_msg"),
    app_commands.Choice(name="산학협력단", value="sanhak"),
    app_commands.Choice(name="장학 공지", value="scholarship")
])
async def forcescan(interaction: discord.Interaction, site: app_commands.Choice[str] = None):
    """강제 스캔 - 즉시 응답하고 백그라운드 실행"""
    logger.info(f"User {interaction.user} requested force scan for site: {site.value if site else 'all'}")
    
    # 즉시 응답 (타임아웃 방지)
    await interaction.response.send_message("🔍 스캔을 시작합니다... (완료되면 알려드립니다)", ephemeral=True)
    
    try:
        from scraper import monitors, force_scan_single, job_wrapper
        
        def run_scan_task():
            """백그라운드에서 스캔 실행"""
            try:
                if site and site.value != "all":
                    site_map = {
                        "sw": 0, 
                        "hlsw": 1, 
                        "dorm": 2, 
                        "hallym_msg": 3, 
                        "sanhak": 4,
                        "scholarship": 5
                    }
                    if site.value in site_map:
                        logger.info(f"Starting force scan for {site.name}")
                        result = force_scan_single(site_map[site.value])
                        # 완료 메시지 전송
                        asyncio.run_coroutine_threadsafe(
                            interaction.followup.send(f"{site.name} 스캔 완료!\n```{result}```", ephemeral=True),
                            client.loop
                        )
                else:
                    logger.info("Starting force scan for all sites")
                    job_wrapper()
                    asyncio.run_coroutine_threadsafe(
                        interaction.followup.send("전체 사이트 스캔 완료!", ephemeral=True),
                        client.loop
                    )
            except Exception as e:
                logger.error(f"Background scan error: {e}", exc_info=True)
                asyncio.run_coroutine_threadsafe(
                    interaction.followup.send(f"스캔 중 오류: {str(e)[:200]}", ephemeral=True),
                    client.loop
                )
        
        # 백그라운드 스레드로 실행
        Thread(target=run_scan_task, daemon=True).start()
        
    except Exception as e:
        logger.error(f"Force scan setup error: {e}", exc_info=True)
        await interaction.followup.send(f"스캔 시작 실패: {e}", ephemeral=True)

@client.tree.command(name="stats", description="공지사항 전송 통계를 확인합니다")
async def stats_command(interaction: discord.Interaction):
    global stats
    
    # 날짜 변경 체크 및 초기화 (실시간 반영)
    update_daily_stats()
    
    embed = discord.Embed(
        title="공지사항 전송 통계",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="총 전송 공지", value=f"{stats['total_notices']}개", inline=True)
    embed.add_field(name="오늘 전송", value=f"{stats['today_notices']}개", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # 빈 필드
    
    # 사이트별 통계
    if stats["site_notices"]:
        for site, count in stats["site_notices"].items():
            embed.add_field(name=f"{site}", value=f"{count}개", inline=True)
    else:
        embed.add_field(name="사이트별 통계", value="아직 전송된 공지가 없습니다", inline=False)
    
    embed.set_footer(text=f"오늘 날짜: {stats['today_date']}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="errors", description="최근 발생한 에러를 확인합니다")
async def errors_command(interaction: discord.Interaction):
    global error_log
    
    embed = discord.Embed(
        title="최근 에러 로그",
        color=discord.Color.red()
    )
    
    if not error_log:
        embed.description = "최근 발생한 에러가 없습니다"
    else:
        # 최근 5개만 표시
        for i, error in enumerate(error_log[-5:], 1):
            time_str = error['time'].strftime("%H:%M:%S")
            embed.add_field(
                name=f"#{i} - {time_str}",
                value=f"**{error['site']}**\n```{error['error'][:100]}```",
                inline=False
            )
    
    embed.set_footer(text=f"총 {len(error_log)}개의 에러 기록됨")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="ping", description="봇의 응답 시간을 확인합니다")
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)  # ms 단위로 변환
    
    embed = discord.Embed(
        title="Pong!",
        description=f"응답 시간: **{latency}ms**",
        color=discord.Color.green() if latency < 100 else discord.Color.orange()
    )
    
    # 상태 표시
    if latency < 100:
        status = f"매우 좋음 {latency}ms"
    elif latency < 200:
        status = f"좋음 {latency}ms"
    elif latency < 500:
        status = f"보통 {latency}ms"
    else:
        status = f"느림 {latency}ms"
    
    embed.add_field(name="상태", value=status, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="scaninterval", description="현재 스캔 주기를 확인합니다")
async def scaninterval(interaction: discord.Interaction):
    global SCAN_INTERVAL_SECONDS
    
    minutes = SCAN_INTERVAL_SECONDS // 60
    seconds = SCAN_INTERVAL_SECONDS % 60
    
    if minutes > 0:
        interval_text = f"{minutes}분 {seconds}초" if seconds > 0 else f"{minutes}분"
    else:
        interval_text = f"{seconds}초"
    
    embed = discord.Embed(
        title="스캔 주기 설정",
        color=discord.Color.blue()
    )
    embed.add_field(name="현재 주기", value=interval_text, inline=True)
    embed.add_field(name="초 단위", value=f"{SCAN_INTERVAL_SECONDS}초", inline=True)
    embed.set_footer(text="변경하려면 /setscaninterval 명령어를 사용하세요")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="setscaninterval", description="스캔 주기를 변경합니다")
@app_commands.describe(
    seconds="스캔 주기 (초 단위, 30~3600)"
)
async def setscaninterval(interaction: discord.Interaction, seconds: int):
    global SCAN_INTERVAL_SECONDS, scraper_scheduler, next_scan_time
    
    logger.info(f"User {interaction.user} requested scan interval change to {seconds}s")
    
    # 유효성 검사
    if seconds < 30:
        await interaction.response.send_message("스캔 주기는 최소 30초 이상이어야 합니다.", ephemeral=True)
        return
    if seconds > 3600:
        await interaction.response.send_message("스캔 주기는 최대 3600초(1시간) 이하여야 합니다.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        old_interval = SCAN_INTERVAL_SECONDS
        SCAN_INTERVAL_SECONDS = seconds
        
        # 스케줄러 재시작
        if scraper_scheduler and scraper_scheduler.running:
            from scraper import job_wrapper
            
            # 기존 작업 제거
            scraper_scheduler.remove_all_jobs()
            
            # 새 주기로 작업 추가
            scraper_scheduler.add_job(
                job_wrapper,
                'interval',
                seconds=SCAN_INTERVAL_SECONDS,
                max_instances=1,
                coalesce=True
            )
            
            # 다음 스캔 시간 업데이트
            next_scan_time = datetime.now() + timedelta(seconds=SCAN_INTERVAL_SECONDS)
            
            logger.info(f"Scan interval changed: {old_interval}s -> {SCAN_INTERVAL_SECONDS}s")
            
            minutes = seconds // 60
            sec = seconds % 60
            if minutes > 0:
                interval_text = f"{minutes}분 {sec}초" if sec > 0 else f"{minutes}분"
            else:
                interval_text = f"{sec}초"
            
            embed = discord.Embed(
                title="스캔 주기 변경 완료",
                color=discord.Color.green()
            )
            embed.add_field(name="이전 주기", value=f"{old_interval}초", inline=True)
            embed.add_field(name="새 주기", value=interval_text, inline=True)
            embed.add_field(name="다음 스캔", value=next_scan_time.strftime("%H:%M:%S"), inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("스크래퍼가 실행 중이 아닙니다.", ephemeral=True)
    
    except Exception as e:
        logger.error(f"Failed to change scan interval: {e}", exc_info=True)
        await interaction.followup.send(f"주기 변경 실패: {e}", ephemeral=True)

# ============================================
# 라즈베리파이 시스템 모니터링 커맨드
# ============================================

if MONITOR_AVAILABLE:
    @client.tree.command(name="system", description="시스템 상태를 확인합니다")
    async def system(interaction: discord.Interaction):
        logger.info(f"User {interaction.user} requested system info")
        await interaction.response.defer(ephemeral=True)
        
        try:
            info = get_system_info()
            if not info:
                await interaction.followup.send("시스템 정보를 가져올 수 없습니다", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="시스템 상태",
                color=discord.Color.blue()
            )
            
            # CPU 정보
            cpu_bar = create_bar(info['cpu']['percent'], 100)
            embed.add_field(
                name="CPU",
                value=f"{cpu_bar} {info['cpu']['percent']}%\n{info['cpu']['count']}코어, {info['cpu']['freq_current']:.0f}MHz",
                inline=False
            )
            
            # 메모리 정보
            mem_bar = create_bar(info['memory']['percent'], 100)
            mem_used_gb = info['memory']['used'] / (1024**3)
            mem_total_gb = info['memory']['total'] / (1024**3)
            embed.add_field(
                name="메모리",
                value=f"{mem_bar} {info['memory']['percent']}%\n{mem_used_gb:.2f}GB / {mem_total_gb:.2f}GB",
                inline=False
            )
            
            # 디스크 정보
            disk_bar = create_bar(info['disk']['percent'], 100)
            disk_used_gb = info['disk']['used'] / (1024**3)
            disk_total_gb = info['disk']['total'] / (1024**3)
            embed.add_field(
                name="디스크",
                value=f"{disk_bar} {info['disk']['percent']}%\n{disk_used_gb:.2f}GB / {disk_total_gb:.2f}GB",
                inline=False
            )
            
            # 시스템 가동 시간 & 로드
            embed.add_field(name="가동 시간", value=info['uptime'], inline=True)
            embed.add_field(
                name="로드 평균",
                value=f"{info['load_avg'][0]:.2f}, {info['load_avg'][1]:.2f}, {info['load_avg'][2]:.2f}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"System command error: {e}", exc_info=True)
            await interaction.followup.send(f"오류 발생: {e}", ephemeral=True)
    
    @client.tree.command(name="hardware", description="시스템 하드웨어 정보를 확인합니다")
    async def hardware(interaction: discord.Interaction):
        logger.info(f"User {interaction.user} requested hardware info")
        await interaction.response.defer(ephemeral=True)
        
        try:
            info = get_hardware_info()
            if not info:
                await interaction.followup.send("하드웨어 정보를 가져올 수 없습니다", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"{MONITOR_TYPE} 하드웨어 상태",
                color=discord.Color.green() if info.get('cpu_temp', 100) < 70 else discord.Color.red()
            )
            
            # 모델 정보
            if 'model' in info:
                embed.add_field(name="모델", value=info['model'], inline=False)
            
            # 온도 정보
            temp_text = []
            if info.get('cpu_temp'):
                cpu_temp = info['cpu_temp']
                temp_emoji = "🔥" if cpu_temp > 80 else "⚠️" if cpu_temp > 70 else "✅"
                temp_text.append(f"CPU: {cpu_temp}°C {temp_emoji}")
            if info.get('gpu_temp'):
                temp_text.append(f"GPU: {info['gpu_temp']}°C")
            
            if temp_text:
                embed.add_field(name="온도", value="\n".join(temp_text), inline=True)
            
            # 전압 & 클럭
            if info.get('voltage'):
                voltage_emoji = "⚠️" if info['voltage'] < 4.8 else "✅"
                embed.add_field(name="전압", value=f"{info['voltage']}V {voltage_emoji}", inline=True)
            
            if info.get('clock_mhz'):
                embed.add_field(name="클럭", value=f"{info['clock_mhz']:.0f}MHz", inline=True)
            
            # 쓰로틀링 상태
            if 'throttled_status' in info:
                status_text = "\n".join(info['throttled_status'])
                status_color = "🟢" if info['throttled_status'] == ["OK"] else "🔴"
                embed.add_field(name=f"쓰로틀링 {status_color}", value=status_text, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Hardware command error: {e}", exc_info=True)
            await interaction.followup.send(f"오류 발생: {e}", ephemeral=True)
    
    @client.tree.command(name="process", description="봇 프로세스 정보를 확인합니다")
    async def process(interaction: discord.Interaction):
        logger.info(f"User {interaction.user} requested process info")
        await interaction.response.defer(ephemeral=True)
        
        try:
            info = get_process_info()
            if not info:
                await interaction.followup.send("프로세스 정보를 가져올 수 없습니다", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="봇 프로세스 상태",
                color=discord.Color.purple()
            )
            
            embed.add_field(name="메모리 사용량", value=f"{info['memory_mb']} MB ({info['memory_percent']}%)", inline=True)
            embed.add_field(name="CPU 사용률", value=f"{info['cpu_percent']}%", inline=True)
            embed.add_field(name="스레드 수", value=str(info['threads']), inline=True)
            embed.add_field(name="프로세스 실행 시간", value=info['runtime'], inline=True)
            embed.add_field(name="Python 버전", value=info['python_version'], inline=True)
            embed.add_field(name="PID", value=str(info['pid']), inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Process command error: {e}", exc_info=True)
            await interaction.followup.send(f"오류 발생: {e}", ephemeral=True)
    
    @client.tree.command(name="network", description="네트워크 정보를 확인합니다")
    async def network(interaction: discord.Interaction):
        logger.info(f"User {interaction.user} requested network info")
        await interaction.response.defer(ephemeral=True)
        
        try:
            info = get_network_info()
            if not info:
                await interaction.followup.send("네트워크 정보를 가져올 수 없습니다", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="네트워크 상태",
                color=discord.Color.teal()
            )
            
            if 'local_ip' in info:
                embed.add_field(name="로컬 IP", value=info['local_ip'], inline=True)
            if 'interface' in info:
                embed.add_field(name="인터페이스", value=info['interface'], inline=True)
            
            embed.add_field(name="전송량", value=info['bytes_sent'], inline=True)
            embed.add_field(name="수신량", value=info['bytes_recv'], inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Network command error: {e}", exc_info=True)
            await interaction.followup.send(f"오류 발생: {e}", ephemeral=True)

def create_bar(value, max_value, length=10):
    """프로그레스 바 생성"""
    filled = int((value / max_value) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}]"

# ============================================
# scraper에서 호출할 함수
# ============================================

def add_error_log(site, error_msg):
    """에러 로그 추가 (최대 10개 유지)"""
    global error_log
    logger.error(f"Scraper error at {site}: {error_msg}")
    error_log.append({
        "time": datetime.now(),
        "site": site,
        "error": str(error_msg)
    })
    if len(error_log) > 10:
        error_log.pop(0)  # 가장 오래된 에러 제거

def send_notice_to_discord(notices):
    """scraper에서 호출하는 함수 - 큐에 공지 추가"""
    if not notices:
        return
    logger.info(f"Adding {len(notices)} notices to queue")
    notice_queue.put(notices)
    print(f"[Queue] Added {len(notices)} notices")

if __name__ == "__main__":
    print("Starting Discord Bot...")
    print("Bot will stay active and process notices from scraper")
    
    # 봇 시작 시간 기록
    bot_start_time = datetime.now()
    
    # scraper를 별도 스레드에서 실행
    def run_scraper():
        global scraper_scheduler, last_scan_time, next_scan_time
        import time
        time.sleep(3)  # 봇이 준비될 시간
        print("\n[Scraper] Starting notice monitor...")
        
        from scraper import monitors, job_wrapper, set_notice_callback, set_time_tracker, set_error_logger
        from apscheduler.schedulers.background import BackgroundScheduler
        
        # 콜백 함수 설정 (같은 Queue 인스턴스를 사용하도록)
        set_notice_callback(send_notice_to_discord)
        
        # 시간 추적 및 에러 로깅 콜백 설정
        def update_scan_time():
            global last_scan_time, next_scan_time
            last_scan_time = datetime.now()
            next_scan_time = last_scan_time + timedelta(seconds=SCAN_INTERVAL_SECONDS)
        
        set_time_tracker(update_scan_time)
        set_error_logger(add_error_log)
        
        scraper_scheduler = BackgroundScheduler()
        # 주기적으로 공지사항 체크
        scraper_scheduler.add_job(
            job_wrapper,
            'interval',
            seconds=SCAN_INTERVAL_SECONDS,
            next_run_time=datetime.now(),  # 시작 직후 즉시 한 번 실행
            max_instances=1,
            coalesce=True  # 밀린 작업은 하나로 합침
        )
        scraper_scheduler.start()
        print(f"[Scraper] Checking every {SCAN_INTERVAL_SECONDS} seconds...")
        
        # 다음 스캔 시간 초기화
        next_scan_time = datetime.now() + timedelta(seconds=SCAN_INTERVAL_SECONDS)
        
        # 스레드가 계속 실행되도록 대기
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("[Scraper] Stopping...")
            scraper_scheduler.shutdown()
    
    import threading
    scraper_thread = threading.Thread(target=run_scraper, daemon=True)  # daemon=True로 변경
    scraper_thread.start()
    
    # Discord 봇 실행
    try:
        client.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down...")

