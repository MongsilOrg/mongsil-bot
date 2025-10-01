import discord
from discord import Embed, Color
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, NamedTuple
import pytz
from client import ERClient

from utils.config import config
from utils.embeds import create_info_embed, create_error_embed
from utils.errors import handle_errors, APIError
from utils.logging_config import get_logger
from utils.emojis import SEASON_EMOJIS, SEASON_PROGRESS_EMOJIS, EMOJIS

logger = get_logger('시즌')

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 시즌 관련 상수
SEASON_ZERO_ID = 19  # 시즌 0이 되는 ID 값
SEASON_NAME_OFFSET = 9  # Season16은 시즌7이므로, 9를 빼면 됨

def get_season_name(season_id: int, season_name: str) -> str:
    """
    시즌 ID와 시즌 이름을 기반으로 한국어 시즌 이름을 생성합니다.
    
    Args:
        season_id: 시즌 ID
        season_name: API에서 받은 시즌 이름 (예: "Season16", "Pre-Season7")
        
    Returns:
        한국어로 번역된 시즌 이름
    """
    if season_id <= SEASON_ZERO_ID:
        return f"EA 시즌 {season_id}"
    
    try:
        # seasonName에서 시즌 번호 추출
        if season_name.startswith("Pre-Season"):
            season_number = int(season_name.replace("Pre-Season", ""))
            actual_season = season_number - SEASON_NAME_OFFSET
            return f"프리 시즌 {actual_season}"
        elif season_name.startswith("Season"):
            season_number = int(season_name.replace("Season", ""))
            actual_season = season_number - SEASON_NAME_OFFSET
            return f"정규 시즌 {actual_season}"
        else:
            return season_name
    except ValueError as e:
        logger.error(f"시즌 이름 파싱 오류: {e}")
        return season_name

class SeasonInfo(NamedTuple):
    """시즌 정보를 저장하는 네임드 튜플"""
    number: int
    start_date: datetime
    end_date: datetime
    name: str

