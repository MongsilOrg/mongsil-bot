import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta
import math
import os

from utils.config import config
from utils.layouts import create_error_layout
from utils.logging_config import get_logger
from utils.api_client import api_client

logger = get_logger(__name__)


class ERClient(commands.Bot):
    def __init__(self, intents: discord.Intents = None):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.presences = False

        super().__init__(command_prefix="!", intents=intents)

        # data 디렉토리 생성
        os.makedirs("data", exist_ok=True)

        self.api_client = api_client
        self.start_time = None  # main.py에서 설정됨

        # 이름만 on_tree_error인 메서드는 아무 데도 연결되지 않는다. 명시적으로 바인딩해야 동작.
        self.tree.on_error = self.on_tree_error

    @property
    def uptime(self) -> Optional[timedelta]:
        """봇의 업타임을 반환합니다."""
        if self.start_time is None:
            return None
        return datetime.now() - self.start_time

    async def get_user_nickname(self, nickname: str) -> Optional[str]:
        """닉네임으로 유저 UID를 조회합니다.

        None은 '없는 닉네임'만 의미한다. API 장애는 예외로 전파해
        '닉네임을 확인해주세요' 오안내가 나가지 않게 한다.
        """
        url = f"{config.api_url}/user/nickname"
        params = {'query': nickname}
        # 닉네임-uid 매핑은 사실상 불변이라 길게 캐시
        response = await self.api_client.get(url, params=params, ttl=86400)

        if response and response.get('code') == 200:
            user_data = response.get('user')
            if user_data:
                # API 문서와 실제 응답의 필드명 차이 대응
                for field in ('userNum', 'userId', 'uid'):
                    if field in user_data:
                        return user_data[field]

        # '없음' 응답(HTTP 200 + code 404)까지 24시간 캐시하면
        # 신규 생성이나 개명 직후 유저가 하루 동안 조회 불가가 된다
        self.api_client.uncache(url, params=params)
        return None

    async def setup_hook(self) -> None:
        try:
            for module in [
                "commands.season",
                "commands.concurrent",
                "commands.playtime",
                "commands.dog",
                "commands.cat",
                "commands.ranking",
                "commands.settings",
                "commands.info",
                "commands.rank",
                "commands.rating"
            ]:
                await self.load_extension(module)

            # 커맨드 동기화는 SYNC_COMMANDS=1 환경변수가 설정된 경우에만 수행
            # 매 재시작마다 sync하면 Discord rate limit에 걸려 연결 끊김/재연결 반복 발생
            if os.getenv('SYNC_COMMANDS') == '1':
                await self.tree.sync()
                logger.info("슬래시 커맨드 동기화 완료")
            else:
                logger.info("슬래시 커맨드 동기화 건너뜀 (SYNC_COMMANDS=1로 설정하면 동기화)")

        except Exception:
            raise

    @tasks.loop(minutes=30.0)
    async def change_status(self):
        """30분마다 봇의 상태를 업데이트합니다."""
        try:
            await self.change_presence(activity=discord.Game(name=f"{len(self.guilds)}개의 서버에서 일"))
        except Exception as e:
            logger.debug(f"상태 업데이트 중 오류 (무시됨): {e}")

    @change_status.before_loop
    async def before_change_status(self):
        await self.wait_until_ready()

    async def on_disconnect(self):
        """봇이 연결이 끊어졌을 때 호출됩니다."""
        logger.warning("봇 연결이 끊어졌습니다.")

    async def on_resumed(self):
        """봇이 재연결되었을 때 호출됩니다."""
        logger.info("봇이 재연결되었습니다.")

    async def on_guild_join(self, guild):
        """봇이 새 서버에 참가했을 때 호출됩니다."""
        logger.info(f"서버 참가: {guild.name} (ID: {guild.id}, 멤버: {guild.member_count})")

    async def on_guild_remove(self, guild):
        """봇이 서버에서 제거되었을 때 호출됩니다."""
        logger.info(f"서버 제거: {guild.name} (ID: {guild.id})")

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        error_message = "명령어 실행 중 오류가 발생했어요. 잠시 후 다시 시도해주세요."

        if isinstance(error, app_commands.CheckFailure):
            error_message = "이 명령어를 실행할 권한이 없어요."
        elif isinstance(error, app_commands.CommandOnCooldown):
            error_message = f"명령어를 너무 자주 사용했어요. {math.ceil(error.retry_after)}초 후에 다시 시도해주세요."

        # 권한/쿨다운은 예상된 유저 조건이라 WARNING (Sentry는 ERROR 이상만 수집)
        if isinstance(error, (app_commands.CheckFailure, app_commands.CommandOnCooldown)):
            logger.warning(f"명령어 차단: {error}")
        else:
            logger.error(f"명령어 실행 오류: {error}", exc_info=True)

        try:
            layout = create_error_layout("오류", error_message)
            if not interaction.response.is_done():
                await interaction.response.send_message(view=layout, ephemeral=True)
            else:
                await interaction.followup.send(view=layout, ephemeral=True)
        except Exception:
            pass

    async def close(self):
        """봇 종료 시 리소스를 정리합니다."""
        try:
            await self.api_client.close()
            logger.info("리소스 정리 완료")
        except Exception as e:
            logger.error(f"리소스 정리 중 오류: {e}")
        finally:
            await super().close()
