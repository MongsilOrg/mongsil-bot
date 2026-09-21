"""
동물 이미지 관련 공통 유틸리티
"""
from typing import Optional, Dict, Any
from io import BytesIO
import discord
from .api_client import api_client
from .layouts import create_error_layout
from .logging_config import get_logger

logger = get_logger('동물유틸')

async def fetch_animal_image(api_url: str, source_name: str) -> Optional[Dict[str, Any]]:
    """동물 이미지를 API에서 가져옵니다."""
    try:
        data = await api_client.get(api_url, use_cache=False)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        # 원인은 api_client가 이미 남긴다. 외부 동물 API의 일시 실패까지
        # ERROR로 올리면 Sentry 이슈만 쌓인다.
        logger.warning(f"{source_name} 이미지 가져오기 실패: {e}")
        return None

async def download_image(url: str) -> Optional[BytesIO]:
    """이미지 URL에서 이미지를 다운로드합니다."""
    try:
        session = await api_client.get_session()
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return BytesIO(data)
            else:
                logger.error(f"이미지 다운로드 실패: 상태 코드 {response.status}")
                return None
    except Exception as e:
        logger.error(f"이미지 다운로드 중 오류 발생: {e}", exc_info=True)
        return None

async def send_animal_photo(
    interaction: discord.Interaction,
    api_url: str,
    animal_name: str,
    filename_prefix: str,
) -> None:
    """동물 사진 명령 공통 흐름: 조회, 다운로드, 전송."""
    await interaction.response.defer()

    image_data = await fetch_animal_image(api_url, animal_name)
    file_bytes = await download_image(image_data['url']) if image_data else None
    if not file_bytes:
        await interaction.followup.send(view=create_error_layout(f"{animal_name} 사진을 가져오지 못했습니다. 잠시 후 다시 시도해주세요."))
        return

    breeds = [b['name'] for b in image_data.get('breeds') or [] if 'name' in b]
    filename = f"{filename_prefix}_{'_'.join(breeds)}.jpg" if breeds else f"{filename_prefix}.jpg"

    await interaction.followup.send(file=discord.File(file_bytes, filename=filename))
