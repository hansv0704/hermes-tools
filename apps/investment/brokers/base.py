"""
投資代理人 v3.0 — 券商抽象層
定義統一的交易介面，紙上/實盤雙模式
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class OrderResult:
    success: bool
    mode: str                    # paper / live
    symbol: str = ""
    side: str = ""               # BUY / SELL
    shares: int = 0
    price: float = 0.0
    total_amount: float = 0.0
    fee: float = 0.0
    tax: float = 0.0
    order_id: str = ""
    message: str = ""
    filled_at: str = ""

@dataclass
class AccountInfo:
    mode: str
    balance: float = 0.0        # 可用資金
    total_asset: float = 0.0    # 總資產
    market_value: float = 0.0   # 持股市值
    pnl: float = 0.0            # 累計損益
    pnl_pct: float = 0.0        # 損益%
    positions: List[Dict] = field(default_factory=list)

class BrokerBase(ABC):
    """券商抽象基底"""

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """查詢帳戶資訊"""
        ...

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        """查詢持倉"""
        ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, shares: int,
                          price: float = 0.0, order_type: str = "M",
                          reason: str = "") -> OrderResult:
        """下單"""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str = "", side: str = "") -> OrderResult:
        """刪單"""
        ...

    @abstractmethod
    async def get_orders(self) -> List[Dict]:
        """查詢委託"""
        ...
