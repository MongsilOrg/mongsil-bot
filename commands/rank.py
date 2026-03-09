import discord
from discord import Embed
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, Any
from client import ERClient

from commands.season import get_current_season_id, get_season_info
from utils.config import config
from utils.embeds import create_info_embed, create_error_embed, create_loading_embed
from utils.errors import handle_errors, validate_nickname, NotFoundError, APIError
from utils.logging_config import get_logger
from utils.character_names import get_character_name
from utils.rank_helpers import fetch_user_stats_solo
from utils.tier_system import TierSystem
from utils.emojis import EMOJIS

logger = get_logger('랭크')


def create_rank_embed(nickname: str, stats: Dict[str, Any], client: ERClient) -> tuple[Embed, None]:
    """랭크 정보 임베드를 생성합니다."""
    # 기본 정보 파싱
    mmr = int(stats.get('mmr', 0))
    rank = int(stats.get('rank', 0))
    rank_size = int(stats.get('rankSize', 0))
    games = int(stats.get('totalGames', 0))
    wins = int(stats.get('totalWins', 0))
    team_kills = int(stats.get('totalTeamKills', 0))
    avg_rank = float(stats.get('averageRank', 0.0))
    avg_kills = float(stats.get('averageKills', 0.0))
    avg_assists = float(stats.get('averageAssistants', 0.0))
    avg_hunts = float(stats.get('averageHunts', 0.0))
    top1_rate = float(stats.get('top1', 0.0))
    top2_rate = float(stats.get('top2', 0.0))
    top3_rate = float(stats.get('top3', 0.0))
    top5_rate = float(stats.get('top5', 0.0))
    
    # API에서 실제 닉네임 가져오기 (대소문자 구분 등)
    actual_nickname = stats.get('nickname', nickname)
    
    # 계산이 필요한 통계
    win_rate = (wins / games * 100) if games > 0 else 0.0
    avg_team_kills = (team_kills / games) if games > 0 else 0.0
    
    # 티어 정보 계산
    tier = TierSystem.get_tier(mmr, rank)
    tier_base = TierSystem.get_tier_base(tier)
    tier_score = mmr - tier_base
    
    # 상위 백분율 계산
    top_percentage = (rank / rank_size * 100) if rank_size > 0 else 0.0
    
    # 티어 표시 문자열 생성
    tier_display = f"{tier} - {tier_score:,} RP"
    
    embed = create_info_embed(
        title=f"{EMOJIS['trophy']} {actual_nickname} - {mmr:,}RP",
        description=f"{tier_display}\n#{rank:,}등 / {rank_size:,}명 중 (상위 {top_percentage:.2f}%)",
        client=client,
        add_icon=False
    )
    
    # 티어 아이콘을 임베드의 썸네일로 설정
    icon_name = TierSystem.get_tier_icon(tier)
    icon_url = f"https://mongsil.dev/w/src/{icon_name}.png"
    embed.set_thumbnail(url=icon_url)
    
    # 첫 번째 줄: 승률 / 게임 수 / 평균 순위
    embed.add_field(name="✨ 승률", value=f"{win_rate:.2f}%", inline=True)
    embed.add_field(name="🎮 게임", value=f"{games:,}게임({wins}승)", inline=True)
    embed.add_field(name="📊 평순", value=f"{avg_rank:.2f}위", inline=True)
    
    # 두 번째 줄: 평균 킬 / 평균 어시스트 / 평균 팀킬
    embed.add_field(name="🗡️ 평킬", value=f"{avg_kills:.2f}", inline=True)
    embed.add_field(name="🤝 어시", value=f"{avg_assists:.2f}", inline=True)
    embed.add_field(name="⚔️ 팀킬", value=f"{avg_team_kills:.2f}", inline=True)
    
    # 세 번째 줄: 탑1 / 탑3 / 평균 사냥
    embed.add_field(name="🥇 탑1", value=f"{top1_rate*100:.2f}%", inline=True)
    embed.add_field(name="🥉 탑3", value=f"{top3_rate*100:.2f}%", inline=True)
    embed.add_field(name="🎯 사냥", value=f"{avg_hunts:.2f}", inline=True)
    
    # 캐릭터 통계 정보 추가 (상위 3개 캐릭터)
    character_stats = stats.get('characterStats', [])
    if character_stats:
        # 게임 수 기준으로 정렬하여 상위 3개 선택
        top_characters = sorted(character_stats, key=lambda x: x.get('totalGames', 0), reverse=True)[:3]
        
        character_info = []
        for char in top_characters:
            char_code = char.get('characterCode', 0)
            char_games = char.get('totalGames', 0)
            char_wins = char.get('wins', 0)
            char_win_rate = (char_wins / char_games * 100) if char_games > 0 else 0.0
            
            # 캐릭터 이름 매핑
            char_name = get_character_name(char_code)
            character_info.append(f"**{char_name}**: {char_games}게임 ({char_win_rate:.1f}%)")
        
        if character_info:
            embed.add_field(
                name="🎭 주요 캐릭터",
                value="\n".join(character_info),
                inline=False
            )
    
    # 푸터 추가
    footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)
    
    return embed, None

