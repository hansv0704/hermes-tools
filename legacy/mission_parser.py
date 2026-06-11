"""
任務解析器 Mission Parser
自然語言 → 策略參數轉換層
將使用者的投資目標（如「一個月翻倍」）轉換為可執行的量化參數
"""
import re
from datetime import datetime, timedelta
from typing import Optional


class MissionParams:
    """任務參數結構"""
    def __init__(self):
        self.risk_level: str = "medium"       # low / medium / high / extreme
        self.timeframe_days: int = 90         # 預計達成天數
        self.target_return_pct: float = 10.0  # 目標報酬率 (%)
        self.max_positions: int = 5           # 最大持股數
        self.max_position_pct: float = 0.20   # 單一持股上限 (佔總資產)
        self.stop_loss_pct: float = 0.05      # 停損 (%)
        self.take_profit_pct: float = 0.15    # 停利 (%)
        self.allow_margin: bool = False       # 是否允許槓桿
        self.allow_short: bool = False        # 是否允許放空
        self.preferred_market: str = "TW"     # TW / US / ALL
        self.scan_frequency: str = "daily"    # daily / weekly / hourly
        self.description: str = ""            # 原始任務描述


class MissionParser:
    """自然語言任務解析器"""

    # ─── 風險關鍵詞 ───
    RISK_KEYWORDS = {
        "extreme": ["翻倍", "暴衝", "梭哈", "all in", "allin", "極限", "瘋狂", "賭", "兩倍", "三倍", "十倍",
                     "all-in", "ALLIN", "最大化", "極端", "超高風險"],
        "high": ["高風險", "高報酬", "激進", "快速成長", "短期爆發", "賺快錢", "冒險", "槓桿",
                  "積極", "衝刺", "一個月內", "兩週內", "一週內", "高回報"],
        "medium": ["穩健", "平衡", "中等", "適中", "成長", "中長期", "定期定額"],
        "low": ["保守", "保本", "安全", "低風險", "存股", "穩定收益", "股息", "被動收入"],
    }

    # ─── 時間關鍵詞 ───
    TIME_KEYWORDS = {
        7: ["一週", "一個禮拜", "7天", "七天", "短期"],
        14: ["兩週", "半個月", "14天", "十四天"],
        30: ["一個月", "30天", "三十天", "月內"],
        60: ["兩個月", "60天", "六十天", "雙月"],
        90: ["三個月", "一季", "90天", "九十天", "季度"],
        180: ["半年", "六個月", "180天"],
        365: ["一年", "12個月", "十二個月", "年度", "長期"],
    }

    # ─── 市場關鍵詞 ───
    MARKET_KEYWORDS = {
        "TW": ["台股", "台灣", "台積", "台灣股市", "TW"],
        "US": ["美股", "美國", "NASDAQ", "NYSE", "那斯達克", "標普", "道瓊", "AAPL", "TSLA", "NVDA"],
        "ALL": ["全球", "不限", "台美", "美台", "全部"],
    }

    @classmethod
    def parse(cls, text: str) -> MissionParams:
        """解析自然語言任務，回傳 MissionParams"""
        params = MissionParams()
        params.description = text.strip()
        text_lower = text.lower()

        # 1. 解析風險等級
        params.risk_level = cls._parse_risk(text_lower)

        # 2. 解析時間框架
        params.timeframe_days = cls._parse_timeframe(text_lower)

        # 3. 解析目標報酬率
        params.target_return_pct = cls._parse_target_return(text_lower, params.risk_level, params.timeframe_days)

        # 4. 解析市場偏好
        params.preferred_market = cls._parse_market(text_lower)

        # 5. 根據風險等級設定預設參數
        cls._apply_risk_profile(params)

        # 6. 根據時間框架微調
        cls._apply_timeframe_adjustment(params)

        return params

    @classmethod
    def _parse_risk(cls, text: str) -> str:
        for level, keywords in cls.RISK_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    return level
        return "medium"

    @classmethod
    def _parse_timeframe(cls, text: str) -> int:
        for days, keywords in sorted(cls.TIME_KEYWORDS.items(), reverse=True):
            for kw in keywords:
                if kw in text:
                    return days
        return 90  # 預設三個月

    @classmethod
    def _parse_target_return(cls, text: str, risk: str, days: int) -> float:
        """從文字中提取目標報酬率"""
        # 直接數字匹配
        pct_match = re.search(r'(\d+)\s*%', text)
        if pct_match:
            return float(pct_match.group(1))

        # 倍數匹配
        multi_match = re.search(r'(\d+)\s*倍', text)
        if multi_match:
            multiplier = float(multi_match.group(1))
            return (multiplier - 1) * 100  # 2 倍 = +100%

        # 翻倍
        if '翻倍' in text or 'double' in text.lower():
            return 100.0

        # 根據風險等級和時間估算
        if risk == "extreme":
            return 100.0
        elif risk == "high":
            return max(20.0, min(50.0, days / 30 * 15))
        elif risk == "medium":
            return max(10.0, min(20.0, days / 30 * 5))
        else:
            return max(5.0, min(10.0, days / 30 * 3))

    @classmethod
    def _parse_market(cls, text: str) -> str:
        for market, keywords in cls.MARKET_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    return market
        return "TW"

    @classmethod
    def _apply_risk_profile(cls, params: MissionParams):
        """根據風險等級設定預設參數"""
        profiles = {
            "extreme": {
                "max_positions": 3,
                "max_position_pct": 0.50,
                "stop_loss_pct": 0.15,
                "take_profit_pct": 0.30,
                "allow_margin": True,
                "scan_frequency": "hourly",
            },
            "high": {
                "max_positions": 5,
                "max_position_pct": 0.30,
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.20,
                "scan_frequency": "daily",
            },
            "medium": {
                "max_positions": 8,
                "max_position_pct": 0.20,
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.15,
                "scan_frequency": "weekly",
            },
            "low": {
                "max_positions": 10,
                "max_position_pct": 0.10,
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.08,
                "scan_frequency": "weekly",
            },
        }
        profile = profiles.get(params.risk_level, profiles["medium"])
        for key, value in profile.items():
            setattr(params, key, value)

    @classmethod
    def _apply_timeframe_adjustment(cls, params: MissionParams):
        """根據時間框架微調止損止盈"""
        if params.timeframe_days <= 14:
            # 極短期：更緊的止損，但允許更寬的上漲空間
            params.stop_loss_pct = min(params.stop_loss_pct, 0.06)
            params.scan_frequency = "hourly"
        elif params.timeframe_days <= 30:
            params.stop_loss_pct = min(params.stop_loss_pct, 0.08)
            params.scan_frequency = "daily"

    @classmethod
    def format_params(cls, params: MissionParams) -> str:
        """將 MissionParams 格式化為可讀文字"""
        risk_emoji = {"extreme": "💀", "high": "🔥", "medium": "📊", "low": "🛡️"}
        market_emoji = {"TW": "🇹🇼", "US": "🇺🇸", "ALL": "🌍"}

        deadline = datetime.now() + timedelta(days=params.timeframe_days)

        return (
            f"🎯 **任務摘要**\n"
            f"──────────────────────\n"
            f"📝 描述: {params.description}\n"
            f"{risk_emoji.get(params.risk_level, '📊')} 風險等級: **{params.risk_level.upper()}**\n"
            f"📅 期限: {params.timeframe_days} 天 (截止: {deadline.strftime('%Y-%m-%d')})\n"
            f"🎯 目標報酬: **+{params.target_return_pct}%**\n"
            f"{market_emoji.get(params.preferred_market, '🌍')} 市場: {params.preferred_market}\n"
            f"📦 最大持股數: {params.max_positions}\n"
            f"📊 單股上限: {params.max_position_pct*100}%\n"
            f"🛑 停損: -{params.stop_loss_pct*100}%\n"
            f"✅ 停利: +{params.take_profit_pct*100}%\n"
            f"📡 掃描頻率: {params.scan_frequency}\n"
            f"🔧 槓桿: {'✅' if params.allow_margin else '❌'} | 放空: {'✅' if params.allow_short else '❌'}"
        )


# ─── 快速測試 ───
if __name__ == "__main__":
    tests = [
        "一個月內讓資產翻倍",
        "我想要穩健成長，存股領股息",
        "高風險短期爆發，兩個月內賺50%",
        "美股保守投資，一年賺10%",
    ]
    for t in tests:
        print(f"\n{'='*50}")
        print(f"輸入: {t}")
        p = MissionParser.parse(t)
        print(MissionParser.format_params(p))
