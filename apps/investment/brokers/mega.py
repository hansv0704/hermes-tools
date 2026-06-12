"""
投資代理人 v3.0 — 兆豐證券實盤券商
封裝 legacy mega_speedy_skill.py，透過執行緒池橋接同步 DLL
"""
from __future__ import annotations
import asyncio
import json
import logging
import sys
import os
import threading
from pathlib import Path
from typing import List, Dict, Optional

from .base import BrokerBase, OrderResult, AccountInfo

log = logging.getLogger("investment.mega")

# ─── 路徑設定 ───
_BASE = Path(__file__).resolve().parent.parent.parent.parent
_MEGA_SPEEDY_DIR = str(_BASE / "MEGA" / "SpeedyAPI_PY" / "megaapi" / "megaSpeedy")
_MEGA_PFX_FILE = str(_BASE / "MEGA" / "MEGARA" / "R124662445.pfx")

# 確保 DLL 目錄在 path
if _MEGA_SPEEDY_DIR not in sys.path:
    sys.path.insert(0, _MEGA_SPEEDY_DIR)

# Legacy skill 路徑
_LEGACY_SKILLS = str(_BASE / "legacy" / "skills")
if _LEGACY_SKILLS not in sys.path:
    sys.path.insert(0, _LEGACY_SKILLS)

def _patch_mega_paths():
    """修正 mega_speedy_skill 內部路徑（原 skill 內部使用相對路徑指向 legacy/MEGA/...）"""
    try:
        import mega_speedy_skill as mss
        mss.MEGA_SPEEDY_DIR = _MEGA_SPEEDY_DIR
        mss.MEGA_PFX_DIR = str(_BASE / "MEGA" / "MEGARA")
        mss.MEGA_PFX_FILE = _MEGA_PFX_FILE
    except ImportError:
        pass


