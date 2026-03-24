import asyncio
import discord
from discord.ext import commands
from discord import app_commands, ui
from typing import List, Dict, Any, NamedTuple, Optional
from client import ERClient
from commands.season import get_current_season_id
import math

from utils.config import config
from utils.layouts import create_error_layout, create_loading_layout, footer_text, CooldownLayoutView
from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.ranking_image_generator import create_ranking_image
from utils.rank_helpers import fetch_user_stats_solo, fetch_ranking_data

logger = get_logger('랭킹')

RANKS_PER_PAGE = 10  # 페이지당 10명씩 표시
TOTAL_RANKS = 100

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

class PaginationView(CooldownLayoutView):
    def __init__(self, client: ERClient, season_id: int, total_pages: int, first_page_users: List[RankUser], season_name: str):
        super().__init__(timeout=config.view_timeout_interactive)
        self.client = client
        self.season_id = season_id
        self.current_page = 1
        self.total_pages = total_pages
        self.page_cache: Dict[int, List[RankUser]] = {1: first_page_users}
        self.season_name = season_name

        self.build_layout()

    def build_layout(self):
        """현재 페이지 기준으로 레이아웃을 빌드합니다."""
        self.clear_items()

        # Container - children을 positional args로 전달
        self.add_item(ui.Container(
            ui.TextDisplay(f"### 🏆 {self.season_name} - KR 랭킹"),
            ui.MediaGallery(discord.MediaGalleryItem(media="attachment://ranking.png")),
            ui.Separator(visible=False),
            ui.TextDisplay(footer_text(self.client)),
            accent_colour=discord.Colour.blurple(),
        ))

        # Pagination ActionRow
        row = ui.ActionRow(
            ui.Button(label="◀️", style=discord.ButtonStyle.primary, custom_id="prev", disabled=(self.current_page == 1)),
            ui.Button(label=f"{self.current_page}/{self.total_pages}", style=discord.ButtonStyle.secondary, disabled=True, custom_id="indicator"),
            ui.Button(label="▶️", style=discord.ButtonStyle.primary, custom_id="next", disabled=(self.current_page == self.total_pages)),
        )
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """버튼 클릭을 핸들링합니다. (1초 쿨다운 적용)"""
        if not await super().interaction_check(interaction):
            return False

        custom_id = interaction.data.get("custom_id")
        if custom_id == "prev" and self.current_page > 1:
            self.current_page -= 1
        elif custom_id == "next" and self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # disabled 버튼이나 indicator 클릭 시 defer로 응답 처리
            await interaction.response.defer()
            return False

        await self.update_page(interaction)
        return False

    async def update_page(self, interaction: discord.Interaction):
        """페이지를 업데이트합니다. 캐시에 없으면 lazy-load합니다."""
        try:
            await interaction.response.defer()

            # 캐시 확인, 없으면 해당 페이지만 로드
            users = self.page_cache.get(self.current_page)
            if users is None:
                users = await get_ranking_info(self.client, self.season_id, self.current_page, fetch_stats=True)
                self.page_cache[self.current_page] = users or []

            if not users:
                return

            # 이미지 생성
            image_bytes = create_ranking_image(users, self.current_page, self.total_pages, self.season_name)

            self.build_layout()

            # 이미지 파일로 첨부
            file = discord.File(image_bytes, filename="ranking.png")
            await interaction.edit_original_response(view=self, attachments=[file])
        except Exception as e:
            logger.error(f"페이지 업데이트 중 오류 발생: {e}", exc_info=True)


