import discord
from discord import Embed, Color, SelectOption, Interaction, ButtonStyle
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button
import json
from typing import Optional, Set, Dict, Any
from client import ERClient
from pathlib import Path
from datetime import datetime

from utils.config import config
from utils.embeds import create_info_embed, create_error_embed, create_success_embed
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

# 데이터 파일 경로 (이제 utils/emoji_zoom.py에서 관리)
DATA_PATH = Path('./data/settings.json')

def create_settings_embed(guild_id: int, is_enabled: bool, client: ERClient) -> Embed:
    """서버 설정 임베드를 생성합니다."""
    status = "활성화" if is_enabled else "비활성화"
    status_emoji = EMOJIS['on'] if is_enabled else EMOJIS['off']
    
    embed = Embed(
        title=f"{EMOJIS['settings']} 서버 설정",
        description="서버별 봇 기능 설정을 관리할 수 있습니다.",
        color=config.embed_color
    )
    
    # 이모지 확대 기능 상태
    embed.add_field(
        name=f"{EMOJIS['emoji_zoom']} 이모지 확대 기능",
        value=f"{status_emoji} **{status}**\n{SETTINGS_CONFIG['emoji_zoom']['description']}",
        inline=False
    )
    
    # 관리자 권한 안내
    embed.add_field(
        name="🔗 필요한 권한",
        value="• **관리자** 권한 - 몽실봇 서비스 이용에 필수\n"
              "• 권한이 없으면 자동으로 비활성화됩니다",
        inline=False
    )
    
    # 사용법 안내
    embed.add_field(
        name=f"{EMOJIS['info']} 사용법",
        value="• 버튼을 클릭하여 설정 토글\n• 관리자 권한이 필요합니다",
        inline=False
    )
    
    footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)
    
    return embed

class SettingsView(View):
    def __init__(self, guild_id: int, client: ERClient):
        super().__init__(timeout=config.view_timeout_interactive)
        self.guild_id = guild_id
        self.client = client
        self.add_toggle_button()

    def add_toggle_button(self):
        """이모지 확대 기능 토글 버튼을 추가합니다."""
        disabled_servers = load_disabled_servers()
        is_enabled = self.guild_id not in disabled_servers
        
        # 현재 상태에 따른 버튼 스타일과 텍스트 설정
        if is_enabled:
            button_style = ButtonStyle.danger
            button_label = "비활성화"
            button_emoji = EMOJIS['off']
        else:
            button_style = ButtonStyle.success
            button_label = "활성화"
            button_emoji = EMOJIS['on']
        
        toggle_button = Button(
            style=button_style,
            label=f"이모지 확대 {button_label}",
            emoji=button_emoji
        )
        
        async def toggle_callback(interaction: Interaction):
            if not interaction.user.guild_permissions.administrator:
                embed = create_error_embed(
                    "권한 없음",
                    "관리자만 설정을 변경할 수 있습니다.",
                    self.client
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 현재 상태 확인
            disabled_servers = load_disabled_servers()
            current_enabled = self.guild_id not in disabled_servers
            
            # 상태 토글
            if current_enabled:
                # 현재 활성화 -> 비활성화로 변경
                disabled_servers.add(self.guild_id)
                new_status = "비활성화"
                status_emoji = EMOJIS['off']
            else:
                # 현재 비활성화 -> 활성화로 변경 (웹훅 권한 검증)
                if not interaction.guild.me.guild_permissions.manage_webhooks:
                    # 웹훅 권한이 없는 경우
                    error_embed = create_error_embed(
                        "권한 부족",
                        "**관리자 권한**이 없어 이모지 확대 기능을 활성화할 수 없습니다.\n\n"
                        "**해결 방법:**\n"
                        "• 서버 설정 → 역할 → 몽실봇 → 권한\n"
                        "• **관리자** 권한을 활성화\n"
                        "• 권한 설정 후 이 버튼을 다시 클릭해주세요",
                        self.client
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                    return
                
                disabled_servers.discard(self.guild_id)
                new_status = "활성화"
                status_emoji = EMOJIS['on']

            # 설정 저장
            if save_disabled_servers(disabled_servers):
                # 성공 메시지
                success_embed = create_success_embed(
                    "설정 변경 완료",
                    f"{EMOJIS['save']} 이모지 확대 기능이 **{new_status}**되었습니다.",
                    self.client
                )
                
                # 메인 임베드 자동 새로고침
                main_embed = create_settings_embed(self.guild_id, not current_enabled, self.client)
                await interaction.response.edit_message(embed=main_embed, view=SettingsView(self.guild_id, self.client))
                
                # 성공 메시지 전송
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
            else:
                # 저장 실패
                embed = create_error_embed(
                    "저장 실패",
                    "설정 저장 중 오류가 발생했습니다. 다시 시도해주세요.",
                    self.client
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        toggle_button.callback = toggle_callback
        self.add_item(toggle_button)

class Settings(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="설정", description="서버 봇 설정 관리 (서버 전용)")
    @app_commands.guild_only()
    @handle_errors(user_message="설정을 가져오는 중 오류가 발생했습니다.")
    async def settings_command(self, interaction: discord.Interaction):
        """서버의 봇 설정을 관리합니다."""
        try:
            disabled_servers = load_disabled_servers()
            is_enabled = interaction.guild_id not in disabled_servers
            
            embed = create_settings_embed(interaction.guild_id, is_enabled, self.client)
            view = SettingsView(interaction.guild_id, self.client)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"설정 명령어 실행 중 오류 발생: {e}", exc_info=True)
            # handle_errors 데코레이터가 이미 에러를 처리하므로 여기서는 추가 처리 불필요

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Settings(client)) 