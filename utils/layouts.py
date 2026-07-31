"""
LayoutView 기반 공통 레이아웃 유틸리티
discord.py 2.7+ Components V2 사용
"""
import time
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


class CooldownLayoutView(ui.LayoutView):
    """상호작용 쿨다운이 적용된 LayoutView 베이스 클래스.

    버튼 등의 상호작용에 유저별 1초 쿨다운을 적용합니다.
    서브클래스에서 interaction_check를 오버라이드할 때 반드시
    super().interaction_check()을 먼저 호출하세요.

    전송 후 self.message에 메시지를 넣어두면 타임아웃 시 버튼을
    비활성화합니다. 안 넣으면 만료된 버튼이 '상호작용 실패'로 남습니다.
    """

    COOLDOWN_SECONDS = 1.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cooldowns: dict = {}
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        user_id = interaction.user.id
        now = time.monotonic()
        last_time = self._cooldowns.get(user_id, 0)

        if now - last_time < self.COOLDOWN_SECONDS:
            await interaction.response.defer()
            return False

        self._cooldowns[user_id] = now

        # 원 인터랙션 토큰은 15분이면 만료된다. 컴포넌트 상호작용의 메시지는
        # 봇 토큰으로 편집되므로 갱신해 두면 늦은 타임아웃 편집도 성공한다.
        if interaction.message is not None:
            self.message = interaction.message

        return True

    async def on_timeout(self) -> None:
        if not self.message:
            return

        changed = False
        for child in self.walk_children():
            if isinstance(child, ui.Button) and child.style != discord.ButtonStyle.link and not child.disabled:
                child.disabled = True
                changed = True

        if changed:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
