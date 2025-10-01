"""
로깅 설정 모듈
"""
import logging
import sys
import os
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """로깅을 설정합니다."""
    
    # 개발 환경인지 확인 (환경변수로 제어)
    is_dev = os.getenv('DEV_MODE', 'false').lower() == 'true'
    
    if format_string is None:
        # 프로덕션에서는 간결한 형식 사용
        if is_dev:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            format_string = "%(asctime)s - %(levelname)s - %(message)s"
    
    # 로그 레벨 설정
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    
    # 기본 포매터 설정
    formatter = logging.Formatter(format_string)
    
    # 콘솔 핸들러 설정 - 프로덕션에서는 WARNING 이상만
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_level = logging.DEBUG if is_dev else logging.WARNING
    console_handler.setLevel(console_level)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 설정 (선택적) - 모든 로그를 파일에 저장 (회전 기능 포함)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 로그 파일 회전: 최대 10MB, 5개 백업 파일 유지
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 로그 저장

        root_logger.addHandler(file_handler)
    
    # 외부 라이브러리 로거 레벨 조정
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    
    # aiohttp 로거 레벨 조정
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.client').setLevel(logging.WARNING)
    
    # urllib3 로거 레벨 조정 (aiohttp 내부에서 사용)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # 프로덕션에서는 특정 모듈들의 로그 레벨 조정
    if not is_dev:
        # 명령어 관련 로거들 - 콘솔에서는 WARNING 이상만
        command_loggers = [
            '정보', '랭크', '랭킹', '설정', '동접', '플탐', '시즌'
        ]
        for logger_name in command_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
        
        # API 클라이언트 로거
        logging.getLogger('utils.api_client').setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """이름을 가진 로거를 반환합니다."""
    return logging.getLogger(name)
