"""
LayoutView 기반 공통 레이아웃 유틸리티
discord.py 2.7+ Components V2 사용
"""
import discord
from discord import ui
from typing import Optional
from .config import config
from .emojis import EMOJIS


def footer_text(client: Optional[discord.Client] = None) -> str:
    """공통 푸터 텍스트를 생성합니다."""
    if client:
        return f'-# 몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    return '-# 몽실봇'


def create_error_layout(title: str, description: str, client: Optional[discord.Client] = None) -> ui.LayoutView:
    """에러 메시지용 LayoutView를 생성합니다."""
    view = ui.LayoutView(timeout=None)
    items = [ui.TextDisplay(f"### ❌ {title}\n{description}")]
    if client:
        items.append(ui.Separator(visible=False))
        items.append(ui.TextDisplay(footer_text(client)))
    view.add_item(ui.Container(*items, accent_colour=discord.Colour.red()))
    return view


def create_loading_layout(title: str, description: str = "", client: Optional[discord.Client] = None) -> ui.LayoutView:
    """로딩 메시지용 LayoutView를 생성합니다."""
    view = ui.LayoutView(timeout=None)
    text = f"### {EMOJIS['loading']} {title}"
    if description:
        text += f"\n{description}"
    items = [ui.TextDisplay(text)]
    if client:
        items.append(ui.Separator(visible=False))
        items.append(ui.TextDisplay(footer_text(client)))
    view.add_item(ui.Container(*items, accent_colour=discord.Colour.blurple()))
    return view


def create_success_layout(title: str, description: str, client: Optional[discord.Client] = None) -> ui.LayoutView:
    """성공 메시지용 LayoutView를 생성합니다."""
    view = ui.LayoutView(timeout=None)
    items = [ui.TextDisplay(f"### ✅ {title}\n{description}")]
    if client:
        items.append(ui.Separator(visible=False))
        items.append(ui.TextDisplay(footer_text(client)))
    view.add_item(ui.Container(*items, accent_colour=discord.Colour.green()))
    return view
