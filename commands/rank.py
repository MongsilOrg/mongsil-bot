import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
from typing import Dict, Any
from client import ERClient

from commands.season import get_current_season_id, get_season_info
from utils.layouts import create_loading_layout, footer_text
from utils.errors import handle_errors, validate_nickname, NotFoundError, APIError
from utils.logging_config import get_logger
from utils.character_names import get_character_name
from utils.rank_helpers import fetch_user_stats_solo
from utils.tier_system import TierSystem
from utils.emojis import EMOJIS

logger = get_logger('랭크')


def create_rank_layout(nickname: str, stats: Dict[str, Any], client: ERClient) -> ui.LayoutView:
    """랭크 정보 LayoutView를 생성합니다."""
    # 기본 정보 파싱
    mmr = int(stats.get('mmr', 0))
    rank = int(stats.get('rank', 0))
    rank_size = int(stats.get('rankSize', 0))
    games = int(stats.get('totalGames', 0))
    wins = int(stats.get('totalWins', 0))
    avg_rank = float(stats.get('averageRank', 0.0))
    avg_kills = float(stats.get('averageKills', 0.0))
    avg_assists = float(stats.get('averageAssistants', 0.0))
    avg_hunts = float(stats.get('averageHunts', 0.0))
    top1_rate = float(stats.get('top1', 0.0))
    top3_rate = float(stats.get('top3', 0.0))

    # API에서 실제 닉네임 가져오기 (대소문자 구분 등)
    actual_nickname = stats.get('nickname', nickname)

    # 계산이 필요한 통계
    win_rate = (wins / games * 100) if games > 0 else 0.0

    # 티어 정보 계산
    tier = TierSystem.get_tier(mmr, rank)

    # 상위 백분율 계산
    top_percentage = (rank / rank_size * 100) if rank_size > 0 else 0.0

    # 티어 아이콘 URL
    icon_name = TierSystem.get_tier_icon(tier)
    icon_url = f"https://cdn.mongsil.dev/mongsilbot/tier/{icon_name}.png"

    # LayoutView 구성
    view = ui.LayoutView()

    container_items = []

    # 헤더 섹션: 닉네임 + 티어 정보 + 썸네일
    header_text = (
        f"## {actual_nickname}\n"
        f"**{tier}** | {mmr:,} RP\n"
        f"-# #{rank:,}등 / {rank_size:,}명 중, 상위 {top_percentage:.2f}%"
    )
    container_items.append(
        ui.Section(
            ui.TextDisplay(header_text),
            accessory=ui.Thumbnail(media=icon_url)
        )
    )

    container_items.append(ui.Separator())

    stats_text = (
        f"**{games:,}**게임 | **{wins:,}**승 | 승률 **{win_rate:.0f}%**\n"
        f"평균 **{avg_rank:.1f}**등 | 탑1 **{top1_rate*100:.0f}%** | 탑3 **{top3_rate*100:.0f}%**\n"
        f"평균 킬 **{avg_kills:.1f}** | 어시 **{avg_assists:.1f}** | 사냥 **{avg_hunts:.1f}**"
    )
    container_items.append(ui.TextDisplay(stats_text))

    # 캐릭터 통계 정보 추가 (상위 3개 캐릭터)
    character_stats = stats.get('characterStats', [])
    if character_stats:
        top_characters = sorted(character_stats, key=lambda x: x.get('totalGames', 0), reverse=True)[:3]

        if top_characters:
            container_items.append(ui.Separator())
            char_lines = []
            for char in top_characters:
                char_code = char.get('characterCode', 0)
                char_games = char.get('totalGames', 0)
                char_wins = char.get('wins', 0)
                char_win_rate = (char_wins / char_games * 100) if char_games > 0 else 0.0

                char_name = get_character_name(char_code)
                char_lines.append(f"**{char_name}** {char_games}게임, 승률 {char_win_rate:.0f}%")
            container_items.append(ui.TextDisplay("### 모스트 캐릭터\n" + "\n".join(char_lines)))

    # 푸터
    container_items.append(ui.Separator(visible=False))
    container_items.append(ui.TextDisplay(footer_text(client)))

    view.add_item(ui.Container(*container_items, accent_colour=discord.Colour.blurple()))

    # DAK.GG 링크 버튼
    view.add_item(
        ui.ActionRow(
            ui.Button(
                style=discord.ButtonStyle.link,
                label="DAK.GG",
                emoji=EMOJIS['chart'],
                url=f"https://dak.gg/er/players/{actual_nickname}"
            )
        )
    )

    return view


class Rank(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="랭크", description="유저 랭크 정보 조회")
    @app_commands.describe(닉네임="조회할 유저의 닉네임 (2-20자, 특수문자 제외)")
    @handle_errors(user_message="랭크 정보를 가져오는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.")
    async def rank_command(self, interaction: discord.Interaction, 닉네임: str):
        """유저의 랭크 정보를 조회합니다."""
        # 입력 검증 (실패 시 handle_errors가 user_message를 ephemeral로 전송)
        validated_nickname = validate_nickname(닉네임)

        # 로딩 메시지 표시
        loading_view = create_loading_layout(
            "랭크 조회 중...",
            f"`{validated_nickname}`님의 랭크 정보를 불러오고 있어요.",
            self.client
        )
        await interaction.response.send_message(view=loading_view)

        # 시즌 정보 조회
        season_id = await get_current_season_id()
        if not season_id:
            raise APIError("시즌 정보를 가져올 수 없습니다.", "현재 시즌 정보를 가져올 수 없어요.\n잠시 후 다시 시도해주세요.")

        # 시즌 정보 가져오기
        season_info = await get_season_info()
        season_name = season_info.name if season_info else f"시즌 {season_id}"

        # 유저 UID 조회
        user_id = await self.client.get_user_nickname(validated_nickname)
        if not user_id:
            raise NotFoundError(
                f"유저를 찾을 수 없습니다: {validated_nickname}",
                f"'{validated_nickname}' 유저를 찾을 수 없어요.\n닉네임을 다시 확인해주세요."
            )

        # 유저 통계 조회
        stats = await fetch_user_stats_solo(self.client, user_id, season_id, use_cache=True)
        if not stats:
            raise NotFoundError(
                f"랭크 정보가 없습니다: {validated_nickname}",
                f"'{validated_nickname}' 유저의 {season_name} 랭크 게임 기록이 없어요."
            )

        view = create_rank_layout(validated_nickname, stats, self.client)
        await interaction.edit_original_response(view=view, embeds=[], attachments=[])

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Rank(client))
