import os
import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, NamedTuple
import pytz
from client import ERClient

from utils.config import config
from utils.layouts import create_error_layout, footer_text
from utils.errors import handle_errors, APIError
from utils.logging_config import get_logger
from utils.emojis import SEASON_EMOJIS, SEASON_PROGRESS_EMOJIS, EMOJIS

logger = get_logger('시즌')

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 시즌 관련 상수
SEASON_ZERO_ID = 19  # 시즌 0이 되는 ID 값
SEASON_NAME_OFFSET = 9  # Season16은 시즌7이므로, 9를 빼면 됨

# 시즌 코드명 (API 미제공 → seasonID 기준 수동 매핑, 새 시즌마다 한 줄 추가)
SEASON_CODENAMES: Dict[int, str] = {
    39: "쁘띠 미뇽",  # 정규 시즌 11
}

# 시즌 데이터 캐시 (API 호출 최소화)
_season_cache: Optional[Dict[str, Any]] = None
_season_cache_time: Optional[datetime] = None
SEASON_CACHE_TTL = timedelta(minutes=30)

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
    API에서 시즌 정보를 가져옵니다. 캐시를 사용하여 API 호출을 최소화합니다.

    Args:
        season_id: 특정 시즌 ID를 찾을 경우 사용. None이면 현재 시즌(isCurrent=1)을 반환.

    Returns:
        시즌 정보 딕셔너리 또는 None
    """
    global _season_cache, _season_cache_time

    # 현재 시즌 조회 시 캐시 확인
    if season_id is None and _season_cache is not None and _season_cache_time is not None:
        if datetime.now() - _season_cache_time < SEASON_CACHE_TTL:
            return _season_cache

    try:
        from utils.api_client import api_client

        # API URL을 config에서 가져오되, v2 버전 사용
        base_url = config.api_url.replace('/v1', '/v2')
        url = f'{base_url}/data/Season'

        data = await api_client.get(url, use_cache=True)

        if not data:
            logger.error("시즌 API 응답 없음")
            return None

        # API 응답 형식 유연하게 처리 (data 필드가 리스트인 경우와 아닌 경우)
        season_list = data.get('data', [])
        if not isinstance(season_list, list):
            season_list = [season_list] if season_list else []

        if not season_list:
            logger.error("시즌 데이터가 비어있습니다")
            return None

        # 특정 season_id를 찾는 경우
        if season_id is not None:
            for season in season_list:
                if isinstance(season, dict) and season.get('seasonID') == season_id:
                    return season
            return None

        # 현재 시즌 찾기 (isCurrent = 1)
        current_season = None
        for season in season_list:
            if isinstance(season, dict) and season.get('isCurrent') == 1:
                current_season = season
                break

        # isCurrent가 없는 경우 가장 높은 seasonID 사용
        if not current_season and season_list:
            current_season = max(
                (s for s in season_list if isinstance(s, dict) and 'seasonID' in s),
                key=lambda s: s['seasonID'],
                default=None
            )

        if current_season:
            # 캐시 업데이트
            _season_cache = current_season
            _season_cache_time = datetime.now()

        return current_season

    except Exception as e:
        logger.error(f"시즌 API 호출 중 오류: {e}", exc_info=True)
        return None

async def get_current_season_id() -> Optional[int]:
    """
    현재 시즌 ID를 가져옵니다.
    API에서 우선 조회하고, 실패 시 환경변수를 fallback으로 사용합니다.

    Returns:
        현재 시즌 ID 또는 None
    """
    try:
        # 1. API에서 현재 시즌 조회
        season_data = await fetch_season_data()
        if season_data and 'seasonID' in season_data:
            return season_data['seasonID']

        # 2. 환경변수 fallback
        env_season_id = os.getenv('SEASON_ID')
        if env_season_id is not None:
            logger.warning(f"API에서 시즌 정보를 가져올 수 없어 환경변수 사용: SEASON_ID={env_season_id}")
            return int(env_season_id)

        return None
    except Exception as e:
        logger.error(f"현재 시즌 ID 조회 중 오류: {e}", exc_info=True)
        # 환경변수 fallback
        env_val = os.getenv('SEASON_ID')
        return int(env_val) if env_val else None

def _parse_season_date(date_str: str) -> Optional[datetime]:
    """시즌 날짜 문자열을 파싱합니다. 여러 형식을 지원합니다."""
    formats = [
        '%Y-%m-%dT%H:%M:%S%z',      # ISO 8601 with timezone
        '%Y-%m-%dT%H:%M:%S.%f%z',   # ISO 8601 with microseconds
        '%Y-%m-%dT%H:%M:%S',         # ISO 8601 without timezone
        '%Y-%m-%d %H:%M:%S',         # 환경변수 형식
        '%Y/%m/%d %H:%M:%S',         # 슬래시 형식
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = KST.localize(dt)
            return dt
        except ValueError:
            continue
    return None

async def get_season_info() -> Optional[SeasonInfo]:
    """
    시즌 정보를 가져옵니다.
    API에서 우선 조회하고, 실패 시 환경변수를 fallback으로 사용합니다.

    Returns:
        SeasonInfo 객체 또는 None
    """
    try:
        # 1. API에서 현재 시즌 조회
        season_data = await fetch_season_data()
        if season_data:
            season_id = season_data.get('seasonID')
            season_name_raw = season_data.get('seasonName', '')
            season_start_str = season_data.get('seasonStart', '')
            season_end_str = season_data.get('seasonEnd', '')

            if season_id and season_start_str and season_end_str:
                start_date = _parse_season_date(season_start_str)
                end_date = _parse_season_date(season_end_str)

                if start_date and end_date:
                    # 시즌 이름 변환
                    season_name = get_season_name(season_id, season_name_raw)
                    return SeasonInfo(
                        number=season_id,
                        start_date=start_date,
                        end_date=end_date,
                        name=season_name
                    )

        # 2. 환경변수 fallback
        env_season_id_str = os.getenv('SEASON_ID')
        if not env_season_id_str:
            logger.warning("시즌 정보를 API와 환경변수 모두에서 가져올 수 없습니다")
            return None
        env_season_id = int(env_season_id_str)

        env_start_str = os.getenv('SEASON_START')
        env_end_str = os.getenv('SEASON_END')
        if not (env_start_str and env_end_str):
            logger.warning("환경변수 SEASON_START 또는 SEASON_END가 설정되지 않았습니다")
            return None

        start_date = _parse_season_date(env_start_str)
        end_date = _parse_season_date(env_end_str)
        if not (start_date and end_date):
            logger.error("환경변수 시즌 날짜 파싱 실패")
            return None

        season_name = os.getenv('SEASON_NAME') or f"시즌 {env_season_id}"
        logger.warning(f"API에서 시즌 정보를 가져올 수 없어 환경변수 사용: {season_name}")

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
    # 칠해진 칸과 빈 칸 모두 같은 폭의 블록 문자(█/░)를 사용해
    # 진행도와 실제 막대 길이가 어긋나지 않도록 한다.
    filled_length = max(0, min(length, round(length * progress / 100)))
    return '█' * filled_length + '░' * (length - filled_length)


def create_season_layout(season_info: Optional[SeasonInfo], client: ERClient) -> ui.LayoutView:
    """
    시즌 정보 LayoutView를 생성합니다.

    Args:
        season_info: 시즌 정보
        client: Discord 클라이언트

    Returns:
        LayoutView 객체
    """
    if not season_info:
        return create_error_layout(
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

    # 시즌 코드명이 있으면 이름과 함께 표시 (예: 정규 시즌 11 (쁘띠 미뇽))
    codename = SEASON_CODENAMES.get(season_info.number)
    name_display = f"{season_info.name} ({codename})" if codename else season_info.name

    # 시즌 시작 전이면 '남은 시간' 대신 '시작까지'로 표기
    time_label = "시작까지" if status_text == "시즌 시작 전" else "남은 시간"

    # 시즌 기간 정보 (간결한 형식)
    start_date_str = season_info.start_date.strftime("%m/%d %H시")
    end_date_str = season_info.end_date.strftime("%m/%d %H시")

    # 시즌 기간과 총 기간
    total_duration = season_info.end_date - season_info.start_date
    total_days = total_duration.days

    # 현재 진행 일수 계산
    now = datetime.now(KST)
    if now < season_info.start_date:
        elapsed_days = 0
    elif now > season_info.end_date:
        elapsed_days = total_days
    else:
        elapsed_days = (now - season_info.start_date).days

    # LayoutView 구성
    view = ui.LayoutView(timeout=None)

    container = ui.Container(
        ui.TextDisplay(
            f"### {season_emoji} {name_display}\n"
            f"{status_emoji} **{status_text}**"
        ),
        ui.Separator(),
        ui.TextDisplay(
            f"📅 **{start_date_str}** ~ **{end_date_str}**\n"
            f"-# {elapsed_days}일째 / 총 {total_days}일"
        ),
        ui.TextDisplay(f"⏰ **{time_label}**: {remaining_time}"),
        ui.Separator(),
        ui.TextDisplay(f"{progress_bar}  **{progress:.1f}%**"),
        ui.Separator(visible=False),
        ui.TextDisplay(footer_text(client)),
        accent_colour=discord.Colour.blurple(),
    )
    view.add_item(container)

    # 링크 버튼 ActionRow
    view.add_item(ui.ActionRow(
        ui.Button(
            style=discord.ButtonStyle.link,
            label="공식 사이트",
            url="https://playeternalreturn.com/",
            emoji=EMOJIS['web'],
        ),
        ui.Button(
            style=discord.ButtonStyle.link,
            label="패치 노트",
            url="https://game.naver.com/lounge/Black_Survival_Eternal_Return/board/17",
            emoji=EMOJIS['patch_note'],
        ),
    ))

    return view

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
        await interaction.response.defer()

        season_info = await get_season_info()
        layout = create_season_layout(season_info, self.client)

        await interaction.followup.send(view=layout)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Season(client))
