import discord
from discord.ext import commands, tasks
from client import ERClient
import asyncio
from datetime import datetime

import os

import sentry_sdk

from utils.config import config  # import 시점에 load_dotenv()가 실행된다
from utils.logging_config import setup_logging, get_logger
from utils.emoji_zoom import process_emoji_zoom, cleanup_emoji_zoom_cache

# 장애 추적. config import로 .env가 로드된 뒤여야 DSN이 잡힌다.
# DSN이 비어 있으면 transport가 없어 어디로도 전송되지 않는다.
def _sentry_before_send(event, hint):
    """예상된 사용자 에러·일시적 네트워크 에러는 Sentry로 보내지 않는다."""
    exc_info = hint.get("exc_info")
    if exc_info:
        name = getattr(exc_info[0], "__name__", "")
        msg = str(exc_info[1])
        if "찾을 수 없습니다" in msg:
            return None
        if name in ("TimeoutError", "ConnectTimeoutError", "ReadTimeout", "ConnectionError", "ClientConnectorError", "ClientOSError", "ServerDisconnectedError", "WSServerHandshakeError", "ConnectionClosed", "ConnectionResetError"):
            return None
        for _t in ("Connection timeout", "Cannot connect to host", "Temporary failure in name resolution", "네트워크 오류", "연결 중 오류"):
            if _t in msg:
                return None
    return event


sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    traces_sample_rate=0.1,
    environment="production",
    before_send=_sentry_before_send,
)

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