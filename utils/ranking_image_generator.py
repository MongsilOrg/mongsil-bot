"""
랭킹 이미지 생성 유틸리티
"""
import os
import io
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from utils.logging_config import get_logger

logger = get_logger('랭킹이미지')

# 다크모드 색상 팔레트
COLORS = {
    'background': '#1a1a1a',      # 다크 배경
    'card': '#2d2d2d',           # 카드 배경
    'text_primary': '#ffffff',   # 주요 텍스트
    'text_secondary': '#b0b0b0', # 보조 텍스트
    'text_muted': '#808080',     # 흐린 텍스트
    'accent': '#5865f2',         # 강조 색상 (Discord 블루)
    'success': '#57f287',        # 성공 색상
    'warning': '#faa61a',        # 경고 색상
    'border': '#404040',         # 테두리
    'rank_gold': '#ffd700',      # 1위 골드
    'rank_silver': '#c0c0c0',    # 2위 실버
    'rank_bronze': '#cd7f32',    # 3위 브론즈
}

# 폰트 크기 설정
FONT_SIZES = {
    'title': 32,
    'subtitle': 20,
    'header': 18,
    'body': 16,
    'small': 14,
    'tiny': 12
}

def create_circular_image(image_path: str, size: int = 40) -> Optional[Image.Image]:
    """캐릭터 이미지를 원형으로 만듭니다. 원본 비율을 유지하고 중앙에서 원형으로 자릅니다."""
    try:
        if not os.path.exists(image_path):
            return None
        
        # 이미지 로드
        char_img = Image.open(image_path).convert('RGBA')
        
        # 원본 이미지 크기
        original_width, original_height = char_img.size
        
        # 중앙에서 정사각형으로 자르기 (원본 비율 유지)
        if original_width > original_height:
            # 가로가 더 긴 경우: 세로 기준으로 중앙에서 자르기
            crop_size = original_height
            left = (original_width - crop_size) // 2
            top = 0
            right = left + crop_size
            bottom = crop_size
        else:
            # 세로가 더 긴 경우: 가로 기준으로 중앙에서 자르기
            crop_size = original_width
            left = 0
            top = (original_height - crop_size) // 2
            right = crop_size
            bottom = top + crop_size
        
        # 중앙에서 정사각형으로 자르기
        char_img = char_img.crop((left, top, right, bottom))
        
        # 원하는 크기로 리사이즈
        char_img = char_img.resize((size, size), Image.Resampling.LANCZOS)
        
        # 투명 배경을 흰색으로 변경 (원형 내부만)
        # 흰색 배경 이미지 생성
        white_bg = Image.new('RGB', (size, size), (255, 255, 255))
        
        # RGBA 이미지를 RGB로 변환하면서 흰색 배경에 합성
        if char_img.mode == 'RGBA':
            # 알파 채널이 있는 경우 흰색 배경에 합성
            white_bg.paste(char_img, (0, 0), char_img)
            char_img = white_bg.convert('RGBA')
        else:
            # 알파 채널이 없는 경우 그대로 사용
            char_img = char_img.convert('RGBA')
        
        # 완벽한 원형 마스크 생성 (안티앨리어싱 적용)
        mask = Image.new('L', (size, size), 0)
        draw_mask = ImageDraw.Draw(mask)
        # 원형을 그릴 때 1픽셀 안쪽으로 그려서 테두리 깔끔하게 처리
        draw_mask.ellipse((1, 1, size-1, size-1), fill=255)
        
        # 원형 이미지 생성 (투명 배경, 원형 내부만 흰색)
        circular_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))  # 투명 배경
        
        # 원형 영역에만 흰색 배경 적용
        white_circle = Image.new('RGBA', (size, size), (255, 255, 255, 255))
        circular_img.paste(white_circle, (0, 0), mask)  # 원형 영역에 흰색 배경
        
        # 캐릭터 이미지를 원형 마스크로 잘라서 붙이기
        char_cropped = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        char_cropped.paste(char_img, (0, 0), mask)
        circular_img.paste(char_cropped, (0, 0), char_cropped)  # 캐릭터 이미지 오버레이
        
        return circular_img
        
    except Exception as e:
        logger.error(f"캐릭터 이미지 처리 실패 {image_path}: {e}")
        return None