def create_dakgg_view(nickname: str) -> discord.ui.View:
    """dak.gg 링크 버튼을 생성합니다."""
    view = discord.ui.View()
    button = discord.ui.Button(
        style=discord.ButtonStyle.link,
        label="DAK.GG 바로가기",
        emoji=EMOJIS['chart'],
        url=f"https://dak.gg/er/players/{nickname}"
    )
    view.add_item(button)
    return view

class Rank(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="랭크", description="유저의 랭크 정보를 조회합니다")
    @app_commands.describe(닉네임="조회할 유저의 닉네임 (2-20자, 특수문자 제외)")
    @handle_errors(user_message="랭크 정보를 가져오는 중 오류가 발생했습니다.")
    async def rank_command(self, interaction: discord.Interaction, 닉네임: str):
        """유저의 랭크 정보를 조회합니다."""
        # 입력 검증
        try:
            validated_nickname = validate_nickname(닉네임)
        except Exception as e:
            embed = create_error_embed("입력 오류", str(e), self.client)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 로딩 메시지 표시
        loading_embed = create_loading_embed(
            "랭크 조회 중...",
            f"`{validated_nickname}`님의 랭크 정보를 불러오고 있습니다.",
            self.client
        )
        await interaction.response.send_message(embed=loading_embed)
        
        # 시즌 정보 조회
        season_id = await get_current_season_id()
        if not season_id:
            raise APIError("시즌 정보를 가져올 수 없습니다.", "현재 시즌 정보를 가져올 수 없습니다.\n잠시 후 다시 시도해주세요.")

        # 시즌 정보 가져오기
        season_info = await get_season_info()
        season_name = season_info.name if season_info else f"시즌 {season_id}"

        # 유저 UID 조회
        user_id = await self.client.get_user_nickname(validated_nickname)
        if not user_id:
            raise NotFoundError(
                f"유저를 찾을 수 없습니다: {validated_nickname}",
                f"'{validated_nickname}' 유저를 찾을 수 없습니다.\n닉네임을 다시 확인해주세요."
            )

        # 유저 통계 조회
        stats = await fetch_user_stats_solo(self.client, user_id, season_id, use_cache=True)
        if not stats:
            raise NotFoundError(
                f"랭크 정보가 없습니다: {validated_nickname}",
                f"'{validated_nickname}' 유저의 {season_name} 랭크 게임 기록이 없습니다."
            )

        embed, _ = create_rank_embed(validated_nickname, stats, self.client)
        view = create_dakgg_view(validated_nickname)
        await interaction.edit_original_response(embed=embed, view=view)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Rank(client))

