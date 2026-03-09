import discord
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, NamedTuple
from client import ERClient
from discord import app_commands
from discord.ext import commands
import asyncio

from utils.config import config
from utils.embeds import create_info_embed, create_error_embed
from utils.errors import handle_errors, validate_nickname, NotFoundError, APIError
from utils.logging_config import get_logger
from utils.emojis import EMOJIS

logger = get_logger('플탐')

class GameStats(NamedTuple):
    """게임 통계 정보를 저장하는 네임드 튜플"""
    date: datetime.date
    duration: int
    character_code: str
    rank: int
    game_mode: str

class PlayTimeStats(NamedTuple):
    """플레이 타임 통계 정보를 저장하는 네임드 튜플"""
    total_seconds: int
    daily_stats: Dict[datetime.date, int]
    games_played: int
    avg_duration: float
    most_played_date: datetime.date
    most_played_time: int

# 요일 상수
WEEKDAYS = {
    0: '월',
    1: '화',
    2: '수',
    3: '목',
    4: '금',
    5: '토',
    6: '일'
}

async def get_user_games(client, user_id: str, start_date: datetime.date) -> List[GameStats]:
    """유저의 게임 기록을 가져옵니다."""
    games = []
    next_cursor = None
    max_requests = 10  # 최대 요청 수 제한
    request_count = 0

    try:
        while request_count < max_requests:
            url = f"{config.api_url}/user/games/uid/{user_id}"
            if next_cursor:
                url += f"?next={next_cursor}"

            data = await client.api_client.get(url, use_cache=True)
            if data:
                current_games = data.get('userGames', data.get('games', []))
                
                # 날짜 체크 및 게임 추가
                for game in current_games:
                    try:
                        game_date = datetime.strptime(
                            game['startDtm'],
                            "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).date()
                        
                        if game_date < start_date:
                            return games
                        
                        games.append(GameStats(
                            date=game_date,
                            duration=game.get('duration', 0),
                            character_code=game.get('characterCode', ''),
                            rank=game.get('gameRank', 0),
                            game_mode=game.get('matchingMode', '')
                        ))
                    except (ValueError, KeyError):
                        continue

                if 'next' not in data or not data['next']:
                    break
                next_cursor = data['next']
                request_count += 1
            else:
                logger.error("게임 기록 조회 실패")
                break

        return games
    except Exception as e:
        logger.error(f"게임 기록 조회 중 오류: {e}", exc_info=True)
        raise

def calculate_play_time_stats(games: List[GameStats], dates: List[datetime.date]) -> PlayTimeStats:
    """플레이 타임 통계를 계산합니다."""
    daily_stats = {date: 0 for date in dates}
    
    # 게임별 플레이 시간 집계
    for game in games:
        if game.date in daily_stats:
            daily_stats[game.date] += game.duration

    total_seconds = sum(daily_stats.values())
    games_played = len(games)
    avg_duration = total_seconds / games_played if games_played > 0 else 0
    
    # 가장 많이 플레이한 날 찾기
    if daily_stats and any(time > 0 for time in daily_stats.values()):
        most_played_date = max(daily_stats.items(), key=lambda x: x[1])[0]
        most_played_time = daily_stats[most_played_date]
    else:
        most_played_date = dates[0] if dates else datetime.now().date()
        most_played_time = 0

    return PlayTimeStats(
        total_seconds=total_seconds,
        daily_stats=daily_stats,
        games_played=games_played,
        avg_duration=avg_duration,
        most_played_date=most_played_date,
        most_played_time=most_played_time
    )

def format_time(seconds: int) -> str:
    """초 단위 시간을 HH:MM:SS 형식으로 변환합니다."""
    if seconds < 0:
        return "00:00:00"
    
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_duration(seconds: int) -> str:
    """초 단위 시간을 사용자 친화적인 형식으로 변환합니다."""
    if seconds < 60:
        return f"{seconds}초"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}분"
    else:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        if minutes > 0:
            return f"{hours}시간 {minutes}분"
        else:
            return f"{hours}시간"

def get_activity_level(total_seconds: int) -> str:
    """플레이 시간에 따른 활동 레벨을 반환합니다."""
    if total_seconds == 0:
        return "😴 휴식 중"
    elif total_seconds < 14400:  # 4시간 미만 (일일 평균 34분 미만)
        return "🌱 초보자"
    elif total_seconds < 36000:  # 10시간 미만 (일일 평균 1시간 26분 미만)
        return "🎯 적당히"
    elif total_seconds < 72000:  # 20시간 미만 (일일 평균 2시간 51분 미만)
        return "🔥 열정적"
    elif total_seconds < 126000:  # 35시간 미만 (일일 평균 5시간 미만)
        return "⚡ 하드코어"
    else:  # 35시간 이상 (일일 평균 5시간 이상)
        return "🚀 전설"

