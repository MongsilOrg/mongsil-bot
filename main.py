import discord
from discord.ext import commands, tasks
from client import ERClient
import asyncio
from datetime import datetime

from utils.config import config
from utils.logging_config import setup_logging, get_logger
from utils.emoji_zoom import process_emoji_zoom, cleanup_emoji_zoom_cache

# 로깅 설정
setup_logging(level="INFO", log_file="bot.log")
logger = get_logger(__name__)

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = False

client = ERClient(intents=intents)


@client.event
async def on_ready():
    """봇이 준비되었을 때 실행됩니다."""
    client.start_time = datetime.now()
    logger.info(f"{client.user} 온라인")
    
    # 이모지 확대 캐시 정리 (봇 재시작 시)
    await cleanup_emoji_zoom_cache()
    
    # 태스크 시작
    if not client.change_status.is_running():
        client.change_status.start()

@client.event
async def on_message(message: discord.Message):
    """메시지를 수신했을 때 실행됩니다."""
    # 기본 필터링
    if not message.guild or message.author.bot:
        return
    
    # 이모지 확대 기능 처리
    await process_emoji_zoom(message)

async def shutdown_handler():
    """봇 종료 시 호출되는 핸들러"""
    try:
        await cleanup_emoji_zoom_cache()
    except Exception as e:
        logger.error(f"종료 처리 중 오류: {e}")

if __name__ == "__main__":
    try:
        import atexit
        atexit.register(lambda: asyncio.run(shutdown_handler()))
        
        client.run(config.bot_token)
    except KeyboardInterrupt:
        logger.warning("봇이 사용자에 의해 중단되었습니다.")
        asyncio.run(shutdown_handler())
    except Exception as e:
        logger.error(f"봇 실행 중 오류 발생: {e}", exc_info=True)
        import sys
        sys.exit(1)