class MegaBroker(BrokerBase):
    """兆豐證券 SpeedyAPI 實盤券商"""

    def __init__(self, mission_id: int = 0):
        self.mission_id = mission_id
        self._session = None
        self._logged_in = False
        self._user_id = ""
        self._account = ""
        self._broker_id = ""
        self._executor = ThreadPoolExecutor(max_workers=1)

    @property
    def logged_in(self) -> bool:
        return self._logged_in and self._session is not None

    def _get_session(self):
        """取得或建立 MegaSpeedySession"""
        if self._session is None:
            _patch_mega_paths()  # 修正路徑後再 import
            from mega_speedy_skill import MegaSpeedySession
            self._session = MegaSpeedySession()
        return self._session

    async def login(self, user_id: str, password: str, account: str,
                    broker_id: str, pfx_password: str) -> Dict:
        """登入兆豐交易主機"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._sync_login,
            user_id, password, account, broker_id, pfx_password
        )
        if result.get("status") == "success":
            self._logged_in = True
            self._user_id = user_id
            self._account = account
            self._broker_id = broker_id
        return result

    def _sync_login(self, user_id, password, account, broker_id, pfx_password) -> Dict:
        try:
            session = self._get_session()
            result = session.connect_and_login(
                user_id=user_id,
                password=password,
                account=account,
                broker_id=broker_id,
                pfx_password=pfx_password
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def logout(self):
        """登出並斷線"""
        if self._session:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._session.Disconnect)
            self._logged_in = False
            self._session = None

    # ═══════════════════════════════════════════
    #  帳戶查詢
    # ═══════════════════════════════════════════

    async def get_account(self) -> AccountInfo:
        if not self.logged_in:
            return AccountInfo(mode="mega", balance=0)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._sync_query_account
        )
        return result

    def _sync_query_account(self) -> AccountInfo:
        try:
            query_param = {
                "branch_id": self._broker_id,
                "cust_id": self._account,
            }
            raw = self._session.makeStockAccountInquriy(query_param)
            # makeStockAccountInquriy 回傳 JSON 字串，需解析
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not raw or raw.get("result") != "0":
                err = raw.get("message", "unknown") if raw else "None"
                log.error(f"MEGA query error: {err}")
                return AccountInfo(mode="mega", balance=0)

            # 彙總庫存市值
            market_value = 0.0
            positions = []
            for item in raw.get("stksumList", []):
                qty = int(item.get("qtyl", 0))
                price = float(item.get("pricenow", 0))
                mv = qty * price
                market_value += mv
                positions.append({
                    "symbol": item.get("stkno", ""),
                    "name": item.get("stkna", ""),
                    "shares": qty,
                    "avg_cost": float(item.get("priceavg", 0)),
                    "current_price": price,
                    "market_value": mv,
                    "pnl": float(item.get("makeasum", 0)),
                    "pnl_pct": float(item.get("makeaper", 0)),
                })

            return AccountInfo(
                mode="mega",
                balance=0,  # MEGA 需另外查
                total_asset=market_value,
                market_value=market_value,
                pnl=float(raw.get("makeant", 0) if "stktotList" in raw and raw["stktotList"] else 0),
                pnl_pct=0,
                positions=positions,
            )
        except Exception as e:
            log.error(f"Query MEGA account failed: {e}")
            return AccountInfo(mode="mega", balance=0)

    # ═══════════════════════════════════════════
    #  持倉
    # ═══════════════════════════════════════════

    async def get_positions(self) -> List[Dict]:
        acc = await self.get_account()
        return acc.positions

    # ═══════════════════════════════════════════

    async def place_order(self, symbol: str, side: str, shares: int,
                          price: float = 0.0, order_type: str = "M",
                          reason: str = "") -> OrderResult:
        if not self.logged_in:
            return OrderResult(success=False, mode="mega", message="尚未登入兆豐")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._sync_place_order,
            symbol, side, shares, price, order_type
        )
        return result

    def _sync_place_order(self, symbol, side, shares, price, order_type) -> OrderResult:
        try:
            market = "tse"  # 預設上市
            if len(symbol) == 4:
                market = "tse"  # 上市
            else:
                market = "tse"  # 預設

            nid = self._session.SendNewOrderEx(
                Market=market,
                UDD=f"AI-{self.mission_id:04d}",
                Symbol=symbol,
                Price=price if order_type == "L" else 0,
                Side="B" if side.upper() == "BUY" else "S",
                OrderQty=shares,
                OrderType=order_type if order_type in ("L", "M", "P") else "M",
                TimeInForce="R",
                TradingSession="N",
                PositionEffect="A",
                TWSEOrdType="0"
            )
            if nid == 0:
                msg = self._session.GetLastErrorMsg() if hasattr(self._session, 'GetLastErrorMsg') else "unknown"
                return OrderResult(success=False, mode="mega", symbol=symbol, side=side,
                                 message=f"下單失敗: {msg}")
            return OrderResult(
                success=True, mode="mega", symbol=symbol, side=side.upper(),
                shares=shares, price=price, order_id=str(nid),
                message=f"MEGA 委託 #{nid}: {symbol} {side} {shares}股"
            )
        except Exception as e:
            return OrderResult(success=False, mode="mega", message=str(e))

    async def cancel_order(self, order_id: str, symbol: str = "", side: str = "") -> OrderResult:
        if not self.logged_in:
            return OrderResult(success=False, mode="mega", message="尚未登入")
        # TODO: 實作取消
        return OrderResult(success=False, mode="mega", message="取消功能待實作")

    async def get_orders(self) -> List[Dict]:
        if not self.logged_in:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._sync_query_orders)

    def _sync_query_orders(self) -> List[Dict]:
        try:
            query_param = {
                "branch_id": self._broker_id,
                "cust_id": self._account,
                "apcode": "0",
                "market": "0",
                "qry_type": "0",
                "nocsint": "N",
            }
            raw = self._session.queryStkOrder(query_param)
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not raw or raw.get("result") != "0":
                return []
            orders = []
            for item in raw.get("ackList", []):
                orders.append({
                    "order_id": item.get("ordno", ""),
                    "symbol": item.get("stockno", ""),
                    "side": "BUY" if item.get("buysell") == "B" else "SELL",
                    "price": float(item.get("odprice", 0)),
                    "quantity": int(item.get("orgqty", 0)),
                    "filled": int(item.get("matqty", 0)),
                    "status": item.get("ordstatus", ""),
                })
            return orders
        except Exception as e:
            log.error(f"Query MEGA orders failed: {e}")
            return []


# ═══════════════════════════════════════════════
#  全局 Mega session（DLL 是全域狀態）
# ═══════════════════════════════════════════════

_global_mega: Optional[MegaBroker] = None
_login_state: Dict = {"logged_in": False, "user_id": "", "account": ""}

async def get_mega_broker(mission_id: int = 0) -> MegaBroker:
    """取得全局 MEGA broker（DLL 限制只能一個連線）"""
    global _global_mega
    if _global_mega is None:
        _global_mega = MegaBroker(mission_id)
    return _global_mega

async def mega_login(user_id: str, password: str, account: str,
                     broker_id: str, pfx_password: str) -> Dict:
    broker = await get_mega_broker()
    result = await broker.login(user_id, password, account, broker_id, pfx_password)
    _login_state["logged_in"] = broker.logged_in
    _login_state["user_id"] = user_id
    _login_state["account"] = account
    return result

async def mega_logout():
    global _global_mega
    if _global_mega:
        await _global_mega.logout()
        _global_mega = None
    _login_state["logged_in"] = False
    _login_state["user_id"] = ""
    _login_state["account"] = ""

def get_login_state() -> Dict:
    return dict(_login_state)


# 在檔案結尾 import（避免循環）
from concurrent.futures import ThreadPoolExecutor