def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """폰트를 가져옵니다."""
    try:
        # 무조건 프로젝트 내 나눔고딕 폰트만 사용
        project_font_path = "data/NanumGothic.ttf"
        
        if not os.path.exists(project_font_path):
            logger.error(f"필수 폰트 파일이 없습니다: {project_font_path}")
            raise FileNotFoundError(f"폰트 파일을 찾을 수 없습니다: {project_font_path}")
        
        return ImageFont.truetype(project_font_path, size)
        
    except Exception as e:
        logger.error(f"폰트 로드 실패: {e}")
        raise

def draw_rounded_rectangle(draw: ImageDraw.Draw, xy: Tuple[int, int, int, int], 
                          radius: int, fill: str = None, outline: str = None, width: int = 1):
    """둥근 모서리 사각형을 그립니다."""
    x1, y1, x2, y2 = xy
    
    # 모서리 호 그리기
    draw.ellipse([x1, y1, x1 + radius*2, y1 + radius*2], fill=fill, outline=outline, width=width)
    draw.ellipse([x2 - radius*2, y1, x2, y1 + radius*2], fill=fill, outline=outline, width=width)
    draw.ellipse([x1, y2 - radius*2, x1 + radius*2, y2], fill=fill, outline=outline, width=width)
    draw.ellipse([x2 - radius*2, y2 - radius*2, x2, y2], fill=fill, outline=outline, width=width)
    
    # 직사각형 부분 그리기
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline, width=width)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline, width=width)

def format_number(num: int) -> str:
    """숫자를 K, M 단위로 포맷팅합니다."""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    else:
        return str(num)

def get_rank_color(rank: int) -> str:
    """순위에 따른 색상을 반환합니다."""
    if rank == 1:
        return COLORS['rank_gold']
    elif rank == 2:
        return COLORS['rank_silver']
    elif rank == 3:
        return COLORS['rank_bronze']
    elif rank <= 10:
        return COLORS['accent']
    else:
        return COLORS['text_primary']