async def get_ranking_info(client: ERClient, season_id: int, page: int = 1, fetch_stats: bool = True) -> Optional[List[RankUser]]:
    """랭킹 정보를 가져옵니다. 유저별 통계는 병렬로 조회합니다."""
    try:
        ranking_data = await fetch_ranking_data(client, season_id, use_cache=True)
        if ranking_data is None:
            return None

        # 페이지네이션 적용
        start_idx = (page - 1) * RANKS_PER_PAGE
        end_idx = min(start_idx + RANKS_PER_PAGE, len(ranking_data))
        page_data = ranking_data[start_idx:end_idx]

        if not fetch_stats:
            return [
                RankUser(
                    rank=ud.get('rank', 0),
                    nickname=ud.get('nickname', ''),
                    mmr=ud.get('mmr', 0),
                    user_id=ud.get('nickname', ''),
                )
                for ud in page_data
            ]

        async def fetch_single_user(user_data):
            """개별 유저의 통계를 가져옵니다."""
            nickname = user_data.get('nickname', '')
            user_id = None
            stats = None

            if nickname:
                user_id = await client.get_user_nickname(nickname)

            if user_id:
                try:
                    stats = await fetch_user_stats_solo(client, user_id, season_id, use_cache=True)
                except Exception:
                    stats = None

            games = wins = 0
            avg_rank = avg_kills = 0.0
            character_stats = []

            if stats:
                games = int(stats.get('totalGames', 0))
                wins = int(stats.get('totalWins', 0))
                avg_rank = float(stats.get('averageRank', 0.0))
                avg_kills = float(stats.get('averageKills', 0.0))
                character_stats = stats.get('characterStats', [])

            return RankUser(
                rank=user_data.get('rank', 0),
                nickname=nickname,
                mmr=user_data.get('mmr', 0),
                user_id=user_id if user_id else nickname,
                games=games,
                wins=wins,
                avg_rank=avg_rank,
                avg_kills=avg_kills,
                character_stats=character_stats
            )

        users = await asyncio.gather(*[fetch_single_user(ud) for ud in page_data])
        return list(users)
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
        # 로딩 메시지 표시
        loading = create_loading_layout(
            "랭킹 조회 중...",
            "상위 100명의 랭킹 데이터를 불러오고 있습니다.",
            self.client
        )
        await interaction.response.send_message(view=loading)

        season_id = await get_current_season_id()
        if not season_id:
            error_layout = create_error_layout("시즌 정보 오류", "현재 시즌 정보를 가져올 수 없습니다.", self.client)
            await interaction.edit_original_response(view=error_layout, embeds=[], attachments=[])
            return

        # 시즌 정보 가져오기
        from commands.season import get_season_info
        season_info = await get_season_info()
        season_name = season_info.name if season_info else "현재 시즌"

        # 랭킹 데이터 가져오기 (1회 호출로 1000명 데이터 수신, 이후 캐시 사용)
        ranking_data = await fetch_ranking_data(self.client, season_id, use_cache=True)
        if not ranking_data:
            error_layout = create_error_layout("오류 발생", "랭킹 정보를 가져올 수 없습니다.", self.client)
            await interaction.edit_original_response(view=error_layout, embeds=[], attachments=[])
            return

        total_pages = math.ceil(min(len(ranking_data), TOTAL_RANKS) / RANKS_PER_PAGE)

        # 첫 페이지만 로드 (나머지는 페이지 이동 시 lazy-load)
        first_page_users = await get_ranking_info(self.client, season_id, 1, fetch_stats=True)
        if not first_page_users:
            error_layout = create_error_layout("오류 발생", "랭킹 정보를 가져올 수 없습니다.", self.client)
            await interaction.edit_original_response(view=error_layout, embeds=[], attachments=[])
            return

        # 첫 페이지 이미지 생성
        image_bytes = create_ranking_image(first_page_users, 1, total_pages, season_name)

        # PaginationView 생성 (첫 페이지 캐시 전달, 이후 페이지는 on-demand)
        view = PaginationView(self.client, season_id, total_pages, first_page_users, season_name)

        # 이미지 파일로 첨부
        file = discord.File(image_bytes, filename="ranking.png")
        await interaction.edit_original_response(view=view, embeds=[], attachments=[file])

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Ranking(client))
