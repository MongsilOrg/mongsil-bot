import discord
from discord import Embed, Color
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Any, NamedTuple, Optional, Tuple
from client import ERClient
import aiohttp
from commands.season import get_current_season_id
import math
from datetime import datetime, timedelta

from utils.config import config
from utils.embeds import create_info_embed, create_error_embed, create_loading_embed
from utils.errors import handle_errors, APIError
from utils.logging_config import get_logger
from utils.ranking_image_generator import create_ranking_embed_with_image
from utils.rank_helpers import fetch_user_stats_solo, fetch_ranking_data
from utils.tier_system import TierSystem

logger = get_logger('랭킹')

RANKS_PER_PAGE = 10  # 페이지당 10명씩 표시
TOTAL_RANKS = 100
CACHE_TTL = timedelta(minutes=5)  # 캐시 유효 시간: 5분

class RankUser(NamedTuple):
    """랭킹 유저 정보를 저장하는 네임드 튜플"""
    rank: int
    nickname: str
    mmr: int
    user_id: str
    games: int = 0
    wins: int = 0
    avg_rank: float = 0.0
    avg_kills: float = 0.0
    character_stats: list = None

class PaginationView(discord.ui.View):
    def __init__(self, client: ERClient, season_id: int, total_pages: int, cached_users: List[List[RankUser]], season_name: str):
        super().__init__(timeout=config.view_timeout_interactive)
        self.client = client
        self.season_id = season_id
        self.current_page = 1
        self.total_pages = total_pages
        self.cached_users = cached_users  # 모든 페이지의 유저 데이터 캐시
        self.season_name = season_name

        self.update_buttons()

    def update_buttons(self):
        """버튼 상태를 업데이트합니다."""
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == self.total_pages
        self.page_indicator.label = f"{self.current_page}/{self.total_pages}"

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지로 이동합니다."""
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_page(interaction)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지로 이동합니다."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self.update_page(interaction)

    async def update_page(self, interaction: discord.Interaction):
        """페이지를 업데이트합니다 (캐시된 데이터 사용)."""
        try:
            # 캐시된 데이터에서 현재 페이지의 유저 정보 가져오기
            users = self.cached_users[self.current_page - 1]
            if not users:
                await interaction.response.send_message("랭킹 정보를 가져올 수 없습니다.", ephemeral=True)
                return

            # 이미지와 임베드 생성
            embed, image_bytes = create_ranking_embed_with_image(
                users, self.current_page, self.total_pages, self.season_name, self.client
            )

            self.update_buttons()

            # 이미지 파일로 첨부
            file = discord.File(image_bytes, filename="ranking.png")
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        except Exception as e:
            logger.error(f"페이지 업데이트 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("페이지를 업데이트하는 중 오류가 발생했습니다.", ephemeral=True)


async def get_ranking_info(client: ERClient, season_id: int, page: int = 1, fetch_stats: bool = True) -> Optional[List[RankUser]]:
    """랭킹 정보를 가져옵니다."""
    try:
        ranking_data = await fetch_ranking_data(client, season_id, use_cache=True)
        if ranking_data is None:
            return None

        # 페이지네이션 적용
        start_idx = (page - 1) * RANKS_PER_PAGE
        end_idx = min(start_idx + RANKS_PER_PAGE, len(ranking_data))
        page_data = ranking_data[start_idx:end_idx]

        users = []
        for user_data in page_data:
            games = wins = 0
            avg_rank = avg_kills = 0.0
            stats = None
            
            # API 응답에는 userId가 없으므로 닉네임으로 userId 조회
            nickname = user_data.get('nickname', '')
            user_id = None
            
            # 닉네임으로 userId 조회 시도
            if nickname and fetch_stats:
                user_id = await client.get_user_nickname(nickname)
                if not user_id:
                    logger.warning(f"닉네임으로 userId를 찾을 수 없습니다: {nickname}")
            
            # userId가 있으면 통계 정보 가져오기
            if fetch_stats and user_id:
                try:
                    stats = await fetch_user_stats_solo(client, user_id, season_id, use_cache=True)
                except Exception:
                    stats = None
                if stats:
                    games = int(stats.get('totalGames', 0))
                    wins = int(stats.get('totalWins', 0))
                    avg_rank = float(stats.get('averageRank', 0.0))
                    avg_kills = float(stats.get('averageKills', 0.0))
            
            # characterStats는 stats에서 가져와야 함 (user_data가 아닌)
            character_stats = []
            if fetch_stats and stats:
                character_stats = stats.get('characterStats', [])
            
            # userId가 없으면 닉네임을 user_id로 사용
            final_user_id = user_id if user_id else nickname
            
            users.append(RankUser(
                rank=user_data.get('rank', 0),
                nickname=nickname,
                mmr=user_data.get('mmr', 0),
                user_id=final_user_id,
                games=games,
                wins=wins,
                avg_rank=avg_rank,
                avg_kills=avg_kills,
                character_stats=character_stats
            ))
        return users
    except Exception as e:
        logger.error(f"랭킹 정보 처리 중 오류 발생: {e}", exc_info=True)
        return None

class Ranking(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="랭킹", description="랭킹을 보여줍니다")
    @handle_errors(user_message="랭킹 정보를 가져오는 중 오류가 발생했습니다.")
    async def ranking_command(self, interaction: discord.Interaction):
        """랭킹을 보여줍니다."""
        try:
            # 로딩 메시지 표시
            loading_embed = create_loading_embed(
                "랭킹 조회 중...",
                "상위 100명의 랭킹 데이터를 불러오고 있습니다.",
                self.client
            )
            await interaction.response.send_message(embed=loading_embed)

            season_id = await get_current_season_id()
            if not season_id:
                await interaction.followup.send("현재 시즌 정보를 가져올 수 없습니다.", ephemeral=True)
                return

            # 시즌 정보 가져오기
            from commands.season import get_season_info
            season_info = await get_season_info()
            season_name = season_info.name if season_info else "현재 시즌"

            # 모든 페이지의 유저 정보를 미리 로드하여 캐시
            total_pages = math.ceil(TOTAL_RANKS / RANKS_PER_PAGE)
            cached_users = []

            for page in range(1, total_pages + 1):
                users = await get_ranking_info(self.client, season_id, page, fetch_stats=True)
                if not users:
                    # 일부 페이지 로드 실패 시 빈 리스트 추가
                    cached_users.append([])
                    logger.warning(f"페이지 {page} 로드 실패")
                else:
                    cached_users.append(users)

            # 첫 페이지가 없으면 에러
            if not cached_users or not cached_users[0]:
                error_embed = create_error_embed("오류 발생", "랭킹 정보를 가져올 수 없습니다.", self.client)
                await interaction.edit_original_response(embed=error_embed)
                return

            # 이미지와 임베드 생성
            embed, image_bytes = create_ranking_embed_with_image(
                cached_users[0], 1, total_pages, season_name, self.client
            )
            view = PaginationView(self.client, season_id, total_pages, cached_users, season_name)

            # 이미지 파일로 첨부
            file = discord.File(image_bytes, filename="ranking.png")
            await interaction.edit_original_response(embed=embed, view=view, attachments=[file])
        except Exception as e:
            logger.error(f"랭킹 명령어 실행 중 오류 발생: {e}", exc_info=True)
            error_embed = create_error_embed(
                "오류 발생",
                "랭킹 정보를 가져오는 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.",
                self.client
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.edit_original_response(embed=error_embed)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Ranking(client)) 