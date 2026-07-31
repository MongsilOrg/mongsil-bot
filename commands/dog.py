import discord
from discord import app_commands
from discord.ext import commands
from client import ERClient
from typing import Optional

from utils.errors import handle_errors
from utils.logging_config import get_logger
from utils.animal_utils import AnimalImage, fetch_animal_image, download_image, create_animal_error_layout

logger = get_logger('강아지')

async def get_dog_info() -> Optional[AnimalImage]:
    """강아지 정보를 가져옵니다."""
    try:
        image_data = await fetch_animal_image('https://api.thedogapi.com/v1/images/search', '강아지')
        if not image_data:
            return None

        breeds = None
        if 'breeds' in image_data and image_data['breeds']:
            breeds = [breed['name'] for breed in image_data['breeds']]

        return AnimalImage(
            url=image_data['url'],
            breeds=breeds,
            source='The Dog API'
        )
    except Exception as e:
        logger.error(f"강아지 정보 처리 중 오류 발생: {e}", exc_info=True)
        return None

class Dog(commands.Cog):
    def __init__(self, client: ERClient):
        self.client = client

    @app_commands.command(name="강아지", description="무작위 강아지 사진")
    @handle_errors(user_message="강아지 사진을 가져오는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.")
    async def dog_command(self, interaction: discord.Interaction):
        """무작위 강아지 사진을 보여줍니다."""
        await interaction.response.defer()

        dog_info = await get_dog_info()
        if not dog_info:
            layout = create_animal_error_layout("not_found", "강아지", self.client)
            await interaction.followup.send(view=layout, ephemeral=True)
            return

        image_data = await download_image(dog_info.url)
        if not image_data:
            layout = create_animal_error_layout("download_failed", "강아지", self.client)
            await interaction.followup.send(view=layout, ephemeral=True)
            return

        filename = "dog.jpg"
        if dog_info.breeds:
            breed_name = '_'.join(dog_info.breeds)
            filename = f"dog_{breed_name}.jpg"

        file = discord.File(image_data, filename=filename)
        await interaction.followup.send(file=file)

async def setup(client: ERClient):
    """명령어를 등록합니다."""
    await client.add_cog(Dog(client))
