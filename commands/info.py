import os
import sys
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

import discord
import psutil
from discord import ButtonStyle, Color, Embed
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from client import ERClient
from utils.config import config
from utils.embeds import create_error_embed
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

class LinkView(View):
    """링크 버튼을 포함하는 뷰"""
    def __init__(self):
        super().__init__(timeout=None)
        
        # 지원 서버 버튼
        support_button = Button(
            style=ButtonStyle.link,
            label="지원 서버",
            url=config.support_server,
            emoji=EMOJIS['support']
        )
        self.add_item(support_button)

        # 봇 초대 버튼
        invite_button = Button(
            style=ButtonStyle.link,
            label="봇 초대하기",
            url=config.bot_invite,
            emoji=EMOJIS['invite']
        )
        self.add_item(invite_button)

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

def create_bot_info_embed(bot_info: Optional[BotInfo], client: ERClient) -> Embed:
    """봇 정보 임베드를 생성합니다."""
    if not bot_info:
        return Embed(
            title="봇 정보",
            description="봇 정보를 가져올 수 없습니다.",
            color=Color.red()
        )

    # 서비스 개시일부터의 일수 계산
    start_date = datetime(2023, 6, 15)
    days_since_start = (datetime.now() - start_date).days

    embed = Embed(
        title=f"{EMOJIS['bot']} 몽실봇 정보",
        description=f"이터널 리턴 전적 검색 및 정보 봇\n{EMOJIS['calendar']} 서비스 개시일: **2023.06.15** (D+{days_since_start})",
        color=config.embed_color
    )
    
    # 봇 상태 정보
    status_info = (
        f"{EMOJIS['server']} **서버**: {bot_info.guild_count:,}개\n"
        f"{EMOJIS['user']} **유저**: {bot_info.user_count:,}명\n"
        f"{EMOJIS['channel']} **채널**: {bot_info.channel_count:,}개\n"
    )
    embed.add_field(
        name=f"{EMOJIS['status']} 봇 상태",
        value=status_info,
        inline=True
    )

    # 시스템 정보
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
    
    # 핑 상태에 따른 이모지 변경
    if bot_info.ping < 100:
        ping_emoji = PING_EMOJIS['good']
    elif bot_info.ping < 200:
        ping_emoji = PING_EMOJIS['normal']
    else:
        ping_emoji = PING_EMOJIS['bad']
    
    system_info = (
        f"{EMOJIS['uptime']} **업타임**: {uptime_str}\n"
        f"{EMOJIS['ram']} **메모리**: {bot_info.ram_usage:.1f}MB\n"
        f"{ping_emoji} **핑**: {bot_info.ping * 1000:.1f}ms"
    )
    embed.add_field(
        name=f"{EMOJIS['system']} 시스템 정보",
        value=system_info,
        inline=True
    )
    
    # 개발 정보
    dev_info = (
        f"{EMOJIS['python']} **Python**: v{bot_info.python_version}\n"
        f"{EMOJIS['lib']} **Discord.py**: v{bot_info.discord_version}\n"
        f"{EMOJIS['dev']} **개발자**: {bot_info.developer_tag}"
    )
    embed.add_field(
        name=f"{EMOJIS['info']} 개발 정보",
        value=dev_info,
        inline=False
    )

    # 푸터 추가
    footer_text = f'몽실봇 • {bot_info.guild_count}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)

    return embed

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
        embed = create_bot_info_embed(bot_info, client)
        view = LinkView()
        
        await interaction.response.send_message(embed=embed, view=view)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Info(client)) 