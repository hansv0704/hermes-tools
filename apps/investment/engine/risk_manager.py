"""
投資代理人 v3.0 — 風險管理引擎
負責部位大小計算、停損停利觸發、資金管理
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

log = logging.getLogger("investment.risk")


class RiskManager:
    """風險管理 — Kelly 公式、部位大小、停損停利"""

    def __init__(self, risk_level: str = "moderate"):
        self.risk_level = risk_level
        self._profiles = {
            "conservative": {"kelly_fraction": 0.25, "max_positions": 3, "max_single_pct": 0.15,
                            "stop_loss": 0.03, "take_profit": 0.08},
            "moderate":     {"kelly_fraction": 0.40, "max_positions": 5, "max_single_pct": 0.20,
                            "stop_loss": 0.05, "take_profit": 0.12},
            "aggressive":   {"kelly_fraction": 0.60, "max_positions": 8, "max_single_pct": 0.30,
                            "stop_loss": 0.08, "take_profit": 0.20},
            "extreme":      {"kelly_fraction": 0.80, "max_positions": 10, "max_single_pct": 0.40,
                            "stop_loss": 0.12, "take_profit": 0.30},
        }
        self.profile = self._profiles.get(risk_level, self._profiles["moderate"])

    # ═══════════════════════════════════════════
    #  部位計算
    # ═══════════════════════════════════════════

    def calculate_position_size(self, total_asset: float, confidence: float = 0.6,
                                 volatility: float = 0.02, win_prob: float = 0.55) -> int:
        """
        使用 Kelly 公式計算建議部位大小
        
        Args:
            total_asset: 總資產
            confidence: AI 信心度 (0-1)
            volatility: 標的波動率
            win_prob: 預估勝率
            
        Returns:
            建議投入金額
        """
        # Kelly: f* = p - (1-p) / (W/L)
        # 簡化: f* = (win_prob - (1 - win_prob)) * kelly_fraction
        edge = max(0, win_prob - 0.5)
        kelly_pct = edge * 2 * self.profile["kelly_fraction"]
        
        # 波動率調整
        vol_adj = min(1.0, 0.02 / max(volatility, 0.005))
        kelly_pct *= vol_adj
        
        # 信心度加權
        kelly_pct *= confidence
        
        # 上限限制
        kelly_pct = min(kelly_pct, self.profile["max_single_pct"])
        kelly_pct = max(kelly_pct, 0.02)  # 最少 2%
        
        amount = total_asset * kelly_pct
        return round(amount, -3)  # 取到千位

    def can_add_position(self, current_positions: int) -> bool:
        """檢查是否還可以增加部位"""
        return current_positions < self.profile["max_positions"]

    # ═══════════════════════════════════════════
    #  停損停利檢查
    # ═══════════════════════════════════════════

    def check_stop_conditions(self, positions: List[Dict]) -> List[Dict]:
        """
        檢查所有持倉是否需要停損/停利
        
        Returns:
            [{"symbol": "2330", "action": "STOP_LOSS", "pnl_pct": -8.5, "reason": "..."}, ...]
        """
        alerts = []
        for pos in positions:
            pnl_pct = pos.get("pnl_pct", 0)

            if pnl_pct <= -self.profile["stop_loss"] * 100:
                alerts.append({
                    "symbol": pos["symbol"],
                    "name": pos.get("name", ""),
                    "action": "STOP_LOSS",
                    "pnl_pct": round(pnl_pct, 2),
                    "reason": f"觸及停損線 ({-self.profile['stop_loss']*100}%)，目前 {pnl_pct:.1f}%",
                })
            elif pnl_pct >= self.profile["take_profit"] * 100:
                alerts.append({
                    "symbol": pos["symbol"],
                    "name": pos.get("name", ""),
                    "action": "TAKE_PROFIT",
                    "pnl_pct": round(pnl_pct, 2),
                    "reason": f"達停利目標 ({self.profile['take_profit']*100}%)，目前 {pnl_pct:.1f}%",
                })

        return alerts

    # ═══════════════════════════════════════════
    #  時間壓力調整
    # ═══════════════════════════════════════════

    def adjust_for_time_pressure(self, deadline_str: str, current_asset: float,
                                  target_amount: float) -> Dict:
        """
        根據剩餘時間調整策略參數
        
        Returns:
            {"time_pressure": 0-1, "urgency": "high"/"medium"/"low",
             "adjusted_kelly": float, "recommendation": str}
        """
        try:
            deadline = datetime.fromisoformat(deadline_str)
            now = datetime.now()
            remaining_days = (deadline - now).days
        except Exception:
            remaining_days = 30

        total_days = max(remaining_days, 1)  # 預設至少30天
        progress = current_asset / target_amount if target_amount > 0 else 0
        
        # 時間壓力 = 進度缺口 / 剩餘時間比例
        needed_progress = 1.0 - progress
        time_ratio = remaining_days / max(total_days, 1)
        
        if time_ratio <= 0.1 and progress < 0.8:
            time_pressure = 1.0
            urgency = "critical"
        elif time_ratio <= 0.3 and progress < 0.6:
            time_pressure = 0.7
            urgency = "high"
        elif time_ratio <= 0.5 and progress < 0.4:
            time_pressure = 0.5
            urgency = "medium"
        else:
            time_pressure = 0.2
            urgency = "low"

        adj_kelly = self.profile["kelly_fraction"]
        if urgency in ("critical", "high"):
            adj_kelly = min(adj_kelly * 1.5, 1.0)  # 提高槓桿但設上限

        return {
            "time_pressure": round(time_pressure, 2),
            "urgency": urgency,
            "remaining_days": remaining_days,
            "progress_pct": round(progress * 100, 1),
            "adjusted_kelly": round(adj_kelly, 2),
            "recommendation": (
                "時間緊迫，建議提高週轉率" if urgency == "critical"
                else "加速佈局，把握機會" if urgency == "high"
                else "按計畫穩健執行" if urgency == "medium"
                else "進度良好，持續觀察"
            ),
        }

    # ═══════════════════════════════════════════
    #  現金儲備
    # ═══════════════════════════════════════════

    def reserve_cash(self, total_asset: float) -> float:
        """保留現金緩衝"""
        return total_asset * 0.05  # 保留 5%

    def available_cash(self, total_asset: float, balance: float) -> float:
        """計算可投入現金（扣除儲備）"""
        reserve = self.reserve_cash(total_asset)
        return max(0, balance - reserve)
