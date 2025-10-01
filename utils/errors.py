"""
에러 처리 유틸리티
"""
import discord
from typing import Optional, Callable, Any
from functools import wraps
from .embeds import create_error_embed
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
                    logger.error(f"BotError in {func.__name__}: {e.message}")

                # Discord Interaction이 있는 경우 에러 메시지 전송
                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if interaction:
                    embed = create_error_embed("오류", e.user_message)
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.send_message(embed=embed, ephemeral=True)
                        else:
                            await interaction.followup.send(embed=embed, ephemeral=True)
                    except Exception:
                        pass  # 에러 메시지 전송 실패는 무시
                
                return None
            except Exception as e:
                if log_error:
                    logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)

                # Discord Interaction이 있는 경우 일반 에러 메시지 전송
                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if interaction:
                    embed = create_error_embed("오류", user_message)
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.send_message(embed=embed, ephemeral=True)
                        else:
                            await interaction.followup.send(embed=embed, ephemeral=True)
                    except Exception:
                        pass  # 에러 메시지 전송 실패는 무시
                
                return None
        return wrapper
    return decorator

def validate_nickname(nickname: str) -> str:
    """닉네임 입력을 검증합니다."""
    if not nickname or not nickname.strip():
        raise ValidationError("닉네임이 비어있습니다.", "❌ 닉네임을 입력해주세요.")
    
    nickname = nickname.strip()
    
    if len(nickname) < 2:
        raise ValidationError("닉네임이 너무 짧습니다.", "❌ 닉네임은 2자 이상이어야 합니다.")
    
    if len(nickname) > 20:
        raise ValidationError("닉네임이 너무 깁니다.", "❌ 닉네임은 20자 이하여야 합니다.")
    
    # 특수 문자 검증 (기본적인 것만)
    forbidden_chars = ['<', '>', '@', '#', '&', '!', '`', '*', '_', '~', '|', '\\']
    for char in forbidden_chars:
        if char in nickname:
            raise ValidationError(f"닉네임에 사용할 수 없는 문자가 포함되어 있습니다: {char}", 
                                f"❌ 닉네임에 특수문자 '{char}'를 사용할 수 없습니다.\n💡 영문, 한글, 숫자만 사용해주세요.")
    
    return nickname
