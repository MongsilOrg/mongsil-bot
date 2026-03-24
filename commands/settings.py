import discord
from discord import Interaction
from discord.ext import commands
from discord import app_commands, ui
from client import ERClient

from utils.config import config
from utils.layouts import create_error_layout, create_success_layout, footer_text, CooldownLayoutView
from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.emoji_zoom import load_disabled_servers, save_disabled_servers
from utils.emojis import EMOJIS

logger = get_logger('설정')

# 설정 상수
SETTINGS_CONFIG = {
    'emoji_zoom': {
        'name': '이모지 확대',
        'description': '서버에서 이모지 확대 기능을 사용합니다',
        'emoji': EMOJIS['emoji_zoom']
    }
}

class SettingsView(CooldownLayoutView):
    def __init__(self, guild_id: int, client: ERClient):
        super().__init__(timeout=config.view_timeout_interactive)
        self.guild_id = guild_id
        self.client = client
        self.build_layout()

    def build_layout(self):
        self.clear_items()
        disabled_servers = load_disabled_servers()
        is_enabled = self.guild_id not in disabled_servers

        status = "활성화" if is_enabled else "비활성화"
        status_emoji = EMOJIS['on'] if is_enabled else EMOJIS['off']

        container = ui.Container(accent_colour=discord.Colour.blurple())
        container.add_item(ui.TextDisplay("### ⚙️ 서버 설정\n서버별 봇 기능 설정을 관리할 수 있습니다."))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"🔍 **이모지 확대 기능**\n{status_emoji} **{status}**\n{SETTINGS_CONFIG['emoji_zoom']['description']}"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay("🔗 **필요한 권한**\n• **관리자** 권한 - 몽실봇 서비스 이용에 필수"))
        container.add_item(ui.Separator(visible=False))
        container.add_item(ui.TextDisplay(footer_text(self.client)))
        self.add_item(container)

        # 토글 버튼
        if is_enabled:
            btn = ui.Button(style=discord.ButtonStyle.danger, label="이모지 확대 비활성화", custom_id="toggle_emoji")
        else:
            btn = ui.Button(style=discord.ButtonStyle.success, label="이모지 확대 활성화", custom_id="toggle_emoji")
        self.add_item(ui.ActionRow(btn))

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False

        custom_id = interaction.data.get("custom_id")
        if custom_id != "toggle_emoji":
            await interaction.response.defer()
            return False

        if not interaction.user.guild_permissions.administrator:
            error_layout = create_error_layout("권한 없음", "관리자만 설정을 변경할 수 있습니다.", self.client)
            await interaction.response.send_message(view=error_layout, ephemeral=True)
            return False

        # 토글 로직
        disabled_servers = load_disabled_servers()
        current_enabled = self.guild_id not in disabled_servers

        if current_enabled:
            disabled_servers.add(self.guild_id)
        else:
            if not interaction.guild.me.guild_permissions.manage_webhooks:
                error_layout = create_error_layout(
                    "권한 부족",
                    "**관리자 권한**이 없어 이모지 확대 기능을 활성화할 수 없습니다.",
                    self.client
                )
                await interaction.response.send_message(view=error_layout, ephemeral=True)
                return False
            disabled_servers.discard(self.guild_id)

        if save_disabled_servers(disabled_servers):
            self.build_layout()
            await interaction.response.edit_message(view=self)
            new_status = "비활성화" if current_enabled else "활성화"
            success = create_success_layout("설정 변경 완료", f"이모지 확대 기능이 **{new_status}**되었습니다.", self.client)
            await interaction.followup.send(view=success, ephemeral=True)
        else:
            error_layout = create_error_layout("저장 실패", "설정 저장 중 오류가 발생했습니다.", self.client)
            await interaction.response.send_message(view=error_layout, ephemeral=True)

        return False

class Settings(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="설정", description="서버 봇 설정 관리 (서버 전용)")
    @app_commands.guild_only()
    @handle_errors(user_message="설정을 가져오는 중 오류가 발생했습니다.")
    async def settings_command(self, interaction: discord.Interaction):
        """서버의 봇 설정을 관리합니다."""
        view = SettingsView(interaction.guild_id, self.client)
        await interaction.response.send_message(view=view)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Settings(client))
