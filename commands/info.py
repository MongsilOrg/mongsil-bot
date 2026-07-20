import os
import sys
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

import discord
import psutil
from discord import ui
from discord import app_commands
from discord.ext import commands

from client import ERClient
from utils.config import config
from utils.layouts import create_error_layout, footer_text
from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.emojis import EMOJIS, PING_EMOJIS

logger = get_logger('정보')

class BotInfo(NamedTuple):
    """봇 정보를 저장하는 네임드 튜플"""
    guild_count: int
    user_count: int
    channel_count: int
    uptime: timedelta
    ram_usage: float
    python_version: str
    discord_version: str
    developer_id: str
    developer_tag: str
    developer_email: str
    ping: float

async def get_bot_info(client: ERClient) -> BotInfo:
    """봇 정보를 수집합니다."""
    try:
        # 서버 수
        guild_count = len(client.guilds)

        # 유저 수 (중복 제외) - members 캐시가 있으면 정확한 중복 제거, 없으면 member_count 합산
        unique_users = set()
        fallback_count = 0
        for guild in client.guilds:
            if guild.members:
                unique_users.update(member.id for member in guild.members)
            else:
                fallback_count += guild.member_count or 0
        user_count = len(unique_users) + fallback_count

        # 채널 수
        channel_count = sum(len(guild.channels) for guild in client.guilds if guild.channels)

        # 업타임 계산
        uptime = client.uptime or timedelta(seconds=0)

        # 메모리 사용량 (MB)
        process = psutil.Process(os.getpid())
        ram_usage = process.memory_info().rss / 1024 / 1024

        # 봇 정보 반환
        return BotInfo(
            guild_count=guild_count,
            user_count=user_count,
            channel_count=channel_count,
            uptime=uptime,
            ram_usage=ram_usage,
            python_version=sys.version.split()[0],
            discord_version=discord.__version__,
            developer_id=config.developer_id,
            developer_tag=config.developer_tag,
            developer_email=config.developer_email,
            ping=client.latency if client.latency else 0.0
        )
    except Exception as e:
        logger.error(f"봇 정보 수집 중 오류 발생: {e}", exc_info=True)
        # 기본값 반환
        return BotInfo(
            guild_count=len(client.guilds),
            user_count=sum(g.member_count or 0 for g in client.guilds),
            channel_count=sum(len(g.channels) for g in client.guilds if g.channels),
            uptime=client.uptime or timedelta(seconds=0),
            ram_usage=psutil.Process().memory_info().rss / 1024 / 1024,
            python_version=sys.version.split()[0],
            discord_version=discord.__version__,
            developer_id=config.developer_id,
            developer_tag=config.developer_tag,
            developer_email=config.developer_email,
            ping=client.latency if client.latency else 0.0
        )

def create_bot_info_layout(bot_info: Optional[BotInfo], client: ERClient) -> ui.LayoutView:
    """봇 정보 LayoutView를 생성합니다."""
    if not bot_info:
        return create_error_layout(
            "봇 정보",
            "봇 정보를 가져올 수 없습니다.",
            client
        )

    # 서비스 개시일부터의 일수 계산
    start_date = datetime(2023, 6, 15)
    days_since_start = (datetime.now() - start_date).days

    # 업타임 문자열
    uptime = bot_info.uptime
    if uptime is None:
        uptime_str = "계산 중..."
    else:
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}일")
        if hours > 0:
            parts.append(f"{hours}시간")
        if minutes > 0:
            parts.append(f"{minutes}분")
        parts.append(f"{seconds}초")
        uptime_str = " ".join(parts)

    # 핑 상태에 따른 이모지 변경 (latency는 초 단위)
    ping_ms = bot_info.ping * 1000
    if ping_ms < 100:
        ping_emoji = PING_EMOJIS['good']
    elif ping_ms < 200:
        ping_emoji = PING_EMOJIS['normal']
    else:
        ping_emoji = PING_EMOJIS['bad']

    # LayoutView 구성
    view = ui.LayoutView(timeout=None)

    container = ui.Container(
        ui.TextDisplay(
            f"### 🤖 몽실봇\n"
            f"이터널 리턴 전적 검색 및 정보 봇\n"
            f"-# 서비스 개시 2023.06.15 · D+{days_since_start}"
        ),
        ui.Separator(),
        ui.TextDisplay(
            f"📊 **봇 현황**\n"
            f"🏠 서버 **{bot_info.guild_count:,}**개 · "
            f"👥 유저 **{bot_info.user_count:,}**명 · "
            f"💬 채널 **{bot_info.channel_count:,}**개"
        ),
        ui.TextDisplay(
            f"⚙️ **시스템**\n"
            f"⏱️ 업타임 **{uptime_str}** · "
            f"🧠 메모리 **{bot_info.ram_usage:.1f}**MB · "
            f"{ping_emoji} 핑 **{ping_ms:.0f}**ms"
        ),
        ui.TextDisplay(
            f"-# Python {bot_info.python_version} · Discord.py {bot_info.discord_version} · 개발 {bot_info.developer_tag}"
        ),
        ui.Separator(visible=False),
        ui.TextDisplay(footer_text(client)),
        accent_colour=discord.Colour.blurple(),
    )
    view.add_item(container)

    # 링크 버튼 ActionRow
    view.add_item(ui.ActionRow(
        ui.Button(
            style=discord.ButtonStyle.link,
            label="지원 서버",
            url=config.support_server,
            emoji=EMOJIS['support'],
        ),
        ui.Button(
            style=discord.ButtonStyle.link,
            label="봇 초대하기",
            url=config.bot_invite,
            emoji=EMOJIS['invite'],
        ),
    ))

    return view

class Info(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(
        name="정보",
        description="봇의 정보를 확인합니다."
    )
    @handle_errors(user_message="봇 정보를 가져오는 중 오류가 발생했습니다.")
    async def info_command(self, interaction: discord.Interaction):
        """봇의 정보를 표시합니다."""
        client: ERClient = interaction.client

        bot_info = await get_bot_info(client)
        layout = create_bot_info_layout(bot_info, client)

        await interaction.response.send_message(view=layout)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Info(client))
