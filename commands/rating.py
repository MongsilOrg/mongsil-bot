import discord
from discord import Embed, Color
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, Any, NamedTuple, Tuple
from client import ERClient
import aiohttp
from commands.season import get_current_season_id, get_season_info

from utils.config import config
from utils.embeds import create_info_embed, create_error_embed
from utils.errors import handle_errors, APIError
from utils.logging_config import get_logger
from utils.emojis import EMOJIS

logger = get_logger('레이팅')

async def fetch_top_ranks(client: ERClient, season_id: int) -> Optional[list]:
    """상위 랭킹 데이터를 한 번에 가져옵니다."""
    try:
        # KR 서버 코드 10을 하드코딩하고 한 번의 호출로 1000등까지 데이터 가져오기
        url = f"{config.api_url}/rank/top/{season_id}/3/10"
        
        data = await client.api_client.get(url, use_cache=False)
        if data and data.get('code') == 200:
            top_ranks = data.get('topRanks', [])
            return top_ranks
        else:
            logger.error(f"랭킹 조회 API 오류: {data.get('message') if data else 'No response'}")
            return None
    except Exception as e:
        logger.error(f"랭킹 조회 중 오류 발생: {e}", exc_info=True)
        return None

async def fetch_rating_info(client: ERClient, season_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """300등과 1000등의 유저 정보를 한 번의 API 호출로 가져옵니다."""
    try:
        top_ranks = await fetch_top_ranks(client, season_id)
        if not top_ranks:
            return None, None
        
        rank_300 = None
        rank_1000 = None
        
        # 가져온 데이터에서 300등과 1000등을 찾기
        # API 응답이 순위별로 정렬되어 있다고 가정하고 효율적으로 검색
        for user in top_ranks:
            user_rank = user.get('rank')
            if user_rank == 300:
                rank_300 = user
            elif user_rank == 1000:
                rank_1000 = user
            
            # 둘 다 찾았으면 루프 종료
            if rank_300 and rank_1000:
                break
        
        return rank_300, rank_1000
    except Exception as e:
        logger.error(f"레이팅 정보 조회 중 오류 발생: {e}", exc_info=True)
        return None, None

def create_rating_embed(rank_300: Optional[Dict], rank_1000: Optional[Dict], client: ERClient, season_name: str) -> Embed:
    """레이팅 정보 임베드를 생성합니다."""
    embed = Embed(
        title=f"{EMOJIS['trophy']} {season_name} KR 레이팅 컷",
        color=config.embed_color
    )

    # 300등 정보
    if rank_300:
        mmr_300 = rank_300.get('mmr', 0)
        nickname_300 = rank_300.get('nickname', '알 수 없음')
        embed.add_field(
            name=f"{EMOJIS['crown']} 이터니티 컷 (300등)",
            value=f"```닉네임: {nickname_300}\nMMR: {mmr_300:,}```",
            inline=False
        )
    else:
        embed.add_field(
            name=f"{EMOJIS['crown']} 이터니티 컷 (300등)",
            value="```정보를 가져올 수 없습니다.```",
            inline=False
        )

    # 1000등 정보
    if rank_1000:
        mmr_1000 = rank_1000.get('mmr', 0)
        nickname_1000 = rank_1000.get('nickname', '알 수 없음')
        embed.add_field(
            name=f"{EMOJIS['sparkles']} 데미갓 컷 (1000등)",
            value=f"```닉네임: {nickname_1000}\nMMR: {mmr_1000:,}```",
            inline=False
        )
    else:
        embed.add_field(
            name=f"{EMOJIS['sparkles']} 데미갓 컷 (1000등)",
            value="```정보를 가져올 수 없습니다.```",
            inline=False
        )

    footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)
    
    return embed


class Rating(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="이터컷", description="이터니티/데미갓 컷 조회")
    @handle_errors(user_message="레이팅 정보를 가져오는 중 오류가 발생했습니다.")
    async def rating_command(self, interaction: discord.Interaction):
        """현재 시즌의 이터니티/데미갓 컷을 확인합니다."""
        try:
            await interaction.response.defer()
            
            season_id = await get_current_season_id()
            if not season_id:
                logger.error("현재 시즌 ID를 가져올 수 없습니다.")
                error_embed = create_error_embed(
                    "시즌 정보 오류",
                    "현재 시즌 정보를 가져올 수 없습니다.\n잠시 후 다시 시도해주세요.",
                    self.client
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # 시즌 정보 가져오기
            season_info = await get_season_info()
            season_name = season_info.name if season_info else f"시즌 {season_id}"

            # 레이팅 정보 조회 (한 번의 API 호출로 300등과 1000등 모두 가져오기)
            rank_300, rank_1000 = await fetch_rating_info(self.client, season_id)
            
            if not rank_300 and not rank_1000:
                error_embed = create_error_embed(
                    "레이팅 정보 없음",
                    f"{season_name}의 레이팅 정보를 가져올 수 없습니다.\n"
                    "시즌이 아직 시작되지 않았거나 API에 문제가 있을 수 있습니다.",
                    self.client
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            embed = create_rating_embed(rank_300, rank_1000, self.client, season_name)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"레이팅 명령어 실행 중 오류 발생: {e}", exc_info=True)
            error_embed = create_error_embed(
                "오류 발생",
                "레이팅 정보를 가져오는 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.",
                self.client
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Rating(client)) 