"""
投資代理人 v3.0 — 紙上交易券商
完全模擬真實交易，計算手續費與稅金
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional

try:
    from .base import BrokerBase, OrderResult, AccountInfo
    from ..database import (
        get_holdings, upsert_holding, add_transaction,
        get_transactions, get_mission, update_mission_balance, log_decision
    )
    from ..data.market_data import get_stock_price
    from ..config import DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT
except ImportError:
    from brokers.base import BrokerBase, OrderResult, AccountInfo
    from database import (
        get_holdings, upsert_holding, add_transaction,
        get_transactions, get_mission, update_mission_balance, log_decision
    )
    from data.market_data import get_stock_price
    from config import DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT

log = logging.getLogger("investment.paper")

# ─── 交易成本 ───
FEE_RATE = 0.001425 * 0.5  # 手續費 0.1425% 打5折
TAX_RATE_BUY = 0.0          # 買進免稅
TAX_RATE_SELL = 0.003       # 賣出證交稅 0.3%
MIN_FEE = 20.0              # 最低手續費


class PaperBroker(BrokerBase):
    """紙上交易券商 — 完全本地模擬"""

    def __init__(self, mission_id: int):
        self.mission_id = mission_id
        self._order_counter = 0

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"PAPER-{self.mission_id}-{self._order_counter:04d}"

    async def get_account(self) -> AccountInfo:
        mission = await get_mission(self.mission_id)
        if not mission:
            return AccountInfo(mode="paper")

        holdings = await get_holdings(self.mission_id)

        # 計算持股市值
        market_value = 0.0
        positions = []
        for h in holdings:
            quote = await get_stock_price(h["symbol"])
            current_price = quote.price if quote else h["avg_cost"]
            mv = h["shares"] * current_price
            pnl = mv - (h["shares"] * h["avg_cost"])
            pnl_pct = (pnl / (h["shares"] * h["avg_cost"]) * 100) if h["shares"] > 0 and h["avg_cost"] > 0 else 0
            market_value += mv
            positions.append({
                "symbol": h["symbol"],
                "name": h.get("name", ""),
                "shares": h["shares"],
                "avg_cost": round(h["avg_cost"], 2),
                "current_price": round(current_price, 2),
                "market_value": round(mv, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })

        balance = mission["current_balance"]
        total_asset = balance + market_value
        total_pnl = total_asset - mission["budget"]
        total_pnl_pct = (total_pnl / mission["budget"] * 100) if mission["budget"] > 0 else 0

        return AccountInfo(
            mode="paper",
            balance=round(balance, 2),
            total_asset=round(total_asset, 2),
            market_value=round(market_value, 2),
            pnl=round(total_pnl, 2),
            pnl_pct=round(total_pnl_pct, 2),
            positions=positions,
        )

    async def get_positions(self) -> List[Dict]:
        holdings = await get_holdings(self.mission_id)
        result = []
        for h in holdings:
            quote = await get_stock_price(h["symbol"])
            current_price = quote.price if quote else h["avg_cost"]
            mv = h["shares"] * current_price
            pnl = mv - (h["shares"] * h["avg_cost"])
            pnl_pct = (pnl / (h["shares"] * h["avg_cost"]) * 100) if h["shares"] > 0 and h["avg_cost"] > 0 else 0
            result.append({
                "symbol": h["symbol"],
                "name": h.get("name", ""),
                "shares": h["shares"],
                "avg_cost": round(h["avg_cost"], 2),
                "current_price": round(current_price, 2),
                "market_value": round(mv, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
        return result

    async def place_order(self, symbol: str, side: str, shares: int,
                          price: float = 0.0, order_type: str = "M",
                          reason: str = "") -> OrderResult:
        """模擬下單（市價單立刻成交）"""
        mission = await get_mission(self.mission_id)
        if not mission:
            return OrderResult(success=False, mode="paper", message="任務不存在")

        if mission["status"] != "active":
            return OrderResult(success=False, mode="paper", message="任務非活躍狀態")

        # 取得即時報價
        quote = await get_stock_price(symbol)
        if not quote or quote.price <= 0:
            return OrderResult(success=False, mode="paper", symbol=symbol, side=side,
                             message=f"無法取得 {symbol} 報價")

        exec_price = quote.price if order_type == "M" else price
        total = exec_price * shares

        # 計算費用
        fee = max(total * FEE_RATE, MIN_FEE)
        tax = total * TAX_RATE_SELL if side.upper() == "SELL" else 0

        holdings = await get_holdings(self.mission_id)
        current_holding = next((h for h in holdings if h["symbol"] == symbol), None)
        current_shares = current_holding["shares"] if current_holding else 0

        if side.upper() == "BUY":
            cost = total + fee
            if cost > mission["current_balance"]:
                return OrderResult(success=False, mode="paper", symbol=symbol, side=side,
                                 message=f"資金不足: 需要 {cost:,.0f}，可用 {mission['current_balance']:,.0f}")
            # 扣款
            new_balance = mission["current_balance"] - cost
            # 更新持倉
            new_shares = current_shares + shares
            new_avg = ((current_shares * (current_holding["avg_cost"] if current_holding else 0)) + total) / new_shares
        else:  # SELL
            if current_shares < shares:
                return OrderResult(success=False, mode="paper", symbol=symbol, side=side,
                                 message=f"庫存不足: 需要 {shares} 股，持有 {current_shares} 股")
            revenue = total - fee - tax
            new_balance = mission["current_balance"] + revenue
            new_shares = current_shares - shares
            new_avg = current_holding["avg_cost"] if current_holding else 0

        # 更新持倉
        await upsert_holding(self.mission_id, symbol, quote.name, new_shares, new_avg)

        # 記錄交易
        order_id = self._next_order_id()
        await add_transaction(
            self.mission_id, symbol, quote.name, side.upper(),
            shares, exec_price, total, reason, "Executor",
            fee=round(fee, 2), tax=round(tax, 2)
        )

        # 計算總資產
        new_holdings = await get_holdings(self.mission_id)
        mkt_val = 0.0
        for h in new_holdings:
            q = await get_stock_price(h["symbol"])
            mkt_val += h["shares"] * (q.price if q else h["avg_cost"])
        total_asset = new_balance + mkt_val
        total_pnl = total_asset - mission["budget"]
        total_pnl_pct = (total_pnl / mission["budget"] * 100) if mission["budget"] > 0 else 0

        await update_mission_balance(self.mission_id, round(new_balance, 2),
                                      round(total_asset, 2), round(total_pnl, 2),
                                      round(total_pnl_pct, 2))

        # 判斷是否達成目標
        status_msg = ""
        mission_updated = await get_mission(self.mission_id)
        if mission_updated and total_asset >= mission_updated["target_amount"]:
            try:
                from ..database import complete_mission
            except ImportError:
                from database import complete_mission
            await complete_mission(self.mission_id, "completed")
            status_msg = " 🎯 任務達成！"

        return OrderResult(
            success=True, mode="paper", symbol=symbol, side=side.upper(),
            shares=shares, price=exec_price, total_amount=total,
            fee=round(fee, 2), tax=round(tax, 2),
            order_id=order_id,
            message=f"{'買進' if side.upper()=='BUY' else '賣出'} {symbol} {shares}股 @ {exec_price}{status_msg}",
            filled_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def cancel_order(self, order_id: str, symbol: str = "", side: str = "") -> OrderResult:
        return OrderResult(success=False, mode="paper", message="紙上交易暫不支援刪單")

    async def get_orders(self) -> List[Dict]:
        return await get_transactions(self.mission_id, 20)
