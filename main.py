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

# .env 파일 로드
load_dotenv()

# 로거 설정
logger = setup_logger("NotifyBot")

# 설정
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
CONFIG_FILE = "config.json"

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
    default_channel = os.getenv('DEFAULT_CHANNEL_ID', '952828252911706153')
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            logger.debug(f"Config loaded: {config}")
            return config
    logger.warning("Config file not found, using defaults")
    return {"send_individually": False, "channel_id": int(default_channel)}

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
    
    async def send_notices(self, notices):
        """공지사항을 Discord에 전송"""
        global stats
        
        # 날짜가 바뀌면 오늘 공지 수 초기화
        today = datetime.now().date()
        if stats["today_date"] != today:
            logger.info(f"Date changed: {stats['today_date']} -> {today}, resetting today's count")
            stats["today_date"] = today
            stats["today_notices"] = 0
        
        # 통계 업데이트
        stats["total_notices"] += len(notices)
        stats["today_notices"] += len(notices)
        for notice in notices:
            site = notice.get('site', '알 수 없음')
            stats["site_notices"][site] = stats["site_notices"].get(site, 0) + 1
            logger.info(f"Notice from {site}: [{notice['id']}] {notice['title']}")
        
        self.config = load_config()
        channel = self.get_channel(self.config["channel_id"])
        
        if not channel:
            logger.error(f"Channel {self.config['channel_id']} not found")
            print(f"[Error] Channel {self.config['channel_id']} not found")
            return
        
        logger.debug(f"Sending to channel: {channel.name} (ID: {channel.id})")

        if self.config["send_individually"]:
            # 방식 1: 공지 하나당 메시지 1개
            for notice in notices:
                site_name = notice.get('site', '알 수 없음')
                embed = discord.Embed(
                    title=f"새 공지사항 #{notice['id']}",
                    description=notice['title'],
                    color=discord.Color.blue(),
                    url=notice['link']
                )
                embed.add_field(name="사이트", value=site_name, inline=True)
                embed.add_field(name="작성일", value=notice['date'], inline=True)
                embed.add_field(name="번호", value=str(notice['id']), inline=True)
                await channel.send(embed=embed)
                await asyncio.sleep(0.5)  # API 제한 방지
        else:
            # 방식 2: 여러 공지를 한번에 통합
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
    
    embed = discord.Embed(
        title="공지 알림 설정",
        color=discord.Color.blue()
    )
    embed.add_field(name="전송 방식", value=mode_text, inline=False)
    embed.add_field(name="알림 채널", value=f"<#{config['channel_id']}>", inline=False)
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
    app_commands.Choice(name="학생생활관", value="dorm")
])
async def forcescan(interaction: discord.Interaction, site: app_commands.Choice[str] = None):
    await interaction.response.defer(ephemeral=True)
    
    try:
        from scraper import monitors, force_scan_single, job_wrapper
        
        if site and site.value != "all":
            # 특정 사이트만 체크
            site_map = {"sw": 0, "hlsw": 1, "dorm": 2}
            if site.value in site_map:
                result = force_scan_single(site_map[site.value])
                await interaction.followup.send(f"{site.name} 체크 완료!\n{result}", ephemeral=True)
            else:
                await interaction.followup.send("잘못된 사이트 선택", ephemeral=True)
        else:
            # 전체 사이트 체크
            job_wrapper()
            await interaction.followup.send("전체 사이트 체크 완료!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"체크 중 오류 발생: {e}", ephemeral=True)

@client.tree.command(name="stats", description="공지사항 전송 통계를 확인합니다")
async def stats_command(interaction: discord.Interaction):
    global stats
    
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
            next_scan_time = last_scan_time + timedelta(seconds=60)
        
        set_time_tracker(update_scan_time)
        set_error_logger(add_error_log)
        
        scraper_scheduler = BackgroundScheduler()
        # 간격을 60초로 늘리고, max_instances 설정
        scraper_scheduler.add_job(
            job_wrapper, 
            'interval', 
            seconds=300,
            max_instances=1,
            coalesce=True  # 밀린 작업은 하나로 합침
        )
        scraper_scheduler.start()
        print("[Scraper] Checking every 60 seconds...")
        
        # 다음 스캔 시간 초기화
        next_scan_time = datetime.now() + timedelta(seconds=60)
        
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

