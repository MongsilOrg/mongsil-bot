"""
에러 처리 유틸리티
"""
import discord
from typing import Optional, Callable
from functools import wraps
from .layouts import create_error_layout
from .logging_config import get_logger

logger = get_logger('errors')

class BotError(Exception):
    """봇 관련 기본 예외 클래스"""
    def __init__(self, message: str, user_message: Optional[str] = None):
        self.message = message
        self.user_message = user_message or "오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        super().__init__(self.message)

class APIError(BotError):
    """API 관련 예외"""
    pass

class ValidationError(BotError):
    """입력 검증 예외"""
    pass

class NotFoundError(BotError):
    """데이터를 찾을 수 없는 예외"""
    pass


async def _send_error(interaction: discord.Interaction, error_text: str):
    """에러 LayoutView를 전송합니다. 로딩 메시지가 있으면 교체합니다."""
    layout = create_error_layout("오류", error_text)
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(view=layout, ephemeral=True)
        else:
            # 로딩 메시지를 에러로 교체 시도, 실패 시 followup
            try:
                await interaction.edit_original_response(view=layout, embeds=[], attachments=[])
            except Exception:
                await interaction.followup.send(view=layout, ephemeral=True)
    except Exception:
        pass


def handle_errors(
    user_message: str = "명령어 실행 중 오류가 발생했습니다.",
    log_error: bool = True
):
    """에러 처리를 위한 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except BotError as e:
                if log_error:
                    # 오타 조회, 기록 없음 같은 예상된 유저 조건은 WARNING으로 남긴다.
                    # Sentry는 ERROR 이상만 수집하므로 노이즈가 되지 않는다.
                    if isinstance(e, (NotFoundError, ValidationError)):
                        logger.warning(f"BotError in {func.__name__}: {e.message}")
                    else:
                        logger.error(f"BotError in {func.__name__}: {e.message}")

                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if interaction:
                    await _send_error(interaction, e.user_message)

                return None
            except Exception as e:
                if log_error:
                    logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)

                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if interaction:
                    await _send_error(interaction, user_message)

                return None
        return wrapper
    return decorator

def validate_nickname(nickname: str) -> str:
    """닉네임 입력을 검증합니다."""
    if not nickname or not nickname.strip():
        raise ValidationError("닉네임이 비어있습니다.", "닉네임을 입력해주세요.")

    nickname = nickname.strip()

    if len(nickname) < 2:
        raise ValidationError("닉네임이 너무 짧습니다.", "닉네임은 2자 이상이어야 합니다.")

    if len(nickname) > 20:
        raise ValidationError("닉네임이 너무 깁니다.", "닉네임은 20자 이하여야 합니다.")

    # 특수 문자 검증 (기본적인 것만)
    forbidden_chars = ['<', '>', '@', '#', '&', '!', '`', '*', '_', '~', '|', '\\']
    for char in forbidden_chars:
        if char in nickname:
            raise ValidationError(f"닉네임에 사용할 수 없는 문자가 포함되어 있습니다: {char}",
                                f"닉네임에 특수문자 '{char}'를 사용할 수 없습니다.\n영문, 한글, 숫자만 사용해주세요.")

    return nickname
