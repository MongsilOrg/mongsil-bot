"""
티어 시스템 유틸리티 모듈
"""


class TierSystem:
    """티어 시스템을 관리하는 클래스"""

    # 티어 정보를 담는 클래스 변수
    TIERS = {
        "이터니티": {"base": 8300, "icon": "10"},
        "데미갓": {"base": 8300, "icon": "9"},
        "미스릴": {"base": 7600, "icon": "8"},
        "메테오라이트 1": {"base": 7300, "icon": "7"},
        "메테오라이트 2": {"base": 7000, "icon": "7"},
        "메테오라이트 3": {"base": 6700, "icon": "7"},
        "메테오라이트 4": {"base": 6400, "icon": "7"},
        "다이아몬드 1": {"base": 6050, "icon": "6"},
        "다이아몬드 2": {"base": 5700, "icon": "6"},
        "다이아몬드 3": {"base": 5350, "icon": "6"},
        "다이아몬드 4": {"base": 5000, "icon": "6"},
        "플래티넘 1": {"base": 4650, "icon": "5"},
        "플래티넘 2": {"base": 4300, "icon": "5"},
        "플래티넘 3": {"base": 3950, "icon": "5"},
        "플래티넘 4": {"base": 3600, "icon": "5"},
        "골드 1": {"base": 3300, "icon": "4"},
        "골드 2": {"base": 3000, "icon": "4"},
        "골드 3": {"base": 2700, "icon": "4"},
        "골드 4": {"base": 2400, "icon": "4"},
        "실버 1": {"base": 2150, "icon": "3"},
        "실버 2": {"base": 1900, "icon": "3"},
        "실버 3": {"base": 1650, "icon": "3"},
        "실버 4": {"base": 1400, "icon": "3"},
        "브론즈 1": {"base": 1200, "icon": "2"},
        "브론즈 2": {"base": 1000, "icon": "2"},
        "브론즈 3": {"base": 800, "icon": "2"},
        "브론즈 4": {"base": 600, "icon": "2"},
        "아이언 1": {"base": 450, "icon": "1"},
        "아이언 2": {"base": 300, "icon": "1"},
        "아이언 3": {"base": 150, "icon": "1"},
        "아이언 4": {"base": 0, "icon": "1"},
        "언랭크": {"base": 0, "icon": "0"}
    }

    @classmethod
    def get_tier(cls, mmr: int, rank: int) -> str:
        """
        MMR과 순위를 기준으로 티어를 반환합니다.

        Args:
            mmr: 유저의 MMR
            rank: 유저의 순위

        Returns:
            티어 이름 (예: "다이아몬드 1", "이터니티" 등)
        """
        if mmr == 0:
            return "언랭크"

        # 이터니티와 데미갓은 미스릴 RP + 700 도달 후 순위 기반
        ranked_gate = cls.TIERS["미스릴"]["base"] + 700
        if mmr >= ranked_gate:
            if rank <= 300:
                return "이터니티"
            elif rank <= 1000:
                return "데미갓"
            return "미스릴"

        # 나머지 티어는 MMR만으로 판단
        for tier, info in cls.TIERS.items():
            if tier in ("이터니티", "데미갓"):
                continue
            if mmr >= info["base"]:
                return tier

        return "언랭크"

    @classmethod
    def get_tier_icon(cls, tier: str) -> str:
        """
        티어에 해당하는 아이콘 파일명을 반환합니다.

        Args:
            tier: 티어 이름

        Returns:
            아이콘 파일명 (예: "6")
        """
        return cls.TIERS.get(tier, cls.TIERS["언랭크"])["icon"]
