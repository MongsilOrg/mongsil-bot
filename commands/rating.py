from datetime import datetime, timezone

import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, Tuple
from client import ERClient
from commands.season import get_ranked_season

from utils.layouts import create_error_layout
from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.rank_helpers import RANKING_SERVER, SERVER_NAMES, fetch_ranking_data

logger = get_logger('레이팅')

async def fetch_rating_info(client: ERClient, season_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """300등과 1000등의 유저 정보를 한 번의 API 호출로 가져옵니다."""
    try:
        top_ranks = await fetch_ranking_data(client, season_id, use_cache=True)
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

def create_rating_layout(rank_300: Optional[Dict], rank_1000: Optional[Dict], season_name: str) -> ui.LayoutView:
    """레이팅 정보 LayoutView를 생성합니다."""
    def cut_text(tier: str, rank: int, user: Optional[Dict]) -> str:
        value = f"**{user.get('mmr', 0):,}** RP" if user else "정보 없음"
        return f"{tier} {value}\n-# {rank}등"

    now_ts = int(datetime.now(timezone.utc).timestamp())
    children = [
        ui.TextDisplay(f"### {season_name} {SERVER_NAMES[RANKING_SERVER]} 이터컷"),
        ui.Separator(),
        ui.TextDisplay(cut_text("이터니티", 300, rank_300)),
        ui.Separator(),
        ui.TextDisplay(cut_text("데미갓", 1000, rank_1000)),
        ui.Separator(),
    ]
    footnote = f"<t:{now_ts}:t> 기준"
    if rank_300 and rank_1000:
        footnote = f"컷 차이 {rank_300.get('mmr', 0) - rank_1000.get('mmr', 0):,} RP | " + footnote
    children.append(ui.TextDisplay(f"-# {footnote}"))

    view = ui.LayoutView()
    view.add_item(ui.Container(*children, accent_colour=discord.Colour.blurple()))
    return view


class Rating(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="이터컷", description="이터니티와 데미갓 RP 컷 조회")
    @handle_errors(user_message="레이팅 정보를 가져오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    async def rating_command(self, interaction: discord.Interaction):
        """현재 시즌의 이터니티/데미갓 컷을 확인합니다."""
        await interaction.response.defer()

        season = await get_ranked_season()
        if not season:
            error_view = create_error_layout("현재 시즌 정보를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
            # 공개 defer 뒤 첫 followup이라 ephemeral은 적용되지 않는다
            await interaction.followup.send(view=error_view)
            return
        season_id, season_name = season

        # 레이팅 정보 조회 (한 번의 API 호출로 300등과 1000등 모두 가져오기)
        rank_300, rank_1000 = await fetch_rating_info(self.client, season_id)

        if not rank_300 and not rank_1000:
            error_view = create_error_layout(f"{season_name} 이터컷을 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
            await interaction.followup.send(view=error_view)
            return

        view = create_rating_layout(rank_300, rank_1000, season_name)
        await interaction.followup.send(view=view)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Rating(client))