def create_ranking_image(users: List, current_page: int, total_pages: int, 
                        season_name: str = "현재 시즌", 
                        image_width: int = 785, image_height: int = 640) -> io.BytesIO:
    """랭킹 이미지를 생성합니다."""
    try:
        # 이미지 크기 설정
        width = image_width
        height = image_height
        margin = 15  # 여백 최적화
        card_height = 52  # 카드 높이 최적화
        card_spacing = 5  # 카드 간격 최적화
        
        # 이미지 생성
        img = Image.new('RGB', (width, height), COLORS['background'])
        draw = ImageDraw.Draw(img)
        
        # 폰트 로드
        title_font = get_font(FONT_SIZES['title'], bold=True)
        subtitle_font = get_font(FONT_SIZES['subtitle'])
        header_font = get_font(FONT_SIZES['header'], bold=True)
        body_font = get_font(FONT_SIZES['body'])
        small_font = get_font(FONT_SIZES['small'])
        
        # 헤더 그리기 (제목과 부제목 제거하여 테이블에 집중)
        header_y = margin + 5
        header_items = ["순위", "닉네임", "MMR", "게임", "승률", "평순", "캐릭터"]
        
        # 헤더와 데이터의 정확한 X 위치 계산 (캐릭터 이미지 공간 포함)
        # 전체 너비 785px에서 좌우 여백 15px씩 제외한 755px를 7개 컬럼으로 최적화 분배
        x_positions = [margin + 5, margin + 70, margin + 270, margin + 370, margin + 460, margin + 550, margin + 640]
        column_widths = [55, 190, 90, 80, 80, 80, 130]  # 캐릭터 영역을 130px로 확장 (3개 캐릭터 완전 표시용)
        
        for i, (item, x_pos) in enumerate(zip(header_items, x_positions)):
            # 모든 헤더 항목을 중앙 정렬
            item_bbox = draw.textbbox((0, 0), item, font=header_font)
            item_width = item_bbox[2] - item_bbox[0]
            item_x = x_pos + (column_widths[i] - item_width) // 2
            draw.text((item_x, header_y), item, fill=COLORS['text_muted'], font=header_font)
        
        # 랭킹 데이터 그리기 (구분선 없이)
        data_y = header_y + 35
        for i, user in enumerate(users):
            # 정확히 10명까지만 표시
            if i >= 10:
                break
                
            # 카드 배경 그리기 (테두리 없이)
            card_rect = (margin, data_y, width - margin, data_y + card_height)
            draw_rounded_rectangle(draw, card_rect, 8, 
                                 fill=COLORS['card'])
            
            # 텍스트 수직 중앙 정렬을 위한 Y 위치 계산
            text_y = data_y + (card_height - FONT_SIZES['body']) // 2
            
            # 순위 (중앙 정렬)
            rank_text = f"#{user.rank}"
            rank_color = get_rank_color(user.rank)
            rank_bbox = draw.textbbox((0, 0), rank_text, font=body_font)
            rank_width = rank_bbox[2] - rank_bbox[0]
            rank_x = x_positions[0] + (column_widths[0] - rank_width) // 2
            draw.text((rank_x, text_y), rank_text, 
                     fill=rank_color, font=body_font)
            
            # 닉네임 (왼쪽 정렬, 폰트 사이즈 조정)
            nickname_text = user.nickname
            nickname_font = body_font
            
            # 닉네임이 칸을 넘어가는지 확인
            nickname_bbox = draw.textbbox((0, 0), nickname_text, font=nickname_font)
            nickname_width = nickname_bbox[2] - nickname_bbox[0]
            nickname_max_width = column_widths[1] - 5  # 중앙정렬을 위한 여백 고려
            
            # 칸을 넘어가면 폰트 사이즈를 줄임
            if nickname_width > nickname_max_width:
                # 폰트 사이즈를 점진적으로 줄여가며 테스트
                for font_size in range(FONT_SIZES['body'] - 1, FONT_SIZES['small'] - 1, -1):
                    test_font = get_font(font_size)
                    test_bbox = draw.textbbox((0, 0), nickname_text, font=test_font)
                    test_width = test_bbox[2] - test_bbox[0]
                    if test_width <= nickname_max_width:
                        nickname_font = test_font
                        break
                
                # 그래도 안 맞으면 작은 폰트로 강제 설정
                if nickname_font == body_font:
                    nickname_font = get_font(FONT_SIZES['small'])
            
            # 닉네임 중앙 정렬
            nickname_bbox = draw.textbbox((0, 0), nickname_text, font=nickname_font)
            nickname_width = nickname_bbox[2] - nickname_bbox[0]
            nickname_x = x_positions[1] + (column_widths[1] - nickname_width) // 2
            draw.text((nickname_x, text_y), nickname_text, 
                     fill=COLORS['text_primary'], font=nickname_font)
            
            # MMR (중앙 정렬)
            mmr_text = f"{user.mmr:,}"
            mmr_bbox = draw.textbbox((0, 0), mmr_text, font=body_font)
            mmr_width = mmr_bbox[2] - mmr_bbox[0]
            mmr_x = x_positions[2] + (column_widths[2] - mmr_width) // 2
            draw.text((mmr_x, text_y), mmr_text, 
                     fill=COLORS['text_primary'], font=body_font)
            
            # 게임 수 (중앙 정렬)
            games_text = f"{user.games}판"
            games_bbox = draw.textbbox((0, 0), games_text, font=body_font)
            games_width = games_bbox[2] - games_bbox[0]
            games_x = x_positions[3] + (column_widths[3] - games_width) // 2
            draw.text((games_x, text_y), games_text, 
                     fill=COLORS['text_secondary'], font=body_font)
            
            # 승률 (중앙 정렬)
            win_rate = (user.wins / user.games * 100) if user.games > 0 else 0
            win_rate_text = f"{win_rate:.1f}%"
            win_rate_color = COLORS['success'] if win_rate >= 50 else COLORS['warning'] if win_rate >= 30 else COLORS['text_muted']
            win_rate_bbox = draw.textbbox((0, 0), win_rate_text, font=body_font)
            win_rate_width = win_rate_bbox[2] - win_rate_bbox[0]
            win_rate_x = x_positions[4] + (column_widths[4] - win_rate_width) // 2
            draw.text((win_rate_x, text_y), win_rate_text, 
                     fill=win_rate_color, font=body_font)
            
            # 평균 순위 (중앙 정렬)
            avg_rank_text = f"{user.avg_rank:.1f}위"
            avg_rank_bbox = draw.textbbox((0, 0), avg_rank_text, font=body_font)
            avg_rank_width = avg_rank_bbox[2] - avg_rank_bbox[0]
            avg_rank_x = x_positions[5] + (column_widths[5] - avg_rank_width) // 2
            draw.text((avg_rank_x, text_y), avg_rank_text, 
                     fill=COLORS['text_secondary'], font=body_font)
            
            # 캐릭터 이미지 (모스트 3)
            if hasattr(user, 'character_stats') and user.character_stats:
                
                # 게임 수 기준으로 정렬하여 상위 3개 선택
                top_characters = sorted(user.character_stats, key=lambda x: x.get('totalGames', 0), reverse=True)[:3]
                
                char_image_size = 32  # 110px 영역에 3개가 들어가도록 크기 조정
                char_spacing = 3  # 간격을 3px로 최적화
                char_start_x = x_positions[6] + 5  # 왼쪽에서 5px 여백으로 시작
                
                for j, char_data in enumerate(top_characters):
                    char_code = char_data.get('characterCode', 0)
                    
                    # 캐릭터 이미지 경로 (파일명 형식: 숫자.png)
                    char_image_path = f"data/characters/{char_code}.png"
                    
                    # 파일이 존재하는지 확인
                    if not os.path.exists(char_image_path):
                        continue
                    
                    # 원형 이미지 생성
                    circular_img = create_circular_image(char_image_path, char_image_size)
                    if circular_img:
                        char_x = char_start_x + j * (char_image_size + char_spacing)
                        char_y = text_y - (char_image_size - FONT_SIZES['body']) // 2
                        
                        # 이미지를 메인 이미지에 붙이기
                        img.paste(circular_img, (char_x, char_y), circular_img)
            else:
                pass  # character_stats가 없는 경우
            
            data_y += card_height + card_spacing
        
        # 이미지를 BytesIO로 변환
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        logger.info(f"랭킹 이미지 생성 완료: {len(users)}명, {width}x{height}")
        return img_bytes
        
    except Exception as e:
        logger.error(f"랭킹 이미지 생성 중 오류 발생: {e}", exc_info=True)
        # Fallback: 빈 이미지 반환
        try:
            fallback_img = Image.new('RGB', (image_width, image_height), COLORS['background'])
            draw = ImageDraw.Draw(fallback_img)
            title_font = get_font(FONT_SIZES['title'], bold=True)
            
            # 에러 메시지 표시
            error_text = "이미지 생성 중 오류가 발생했습니다."
            text_bbox = draw.textbbox((0, 0), error_text, font=title_font)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(((image_width - text_width) // 2, image_height // 2), error_text, 
                     fill=COLORS['text_primary'], font=title_font)
            
            img_bytes = io.BytesIO()
            fallback_img.save(img_bytes, format='PNG', optimize=True)
            img_bytes.seek(0)
            return img_bytes
        except Exception as fallback_error:
            logger.error(f"Fallback 이미지 생성도 실패: {fallback_error}")
            raise

