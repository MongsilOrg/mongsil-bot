import discord
from discord import app_commands
from discord.ext import commands
from client import ERClient
from typing import Optional, Dict, Any

from utils.config import config
from utils.embeds import create_error_embed
from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.animal_utils import AnimalImage, fetch_animal_image, download_image, create_animal_embed, create_animal_error_embed

logger = get_logger('고양이')

async def get_cat_info() -> Optional[AnimalImage]:
    """고양이 정보를 가져옵니다."""
    try:
        image_data = await fetch_animal_image('https://api.thecatapi.com/v1/images/search', '고양이')
        if not image_data:
            return None

        breeds = None
        if 'breeds' in image_data and image_data['breeds']:
            breeds = [breed['name'] for breed in image_data['breeds']]

        return AnimalImage(
            url=image_data['url'],
            breeds=breeds,
            source='The Cat API'
        )
    except Exception as e:
        logger.error(f"고양이 정보 처리 중 오류 발생: {e}", exc_info=True)
        return None

class Cat(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="고양이", description="무작위 고양이 사진을 보여줍니다")
    @handle_errors(user_message="고양이 사진을 가져오는 중 오류가 발생했습니다.")
    async def cat_command(self, interaction: discord.Interaction):
        """무작위 고양이 사진을 보여줍니다."""
        try:
            await interaction.response.defer()
            
            cat_info = await get_cat_info()
            if not cat_info:
                embed = create_animal_error_embed("not_found", "고양이", self.client)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            image_data = await download_image(cat_info.url)
            if not image_data:
                embed = create_animal_error_embed("download_failed", "고양이", self.client)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            filename = "cat.jpg"
            if cat_info.breeds:
                breed_name = '_'.join(cat_info.breeds)
                filename = f"cat_{breed_name}.jpg"

            file = discord.File(image_data, filename=filename)
            await interaction.followup.send(file=file)
            
        except Exception as e:
            logger.error(f"고양이 명령어 실행 중 오류 발생: {e}", exc_info=True)
            if not interaction.response.is_done():
                embed = create_animal_error_embed("error", "고양이", self.client)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = create_animal_error_embed("error", "고양이", self.client)
                await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Cat(client))
