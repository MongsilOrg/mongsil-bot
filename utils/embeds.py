"""
공통 임베드 생성 유틸리티
"""
import discord
from typing import Optional
from .config import config
from .emojis import EMOJIS

def create_base_embed(
    title: str,
    description: str = "",
    color: Optional[int] = None,
    client: Optional[discord.Client] = None
) -> discord.Embed:
    """기본 임베드를 생성합니다."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or config.embed_color
    )
    
    if client:
        footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
        embed.set_footer(text=footer_text, icon_url=config.footer_icon)
    
    return embed

def create_error_embed(
    title: str,
    description: str,
    client: Optional[discord.Client] = None
) -> discord.Embed:
    """에러 메시지를 위한 임베드를 생성합니다."""
    return create_base_embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
        client=client
    )

def create_success_embed(
    title: str,
    description: str,
    client: Optional[discord.Client] = None
) -> discord.Embed:
    """성공 메시지를 위한 임베드를 생성합니다."""
    return create_base_embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
        client=client
    )

def create_info_embed(
    title: str,
    description: str,
    client: Optional[discord.Client] = None,
    add_icon: bool = True
) -> discord.Embed:
    """정보 메시지를 위한 임베드를 생성합니다."""
    title_with_icon = f"ℹ️ {title}" if add_icon else title
    return create_base_embed(
        title=title_with_icon,
        description=description,
        color=config.embed_color,
        client=client
    )

def create_loading_embed(
    title: str,
    description: str = "",
    client: Optional[discord.Client] = None
) -> discord.Embed:
    """로딩 메시지를 위한 임베드를 생성합니다."""
    return create_base_embed(
        title=f"{EMOJIS['loading']} {title}",
        description=description,
        color=config.embed_color,
        client=client
    )
