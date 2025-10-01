"""
동물 이미지 관련 공통 유틸리티
"""
import discord
from typing import Optional, Dict, Any, NamedTuple
from io import BytesIO
from .api_client import api_client
from .embeds import create_info_embed, create_error_embed
from .logging_config import get_logger

logger = get_logger('동물유틸')

class AnimalImage(NamedTuple):
    """동물 이미지 정보를 저장하는 네임드 튜플"""
    url: str
    breeds: Optional[list[str]] = None
    source: str = 'Unknown'

async def fetch_animal_image(api_url: str, source_name: str) -> Optional[Dict[str, Any]]:
    """동물 이미지를 API에서 가져옵니다."""
    try:
        data = await api_client.get(api_url, use_cache=False)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"{source_name} 이미지 가져오기 실패: {e}")
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

def create_animal_embed(animal_info: AnimalImage, emoji: str, animal_name: str, client) -> discord.Embed:
    """동물 임베드를 생성합니다."""
    embed = create_info_embed(
        title=f"{emoji} 랜덤 {animal_name}",
        description=f"귀여운 {animal_name} 사진입니다!",
        client=client
    )
    
    # 품종 정보 추가
    if animal_info.breeds:
        breed_text = ", ".join(animal_info.breeds)
        embed.add_field(
            name="🐾 품종",
            value=breed_text,
            inline=True
        )
    
    # 출처 정보 추가
    embed.add_field(
        name="📸 출처",
        value=animal_info.source,
        inline=True
    )
    
    return embed

def create_animal_error_embed(error_type: str, animal_name: str, client) -> discord.Embed:
    """동물 관련 에러 임베드를 생성합니다."""
    if error_type == "not_found":
        return create_error_embed(
            f"{animal_name} 사진을 찾을 수 없습니다",
            f"현재 {animal_name} 사진을 가져올 수 없습니다.\n잠시 후 다시 시도해주세요.",
            client
        )
    elif error_type == "download_failed":
        return create_error_embed(
            "이미지 다운로드 실패",
            f"{animal_name} 이미지를 다운로드할 수 없습니다.\n네트워크 연결을 확인해주세요.",
            client
        )
    else:
        return create_error_embed(
            "오류 발생",
            f"{animal_name} 사진을 가져오는 중 오류가 발생했습니다.",
            client
        )
