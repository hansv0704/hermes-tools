"""
實盤交易引擎 Live Trading Engine — Phase 3
- 包裝 MegaSpeedySession（兆豐 SpeedyAPI）
- 提供與 PaperTradingEngine 完全相容的 buy/sell/get_positions/get_account 介面
- 支援 paper / live 雙模式動態切換
- 預設 paper 模式（安全），需手動 /login_mega + /trade_mode live 才會觸及實盤

架構：
  handlers.py ──→ live_engine.login() / .get_status() / .set_mode()
  mission_executor.py ──→ live_engine.buy() / .sell() / .get_positions() / .get_account()
"""
from __future__ import annotations
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger(__name__)

# ─── 手續費設定（與 paper_trading_engine 一致）───
COMMISSION_RATE = 0.001425
TAX_RATE = 0.003
MIN_COMMISSION = 20


class LiveTradingEngine:
    """實盤交易引擎 — 單例，包裝 MegaSpeedySession。

    ┌─ paper 模式（預設）──┐    ┌─ live 模式 ──────────────┐
    │ PaperTradingEngine    │    │ MegaSpeedySession        │
    │ (alice_core.db)       │    │ (spapi.emega.com.tw)     │
    └───────────────────────┘    └──────────────────────────┘
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._mode: str = "paper"       # "paper" | "live"
        self._session = None            # MegaSpeedySession（延遲初始化）
        self._user_id: str = ""
        self._account: str = ""
        self._broker_id: str = ""
        self._initialized = True

    # ═══════════════════════════════════════════
    #  模式管理
    # ═══════════════════════════════════════════

    @property
    def is_live(self) -> bool:
        """是否已在實盤模式且已登入"""
        return self._mode == "live" and self._is_connected

    @property
    def _is_connected(self) -> bool:
        if self._session is None:
            return False
        try:
            status = self._session.get_status()
            return status.get("logged_in", False)
        except Exception:
            return False

    def _ensure_connected(self) -> dict:
        """P1-5: session 健康檢查。若斷線則回報狀態而非靜默失敗"""
        if self._session is None:
            return {"status": "error", "message": "無 session 實例，請重新 /login_mega"}
        try:
            status = self._session.get_status()
            if not status.get("logged_in", False):
                return {
                    "status": "error",
                    "message": "⚠️ 兆豐 session 已過期，請重新 /login_mega",
                    "detail": status,
                }
            return {"status": "success", "message": "連線正常"}
        except Exception as e:
            return {"status": "error", "message": f"⚠️ session 健康檢查失敗: {e}，請重新登入"}

    def get_mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> dict:
        """切換交易模式：paper 或 live"""
        if mode not in ("paper", "live"):
            return {"status": "error", "message": f"無效模式: {mode}，僅支援 paper/live"}

        old_mode = self._mode
        self._mode = mode

        if mode == "live" and not self._is_connected:
            return {
                "status": "warning",
                "message": f"已切換至 🟢 實盤模式，但尚未登入兆豐。請使用 /login_mega 登入。",
                "mode": mode,
            }

        return {
            "status": "success",
            "message": f"✅ 已從 {old_mode.upper()} 切換至 {mode.upper()} 模式",
            "mode": mode,
        }

    # ═══════════════════════════════════════════
    #  登入 / 登出
    # ═══════════════════════════════════════════

    def verify_credentials(self) -> dict:
        """驗證憑證與環境是否就緒（不實際登入，輕量檢查）

        檢查項目：
        1. .env 中 MEGA_ACCOUNT / MEGA_PASSWORD 是否存在
        2. 憑證檔案 (.pfx) 是否存在
        3. DNS 是否能解析下單主機
        4. SpeedyAPI DLL 是否可載入
        """
        issues = []

        # 1. 環境變數檢查
        account = os.getenv("MEGA_ACCOUNT")
        password = os.getenv("MEGA_PASSWORD")
        if not account:
            issues.append("❌ .env 缺少 MEGA_ACCOUNT")
        if not password:
            issues.append("❌ .env 缺少 MEGA_PASSWORD")

        # 2. 憑證檔案檢查
        pfx_path = Path(__file__).resolve().parent / "MEGA" / "MEGARA" / "R124662445.pfx"
        if not pfx_path.exists():
            issues.append(f"❌ 憑證檔案不存在: {pfx_path}")

        # 3. DNS 解析檢查
        try:
            import socket
            socket.getaddrinfo("spapi.emega.com.tw", 56789, socket.AF_INET, socket.SOCK_STREAM)
        except (socket.gaierror, socket.timeout, OSError):
            issues.append("❌ DNS 無法解析 spapi.emega.com.tw:56789")

        # 4. SpeedyAPI DLL 檢查
        try:
            from skills.mega_speedy_skill import MEGA_SPEEDY_DIR
            dll_path = Path(MEGA_SPEEDY_DIR) / "megaSpeedyAPI_64.dll"
            if not dll_path.exists():
                issues.append(f"❌ SpeedyAPI DLL 不存在: {dll_path}")
        except ImportError:
            issues.append("❌ 無法載入 mega_speedy_skill 模組")

        if issues:
            return {
                "status": "error",
                "ready": False,
                "message": "憑證驗證失敗",
                "issues": issues,
            }

        return {
            "status": "success",
            "ready": True,
            "message": "✅ 憑證驗證通過，可進行登入",
            "account_masked": account[:2] + "***" + account[-2:] if account and len(account) >= 4 else "N/A",
        }

    def login(self, user_id: str, password: str, account: str,
              broker_id: str, pfx_password: str) -> dict:
        """登入兆豐 SpeedyAPI"""
        try:
            from skills.mega_speedy_skill import get_session

            session = get_session()
            result = session.connect_and_login(
                user_id=user_id,
                password=password,
                account=account,
                broker_id=broker_id,
                pfx_password=pfx_password,
            )

            if result.get("status") == "success":
                self._session = session
                self._user_id = user_id
                self._account = account
                self._broker_id = broker_id
                self._mode = "live"  # 登入成功自動切換至 live

            return result

        except ImportError as e:
            return {"status": "error", "message": f"SpeedyAPI 模組載入失敗: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"登入異常: {str(e)}"}

    def get_status(self) -> dict:
        """查詢連線狀態"""
        base = {
            "is_live": self._mode == "live",
            "connected": False,
            "logged_in": False,
            "account": self._account or "N/A",
            "broker_id": self._broker_id or "N/A",
            "user_id": self._user_id or "N/A",
            "mode": self._mode,
        }
        if self._session:
            try:
                s = self._session.get_status()
                base["connected"] = s.get("connected", False)
                base["logged_in"] = s.get("logged_in", False)
                base["account"] = s.get("account", self._account)
                base["broker_id"] = s.get("broker_id", self._broker_id)
                base["user_id"] = s.get("user_id", self._user_id)
            except Exception:
                pass
        return base

    # ═══════════════════════════════════════════
    #  交易介面（相容 PaperTradingEngine）
    # ═══════════════════════════════════════════

    def buy(self, symbol: str, shares: int, price: float,
            name: str = "", strategy: str = "manual") -> dict:
        """買入 — 依當前模式路由"""

        symbol = symbol.strip().upper()
        if not symbol or shares <= 0 or price <= 0:
            return {"status": "error", "message": "參數不完整"}

        if self._mode == "live":
            return self._live_buy(symbol, shares, price, name, strategy)
        else:
            # paper 模式：委派給 PaperTradingEngine
            from paper_trading_engine import paper_engine
            return paper_engine.buy(symbol, shares, price, name, strategy)

    def sell(self, symbol: str, shares: int, price: float,
             strategy: str = "manual", note: str = "") -> dict:
        """賣出 — 依當前模式路由"""

        symbol = symbol.strip().upper()
        if not symbol or shares <= 0 or price <= 0:
            return {"status": "error", "message": "參數不完整"}

        if self._mode == "live":
            return self._live_sell(symbol, shares, price, strategy, note)
        else:
            from paper_trading_engine import paper_engine
            return paper_engine.sell(symbol, shares, price, strategy, note)

    def get_positions(self) -> list:
        """取得持倉"""
        if self._mode == "live" and self._is_connected:
            return self._live_positions()
        else:
            from paper_trading_engine import paper_engine
            return paper_engine.get_positions()

    def get_account(self) -> dict:
        """取得帳戶資訊"""
        if self._mode == "live" and self._is_connected:
            return self._live_account()
        else:
            from paper_trading_engine import paper_engine
            return paper_engine.get_account()

    def get_orders(self, limit: int = 50) -> list:
        """取得委託歷史"""
        if self._mode == "live" and self._is_connected:
            return self._live_orders(limit)
        else:
            from paper_trading_engine import paper_engine
            return paper_engine.get_orders(limit)

    # ═══════════════════════════════════════════
    #  實盤操作（私有）
    # ═══════════════════════════════════════════

    def _live_buy(self, symbol: str, shares: int, price: float,
                  name: str, strategy: str) -> dict:
        """實盤買入 — 限價單 ROD + P1-3 成交確認 + P3-2 交易時間檢查"""
        health = self._ensure_connected()
        if health["status"] != "success":
            return {"status": "error", "message": health["message"]}

        # P3-2: 交易時間檢查
        is_open, market_msg = self._check_market_hours()
        if not is_open:
            return {"status": "market_closed", "message": f"🕐 {market_msg}，實盤下單已攔截"}

        market = self._detect_market(symbol)

        try:
            result = self._session.place_order(
                symbol=symbol,
                side="BUY",
                price=price,
                quantity=shares,
                market=market,
            )

            if result.get("status") != "success":
                return result

            order_id = result.get("order_id")
            total = shares * price
            commission = max(total * COMMISSION_RATE, MIN_COMMISSION)

            # P1-3: 輪詢訂單狀態（最多 5 秒）
            filled = self._poll_order_status(order_id, symbol)
            if filled is None:
                return {
                    "status": "partial",
                    "message": f"📈 [實盤] 買入 {name or symbol} ({symbol}) {shares}股 @${price:.2f} — ⚠️ 訂單已送出但無法確認成交，請手動檢查",
                    "order_id": order_id,
                    "total_cost": round(total + commission, 2),
                    "commission": round(commission, 2),
                    "new_balance": None,
                }
            elif filled == 0:
                return {
                    "status": "pending",
                    "message": f"📈 [實盤] 買入 {name or symbol} ({symbol}) {shares}股 @${price:.2f} — ⏳ 尚未成交（限價單等待中）",
                    "order_id": order_id,
                    "total_cost": round(total + commission, 2),
                    "commission": round(commission, 2),
                    "new_balance": None,
                }

            return {
                "status": "success",
                "message": f"📈 [實盤] 買入 {name or symbol} ({symbol}) {shares}股 @${price:.2f} ✅ 已成交",
                "order_id": order_id,
                "filled_shares": filled,
                "total_cost": round(total + commission, 2),
                "commission": round(commission, 2),
                "new_balance": None,
            }

        except Exception as e:
            return {"status": "error", "message": f"實盤買入異常: {str(e)}"}

    def _live_sell(self, symbol: str, shares: int, price: float,
                   strategy: str, note: str) -> dict:
        """實盤賣出 — 限價單 ROD + P1-3 成交確認 + P3-2 交易時間檢查"""
        health = self._ensure_connected()
        if health["status"] != "success":
            return {"status": "error", "message": health["message"]}

        # P3-2: 交易時間檢查
        is_open, market_msg = self._check_market_hours()
        if not is_open:
            return {"status": "market_closed", "message": f"🕐 {market_msg}，實盤下單已攔截"}

        market = self._detect_market(symbol)

        # 檢查庫存
        positions = self._live_positions()
        holding = next((p for p in positions if p["symbol"] == symbol), None)
        if not holding:
            return {"status": "error", "message": f"未持有 {symbol}，無法賣出"}
        if shares > holding["shares"]:
            return {"status": "error", "message": f"賣出股數 ({shares}) 超過持有 ({holding['shares']})"}

        try:
            result = self._session.place_order(
                symbol=symbol,
                side="SELL",
                price=price,
                quantity=shares,
                market=market,
            )

            if result.get("status") != "success":
                return result

            order_id = result.get("order_id")
            total = shares * price
            commission = max(total * COMMISSION_RATE, MIN_COMMISSION)
            tax = total * TAX_RATE

            # P1-3: 輪詢訂單狀態
            filled = self._poll_order_status(order_id, symbol)
            if filled is None:
                return {
                    "status": "partial",
                    "message": f"📉 [實盤] 賣出 {symbol} {shares}股 @${price:.2f} — ⚠️ 訂單已送出但無法確認成交，請手動檢查",
                    "order_id": order_id,
                    "net_proceeds": round(total - commission - tax, 2),
                    "commission": round(commission, 2),
                    "tax": round(tax, 2),
                    "new_balance": None,
                    "remaining_shares": holding["shares"] - shares,
                }
            elif filled == 0:
                return {
                    "status": "pending",
                    "message": f"📉 [實盤] 賣出 {symbol} {shares}股 @${price:.2f} — ⏳ 尚未成交（限價單等待中）",
                    "order_id": order_id,
                    "net_proceeds": round(total - commission - tax, 2),
                    "commission": round(commission, 2),
                    "tax": round(tax, 2),
                    "new_balance": None,
                    "remaining_shares": holding["shares"] - shares,
                }

            return {
                "status": "success",
                "message": f"📉 [實盤] 賣出 {symbol} {shares}股 @${price:.2f} ✅ 已成交",
                "order_id": order_id,
                "filled_shares": filled,
                "net_proceeds": round(total - commission - tax, 2),
                "commission": round(commission, 2),
                "tax": round(tax, 2),
                "new_balance": None,
                "remaining_shares": holding["shares"] - shares,
            }

        except Exception as e:
            return {"status": "error", "message": f"實盤賣出異常: {str(e)}"}

    def _live_positions(self) -> list:
        """查詢實盤庫存"""
        if not self._is_connected:
            return []

        try:
            result = self._session.query_positions()
            if result.get("status") != "success":
                return []

            parsed = result.get("parsed", [])
            positions = []
            for item in parsed:
                # Mega API 庫存欄位對應
                symbol = item.get("stock_id", item.get("stk_id", item.get("Symbol", ""))).strip()
                if not symbol:
                    continue

                try:
                    shares = int(item.get("qty", item.get("Qty", item.get("shares", 0))))
                except (ValueError, TypeError):
                    shares = 0

                try:
                    cost = float(item.get("cost", item.get("Cost", item.get("avg_cost", 0))))
                except (ValueError, TypeError):
                    cost = 0.0

                name = item.get("stock_name", item.get("stk_name", symbol))

                # 嘗試取得即時價格
                price = self._get_current_price(symbol)

                current_value = shares * price if price else shares * cost
                pnl = current_value - shares * cost if price else 0
                pnl_pct = (pnl / (shares * cost) * 100) if cost > 0 and shares > 0 else 0

                positions.append({
                    "id": 0,
                    "symbol": symbol,
                    "name": name,
                    "shares": shares,
                    "avg_cost": round(cost, 2),
                    "market": "TW",
                    "strategy": "live",
                    "price": round(price, 2) if price else None,
                    "current_value": round(current_value, 2),
                    "cost_basis": round(shares * cost, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "opened_at": str(datetime.now()),
                    "updated_at": str(datetime.now()),
                })
            return positions

        except Exception as e:
            log.warning(f"查詢實盤庫存失敗: {e}")
            return []

    def _live_account(self) -> dict:
        """查詢實盤帳戶（P1-1: 銀行餘額 + P2-5: 券商對帳）"""
        bank_balance = 0.0
        balance_source = "unknown"
        broker_balance = 0.0

        # P1-1: 嘗試從 Mega API 查詢銀行餘額
        if self._is_connected:
            try:
                bank_result = self._session.query_bank_balance()
                if bank_result.get("status") == "success":
                    bank_balance = float(bank_result.get("balance", bank_result.get("available", 0)))
                    balance_source = "mega_api"
            except Exception:
                pass

        # P2-5: 嘗試查詢券商帳戶餘額（已交割可用資金）
        if self._is_connected:
            try:
                broker_result = self._session.query_account_balance()
                if broker_result.get("status") == "success":
                    broker_balance = float(broker_result.get("balance", broker_result.get("available", 0)))
            except Exception:
                pass

        # 若 Mega API 無法取得，fallback 到 paper_engine（跨模式參考）
        if balance_source == "unknown":
            try:
                from paper_trading_engine import paper_engine
                paper_acc = paper_engine.get_account()
                bank_balance = paper_acc.get("balance", 0)
                balance_source = "paper_fallback"
            except Exception:
                bank_balance = 0.0

        # P3-5: 可用資金取銀行與券商中較保守者（避免因交割時差導致超買）
        # 券商餘額 = 已交割 + 未交割款項（T+2），可能 > 銀行餘額
        # 銀行餘額 = 實際已交割現金，可能 < 券商餘額
        # 取 min 確保下單金額不超過實際可動用現金
        available = min(bank_balance, broker_balance) if broker_balance > 0 else bank_balance

        # 查庫存市值
        positions = self._live_positions() if self._is_connected else []
        stock_value = sum(p.get("current_value", 0) for p in positions)

        total_assets = available + stock_value

        # P2-5: 銀行 vs 券商差異
        diff = bank_balance - broker_balance
        diff_note = ""
        if broker_balance > 0:
            if abs(diff) > 100:
                diff_note = f"⚠️ 銀行-券商差額 ${diff:+.0f}，可能有未交割款項"
            else:
                diff_note = "✅ 銀行與券商餘額一致"

        note_parts = []
        if balance_source == "mega_api":
            note_parts.append("✅ Mega API 銀行餘額")
        else:
            note_parts.append("⚠️ 現金為紙上估算值")
        if diff_note:
            note_parts.append(diff_note)

        return {
            "balance": round(available, 2),
            "balance_source": balance_source,
            "bank_balance": round(bank_balance, 2),
            "broker_balance": round(broker_balance, 2),
            "balance_diff": round(diff, 2),
            "initial_balance": round(bank_balance, 2),
            "stock_value": round(stock_value, 2),
            "total_assets": round(total_assets, 2),
            "total_return": 0,
            "total_return_pct": 0,
            "note": " | ".join(note_parts),
        }

    def _live_orders(self, limit: int = 50) -> list:
        """查詢實盤委託"""
        if not self._is_connected:
            return []

        try:
            result = self._session.query_orders()
            if result.get("status") != "success":
                return []

            parsed = result.get("parsed", [])
            orders = []
            for i, item in enumerate(parsed[:limit]):
                orders.append({
                    "id": i,
                    "symbol": item.get("stock_id", item.get("Symbol", "")),
                    "name": item.get("stock_name", ""),
                    "side": item.get("bs", item.get("Side", "")),
                    "shares": item.get("qty", item.get("OrderQty", 0)),
                    "price": float(item.get("price", item.get("Price", 0))),
                    "total": 0,
                    "commission": 0,
                    "tax": 0,
                    "status": item.get("status", item.get("OrdStatus", "")),
                    "strategy": "live",
                    "note": "",
                    "created_at": str(datetime.now()),
                })
            return orders

        except Exception as e:
            log.warning(f"查詢實盤委託失敗: {e}")
            return []

    # ═══════════════════════════════════════════
    #  輔助方法
    # ═══════════════════════════════════════════

    @staticmethod
    def _detect_market(symbol: str) -> str:
        """依股票代碼判斷上市 (tse) 或上櫃 (otc)"""
        if not symbol.isdigit():
            return "tse"
        code = int(symbol)
        if 4000 <= code <= 6999 or 8000 <= code <= 8999:
            return "otc"
        return "tse"

    @staticmethod
    def _check_market_hours() -> tuple:
        """P3-2: 檢查台股是否在交易時間內。回傳 (bool, str)"""
        now = datetime.now()
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute

        if weekday >= 5:
            return False, "週末休市"
        if hour < 9:
            return False, "尚未開盤 (台股 09:00-13:30)"
        if hour > 13 or (hour == 13 and minute > 30):
            return False, "已收盤 (台股 09:00-13:30)"
        return True, "交易中"

    def _poll_order_status(self, order_id: str, symbol: str,
                           max_wait: float = 5.0, interval: float = 0.8) -> Optional[int]:
        """P1-3+P3-3: 輪詢訂單狀態直到成交或超時。
        回傳: 成交股數 (int), None=無法查詢或超時, 0=明確未成交(取消/刪除)"""
        import time
        if not order_id or not self._is_connected:
            return None

        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                result = self._session.query_order(order_id)
                if result.get("status") != "success":
                    time.sleep(interval)
                    continue
                status = result.get("order_status", result.get("status", ""))
                filled_qty = result.get("filled_qty", result.get("filled_quantity", 0))
                if status in ("F", "4", "filled", "dealt", "成交"):
                    return int(filled_qty) if filled_qty else 1  # 保守回報至少成交
                if status in ("C", "D", "cancelled", "deleted", "取消", "刪除"):
                    return 0  # P3-3: 明確未成交
                time.sleep(interval)
            except Exception:
                time.sleep(interval)
        return None  # P3-3: 超時 → 無法確認（與明確未成交區分）

    @staticmethod
    def _get_current_price(symbol: str) -> Optional[float]:
        """取得個股即時價格"""
        try:
            import yfinance as yf
            if symbol.isdigit():
                for suffix in ['.TW', '.TWO']:
                    try:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        p = t.fast_info.get('last_price')
                        if p:
                            return float(p)
                    except Exception:
                        continue
            else:
                t = yf.Ticker(symbol)
                p = t.fast_info.get('last_price')
                if p:
                    return float(p)
        except Exception:
            pass
        return None


# ═══════════════════════════════════════════
#  全域單例
# ═══════════════════════════════════════════
live_engine = LiveTradingEngine()


def get_live_engine() -> LiveTradingEngine:
    return live_engine