def create_playtime_embed(client, nickname: str, stats: PlayTimeStats) -> discord.Embed:
    """플레이 타임 임베드를 생성합니다."""
    # 활동 레벨 결정
    activity_level = get_activity_level(stats.total_seconds)
    
    # 플레이한 날짜 수 계산
    play_days = sum(1 for time in stats.daily_stats.values() if time > 0)
    
    # 임베드 생성
    embed = discord.Embed(
        title=f"{EMOJIS['fire']} {nickname}님의 플레이 타임",
        description=f"{activity_level} • 최근 7일간 게임 활동",
        color=config.embed_color
    )
    
    # 메인 통계 (2개 필드)
    embed.add_field(
        name=f"{EMOJIS['total']} **총 플레이 시간**",
        value=f"`{format_duration(stats.total_seconds)}` • {stats.games_played:,}판",
        inline=True
    )
    
    # 일일 평균 계산 (7일 기준만)
    daily_avg = stats.total_seconds // 7
    
    embed.add_field(
        name=f"{EMOJIS['average']} **일일 평균**",
        value=f"`{format_duration(daily_avg)}`",
        inline=True
    )
    
    # 일일 플레이 타임 차트 (시각적 표현)
    daily_chart = create_daily_chart(stats.daily_stats)
    embed.add_field(
        name=f"{EMOJIS['chart']} **일일 플레이 타임**",
        value=daily_chart,
        inline=False
    )
    
    # 추가 통계 정보
    if stats.games_played > 0:
        avg_game_duration = stats.total_seconds / stats.games_played
        embed.add_field(
            name=f"{EMOJIS['clock']} **게임 통계**",
            value=f"평균 게임 시간: `{format_duration(int(avg_game_duration))}`",
            inline=True
        )
    
    # 푸터 추가
    footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)
    
    return embed

def create_daily_chart(daily_stats: Dict[datetime.date, int]) -> str:
    """일일 플레이 타임을 시각적 차트로 표현합니다."""
    chart_lines = []
    max_time = max(daily_stats.values()) if daily_stats else 1
    
    for date, play_time in sorted(daily_stats.items()):
        weekday = WEEKDAYS[date.weekday()]
        date_str = f"{date.strftime('%m/%d')} ({weekday})"
        
        if play_time == 0:
            chart_lines.append(f"`{date_str}` ░░░░░░░░░░ `-`")
        else:
            # 진행률 바 생성 (10칸)
            progress = min(10, int((play_time / max_time) * 10))
            bar = "█" * progress + "░" * (10 - progress)
            time_str = format_duration(play_time)
            chart_lines.append(f"`{date_str}` {bar} `{time_str}`")
    
    return "\n".join(chart_lines)

class PlaytimeView(discord.ui.View):
    """플레이 타임 조회용 인터랙티브 뷰"""

    def __init__(self, nickname: str):
        super().__init__(timeout=config.view_timeout_static)
        self.nickname = nickname
        
        # DAK.GG 링크 버튼 추가
        dakgg_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="DAK.GG 바로가기",
            emoji=EMOJIS['chart'],
            url=f"https://dak.gg/er/players/{nickname}"
        )
        self.add_item(dakgg_button)

async def get_playtime_info(client: ERClient, nickname: str) -> Optional[PlayTimeStats]:
    """플레이어의 플레이 타임 정보를 가져옵니다."""
    try:
        # 유저 UID 조회
        user_id = await client.get_user_nickname(nickname)
        if not user_id:
            return None

        # 오늘을 포함한 최근 7일 날짜 리스트 생성 (오늘부터 6일 전까지)
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)) for i in range(7)]  # 오늘부터 6일 전까지
        start_date = dates[-1]  # 가장 오래된 날짜

        # 게임 기록 조회
        games = await get_user_games(client, user_id, start_date)
        if not games:
            return None

        # 통계 계산
        return calculate_play_time_stats(games, dates)
    except Exception as e:
        logger.error(f"플레이 타임 정보 조회 중 오류: {e}", exc_info=True)
        return None

class Playtime(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="플탐", description="최근 7일 플레이 타임 조회")
    @app_commands.describe(닉네임="조회할 유저의 닉네임 (2-20자, 특수문자 제외)")
    @handle_errors(user_message="플레이 타임 정보를 가져오는 중 오류가 발생했습니다.")
    async def playtime(
        self,
        interaction: discord.Interaction,
        닉네임: str
    ):
        """플레이어의 최근 7일 플레이 타임을 조회합니다."""
        try:
            # 닉네임 검증
            validated_nickname = validate_nickname(닉네임)
            
            # 로딩 메시지 표시
            loading_embed = discord.Embed(
                title=f"{EMOJIS['loading']} 플레이 타임 조회 중...",
                description=f"`{validated_nickname}`님의 게임 데이터를 분석하고 있습니다.",
                color=config.embed_color
            )
            await interaction.response.send_message(embed=loading_embed)

            # 플레이 타임 정보 조회
            stats = await get_playtime_info(self.client, validated_nickname)
            if not stats:
                # 데이터가 없는 경우 친화적인 메시지
                no_data_embed = discord.Embed(
                    title=f"😴 {validated_nickname}님의 플레이 기록",
                    description="최근 7일간 플레이 기록이 없습니다.\n\n💡 **다음과 같은 이유일 수 있습니다:**\n• 최근에 게임을 하지 않았음\n• 닉네임이 정확하지 않음\n• 게임 데이터가 아직 업데이트되지 않음",
                    color=config.embed_color
                )
                no_data_embed.add_field(
                    name="🔍 **확인 방법**",
                    value=f"• [DAK.GG](https://dak.gg/er/players/{validated_nickname})에서 닉네임 확인\n• 게임 내에서 최근 플레이 기록 확인",
                    inline=False
                )
                no_data_embed.set_footer(text=f"몽실봇 • {len(self.client.guilds)}개의 서버에서 활동 중")
                
                view = PlaytimeView(validated_nickname)
                await interaction.edit_original_response(embed=no_data_embed, view=view)
                return

            # 성공적인 결과 표시
            embed = create_playtime_embed(self.client, validated_nickname, stats)
            view = PlaytimeView(validated_nickname)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"플탐 명령어 실행 중 오류: {e}", exc_info=True)
            error_embed = create_error_embed(
                "오류 발생",
                "플레이 타임 정보를 가져오는 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요."
            )
            try:
                await interaction.edit_original_response(embed=error_embed)
            except discord.NotFound:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Playtime(client)) 