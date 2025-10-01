"""
이모지 상수 정의

전체 봇에서 사용하는 이모지를 중앙에서 관리합니다.
"""

# 공통 이모지
EMOJIS = {
    # 상태 표시
    'on': '✅',
    'off': '❌',
    'loading': '⏳',
    'error': '⚠️',
    'success': '✅',

    # 사용자/권한
    'admin': '👑',
    'user': '👥',
    'users': '👥',
    'bot': '🤖',
    'dev': '👨‍💻',

    # 정보 표시
    'info': 'ℹ️',
    'settings': '⚙️',
    'system': '⚙️',
    'save': '💾',
    'refresh': '🔄',

    # 통계/차트
    'chart': '📊',
    'status': '📊',
    'total': '📊',
    'trend': '📈',
    'average': '📈',
    'down': '📉',
    'trophy': '🏆',

    # 등급/티어
    'crown': '👑',
    'sparkles': '✨',

    # 시간 관련
    'calendar': '📅',
    'time': '⏰',
    'clock': '🕐',
    'uptime': '⏱️',

    # 게임 관련
    'game': '🎮',
    'games': '🎮',
    'discord': '🎮',
    'fire': '🔥',
    'most': '🔝',

    # 서버/시스템
    'server': '🏠',
    'channel': '💬',
    'command': '⚡',
    'ram': '🧠',
    'ping': '📶',

    # 기능별
    'emoji_zoom': '🔍',
    'search': '🔍',

    # 기술/라이브러리
    'python': '🐍',
    'lib': '📦',

    # 링크/외부
    'link': '🔗',
    'support': '💬',
    'invite': '🚀',
    'web': '🌐',
    'email': '📧',
    'patch_note': '📝',
}

# 시즌 관련 이모지 (동적)
SEASON_EMOJIS = {
    'ea': '🔧',
    'pre_season': '⚡',
    'regular': '🏆',
}

# 시즌 진행도 이모지 (동적)
SEASON_PROGRESS_EMOJIS = {
    'before_start': '⏳',
    'early': '🌅',
    'first_half': '☀️',
    'second_half': '🌆',
    'final': '🌙',
    'finished': '🏁',
}

# 핑 상태 이모지 (동적)
PING_EMOJIS = {
    'good': '🟢',      # < 100ms
    'normal': '🟡',    # 100-200ms
    'bad': '🔴',       # > 200ms
}