async def fetch_season_data(season_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    API에서 시즌 정보를 가져옵니다.
    
    Args:
        season_id: 특정 시즌 ID를 찾을 경우 사용. None이면 현재 시즌(isCurrent=1)을 반환.
        
    Returns:
        시즌 정보 딕셔너리 또는 None
    """
    try:
        from utils.api_client import api_client
        
        # API URL을 config에서 가져오되, v2 버전 사용
        base_url = config.api_url.replace('/v1', '/v2')
        url = f'{base_url}/data/Season'
        
        data = await api_client.get(url, use_cache=True)
        
        if not data or 'data' not in data or not isinstance(data['data'], list) or len(data['data']) == 0:
            logger.error("시즌 API 응답 오류")
            return None
        
        # 특정 season_id를 찾는 경우
        if season_id is not None:
            for season in data['data']:
                if isinstance(season, dict) and season.get('seasonID') == season_id:
                    # 필수 필드 검증
                    required_fields = ['seasonID', 'seasonName', 'seasonStart', 'seasonEnd']
                    for field in required_fields:
                        if field not in season:
                            logger.error(f"시즌 데이터에 필수 필드 '{field}' 누락")
                            return None
                    return season
            return None
        
        # 현재 시즌 찾기 (isCurrent = 1)
        current_season = None
        for season in data['data']:
            if isinstance(season, dict) and season.get('isCurrent') == 1:
                current_season = season
                break
        
        if not current_season:
            return None
            
        # 필수 필드 검증
        required_fields = ['seasonID', 'seasonName', 'seasonStart', 'seasonEnd']
        for field in required_fields:
            if field not in current_season:
                logger.error(f"시즌 데이터에 필수 필드 '{field}' 누락")
                return None
        
        return current_season
        
    except Exception as e:
        logger.error(f"시즌 API 호출 중 오류: {e}", exc_info=True)
        return None

async def get_current_season_id() -> Optional[int]:
    """
    현재 시즌 ID를 가져옵니다.
    .env 파일의 SEASON_ID 환경변수에서만 가져옵니다.
    
    Returns:
        현재 시즌 ID 또는 None
    """
    try:
        # 환경변수에서만 시즌 ID 가져오기
        season_id = getattr(config, 'season_id', None)
        if season_id is not None:
            return season_id
        return None
    except Exception as e:
        logger.error(f"현재 시즌 ID 조회 중 오류: {e}", exc_info=True)
        return None

async def get_season_info() -> Optional[SeasonInfo]:
    """
    시즌 정보를 가져옵니다.
    
    Returns:
        SeasonInfo 객체 또는 None
    """
    try:
        # 환경변수에서만 시즌 ID 가져오기
        env_season_id = getattr(config, 'season_id', None)
        if env_season_id is None:
            logger.warning("환경변수 SEASON_ID가 설정되지 않았습니다")
            return None
        
        # 환경변수에서 시즌 날짜 정보 가져오기
        if not (getattr(config, 'season_start', None) and getattr(config, 'season_end', None)):
            logger.warning("환경변수 SEASON_START 또는 SEASON_END가 설정되지 않았습니다")
            return None
        
        try:
            env_start = datetime.strptime(config.season_start, '%Y-%m-%d %H:%M:%S')
            env_end = datetime.strptime(config.season_end, '%Y-%m-%d %H:%M:%S')
            start_date = KST.localize(env_start)
            end_date = KST.localize(env_end)
        except ValueError as e:
            logger.error(f"환경변수 시즌 날짜 파싱 오류: {e}", exc_info=True)
            return None
        
        # 환경변수에서 시즌 이름 가져오기
        season_name = getattr(config, 'season_name', None)
        if not season_name:
            # 환경변수가 없으면 기본 형식 사용
            season_name = f"시즌 {env_season_id}"

        return SeasonInfo(
            number=env_season_id,
            start_date=start_date,
            end_date=end_date,
            name=season_name
        )

    except Exception as e:
        logger.error(f"시즌 정보 계산 중 오류: {e}", exc_info=True)
        return None

def _calculate_season_progress(season_info: SeasonInfo) -> Tuple[float, str, str, str]:
    """
    시즌 진행도를 계산합니다.
    
    Args:
        season_info: 시즌 정보
        
    Returns:
        (진행도 퍼센트, 남은 시간 문자열, 상태 이모지, 상태 텍스트) 튜플
    """
    now = datetime.now(KST)
    
    # 시즌이 아직 시작되지 않은 경우
    if now < season_info.start_date:
        time_until_start = season_info.start_date - now
        days = time_until_start.days
        hours, remainder = divmod(time_until_start.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        remaining_time = f"{days}일 {hours}시간 {minutes}분 {seconds}초"
        return 0.0, remaining_time, SEASON_PROGRESS_EMOJIS['before_start'], "시즌 시작 전"

    # 시즌이 이미 종료된 경우
    if now > season_info.end_date:
        return 100.0, "0일 0시간 0분 0초", SEASON_PROGRESS_EMOJIS['finished'], "시즌 종료됨"
    
    # 진행도 계산
    total_duration = season_info.end_date - season_info.start_date
    elapsed_duration = now - season_info.start_date
    progress = min(max(elapsed_duration.total_seconds() / total_duration.total_seconds() * 100, 0), 100)
    
    # 남은 시간 계산
    time_left = season_info.end_date - now
    days = time_left.days
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    remaining_time = f"{days}일 {hours}시간 {minutes}분 {seconds}초"
    
    # 진행도에 따른 상태 이모지
    if progress < 25:
        status_emoji = SEASON_PROGRESS_EMOJIS['early']
        status_text = "시즌 초반"
    elif progress < 50:
        status_emoji = SEASON_PROGRESS_EMOJIS['first_half']
        status_text = "시즌 전반"
    elif progress < 75:
        status_emoji = SEASON_PROGRESS_EMOJIS['second_half']
        status_text = "시즌 후반"
    else:
        status_emoji = SEASON_PROGRESS_EMOJIS['final']
        status_text = "시즌 마무리"
    
    return progress, remaining_time, status_emoji, status_text

def _create_progress_bar(progress: float, length: int = 20) -> str:
    """
    진행도 바를 생성합니다.
    
    Args:
        progress: 진행도 (0-100)
        length: 바의 길이
        
    Returns:
        진행도 바 문자열
    """
    filled_length = int(length * progress / 100)
    
    # 진행도에 따른 다른 문자 사용
    if progress < 25:
        filled_char = '▱'
        empty_char = '▱'
    elif progress < 50:
        filled_char = '▰'
        empty_char = '▱'
    elif progress < 75:
        filled_char = '█'
        empty_char = '▱'
    else:
        filled_char = '█'
        empty_char = '░'
    
    return filled_char * filled_length + empty_char * (length - filled_length)


def create_season_embed(season_info: Optional[SeasonInfo], client: ERClient) -> discord.Embed:
    """
    시즌 정보 임베드를 생성합니다.
    
    Args:
        season_info: 시즌 정보
        client: Discord 클라이언트
        
    Returns:
        Discord 임베드 객체
    """
    if not season_info:
        return create_error_embed(
            "시즌 정보 오류",
            "현재 시즌 정보를 가져올 수 없습니다.\n잠시 후 다시 시도해주세요.",
            client
        )

    # 시즌 진행도 계산
    progress, remaining_time, status_emoji, status_text = _calculate_season_progress(season_info)
    progress_bar = _create_progress_bar(progress)
    
    # 시즌 타입에 따른 이모지 선택
    if "EA" in season_info.name:
        season_emoji = SEASON_EMOJIS['ea']
    elif "프리" in season_info.name:
        season_emoji = SEASON_EMOJIS['pre_season']
    else:
        season_emoji = SEASON_EMOJIS['regular']

    embed = discord.Embed(
        title=f"{season_emoji} {season_info.name}",
        description=f"{status_emoji} **{status_text}** • {progress:.1f}% 진행",
        color=config.embed_color
    )
    
    # 시즌 기간 정보 (간결한 형식)
    start_date_str = season_info.start_date.strftime("%m/%d %H시")
    end_date_str = season_info.end_date.strftime("%m/%d %H시")
    
    # 시즌 기간과 총 기간을 하나의 필드로 통합
    total_duration = season_info.end_date - season_info.start_date
    total_days = total_duration.days
    
    # 현재 진행 일수 계산
    now = datetime.now(KST)
    if now < season_info.start_date:
        elapsed_days = 0
        progress_display = f"0/{total_days}일"
    elif now > season_info.end_date:
        elapsed_days = total_days
        progress_display = f"{total_days}/{total_days}일"
    else:
        elapsed_days = (now - season_info.start_date).days
        progress_display = f"{elapsed_days}/{total_days}일"
    
    embed.add_field(
        name=f"{EMOJIS['calendar']} 시즌 기간",
        value=f"**{start_date_str}** ~ **{end_date_str}**\n{progress_display}",
        inline=True
    )

    # 남은 시간 정보
    embed.add_field(
        name=f"{EMOJIS['time']} 남은 시간",
        value=remaining_time,
        inline=True
    )
    
    # 빈 필드 (레이아웃 균형을 위해)
    embed.add_field(
        name="\u200b",  # 투명 문자
        value="\u200b",
        inline=True
    )
    
    # 진행도 정보 (한 칸 아래로 이동)
    progress_info = f"```{progress_bar} {progress:.1f}%```"
    embed.add_field(
        name=f"{EMOJIS['trend']} 시즌 진행도",
        value=progress_info,
        inline=False
    )


    # 푸터 추가
    footer_text = f'몽실봇 • {len(client.guilds)}개의 서버에서 활동 중'
    embed.set_footer(text=footer_text, icon_url=config.footer_icon)

    return embed

class SeasonView(discord.ui.View):
    """시즌 정보에 대한 상호작용 버튼을 제공하는 뷰"""

    def __init__(self, client: ERClient):
        super().__init__(timeout=config.view_timeout_static)
        self.client = client
        
        # 공식 사이트 버튼
        official_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="공식 사이트",
            url="https://playeternalreturn.com/",
            emoji=EMOJIS['web']
        )
        self.add_item(official_button)

        # 패치 노트 버튼
        patch_button = discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="패치 노트",
            url="https://game.naver.com/lounge/Black_Survival_Eternal_Return/board/17",
            emoji=EMOJIS['patch_note']
        )
        self.add_item(patch_button)

class Season(commands.Cog):
    """시즌 관련 명령어를 처리하는 Cog"""
    
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="시즌", description="현재 시즌 정보 조회")
    @handle_errors(user_message="시즌 정보를 가져오는 중 오류가 발생했습니다.")
    async def season_command(self, interaction: discord.Interaction):
        """
        현재 시즌 정보를 보여줍니다.
        
        시즌 이름, 시작일, 종료일, 진행도를 포함한 정보를 표시합니다.
        상호작용 버튼을 통해 공식 사이트와 패치 노트에 접근할 수 있습니다.
        """
        try:
            await interaction.response.defer()
            
            season_info = await get_season_info()
            embed = create_season_embed(season_info, self.client)
            view = SeasonView(self.client)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"시즌 명령어 실행 중 오류: {e}", exc_info=True)
            # handle_errors 데코레이터가 이미 에러를 처리하므로 여기서는 추가 처리 불필요

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Season(client)) 