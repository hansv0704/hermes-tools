"""
兆豐 SpeedyAPI 整合 Skill (v2.0 — 繼承模式修正 Access Violation)
封裝 spdOrderAPI (ctypes → megaSpeedyAPI_64.dll)
提供同步操作：連線、登入、查詢庫存/委託/成交、下單

架構：
  Flask API (5002)
    └── mega_speedy_skill.py (Skill 包裝層)
          └── MegaSpeedySession(spdOrderAPI)  ← 直接繼承，非包裝
                └── socket → spapi.emega.com.tw:56789

v2.0 修正：
  - Access Violation: 改為繼承 spdOrderAPI，讓 DLL 回呼正確路由到覆蓋的方法
  - 查詢方法: 改用 dict-based query_param 調用 makeStockAccountInquriy 等原生方法
  - 下單/刪單: 修正參數順序以匹配 SendNewOrderEx / SendCancelOrderEx 真實簽名
"""
import sys
import os
import json
import threading
import time
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ============================================================
#  SpeedyAPI 路徑設定
# ============================================================
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # skills → legacy → root
MEGA_SPEEDY_DIR = str(_BASE_DIR / "MEGA" / "SpeedyAPI_PY" / "megaapi" / "megaSpeedy")
MEGA_PFX_DIR = str(_BASE_DIR / "MEGA" / "MEGARA")
MEGA_PFX_FILE = os.path.join(MEGA_PFX_DIR, "R124662445.pfx")

# 將 megaSpeedy 目錄加入 sys.path 以便 import spdOrderAPI
if MEGA_SPEEDY_DIR not in sys.path:
    sys.path.insert(0, MEGA_SPEEDY_DIR)

# DLL 初始化需要 Temp/ 目錄下的 .ini 檔案，先切換工作目錄
_original_cwd = os.getcwd()
os.chdir(MEGA_SPEEDY_DIR)

try:
    from spdOrderAPI import spdOrderAPI
finally:
    os.chdir(_original_cwd)


# ============================================================
#  MegaSpeedySession — 繼承 spdOrderAPI（解決 Access Violation）
# ============================================================
class MegaSpeedySession(spdOrderAPI):
    """兆豐 SpeedyAPI 連線 Session（直接繼承 spdOrderAPI）。

    因為 DLL 本身是全域狀態，同一時間只能有一個連線。
    使用 threading.Lock 保護所有操作。

    關鍵修正：必須繼承 spdOrderAPI，覆蓋 OnConnected/OnLogonResponse 等事件方法。
    包裝模式（self._api = spdOrderAPI()）會導致 DLL 回呼指向基類的空 pass，
    memory layout 不匹配 → Access Violation。
    """

    def __init__(self):
        # 呼叫 spdOrderAPI.__init__：建立 C++ Obj、註冊事件回呼
        # 因為 self 是 MegaSpeedySession，回呼會正確路由到我們覆蓋的方法
        super().__init__()

        self._lock = threading.Lock()
        self._connected = False
        self._logged_in = False
        self._user_id = ""
        self._account = ""
        self._broker_id = ""
        self._last_error = ""

        # ── 非同步回呼同步化 ──
        self._logon_event = threading.Event()
        self._logon_success = False
        self._logon_message = ""

    # ============================================================
    #  事件回呼（覆蓋 spdOrderAPI 的空方法，由 DLL 背景執行緒觸發）
    # ============================================================
    def OnConnected(self):
        self._connected = True
        log.info("[SpeedyAPI] ✅ 已連線至下單主機")

    def OnDisconnected(self):
        self._connected = False
        self._logged_in = False
        log.info("[SpeedyAPI] ⚠️ 已斷線")

    def OnLogonResponse(self, IsSucceed, ReplyString):
        self._logon_success = IsSucceed
        self._logon_message = str(ReplyString) if ReplyString else ""
        self._logged_in = IsSucceed
        self._logon_event.set()
        log.info(f"[SpeedyAPI] 登入回應: {'✅' if IsSucceed else '❌'} {self._logon_message}")

    def OnReplyNewOrder(self, NID, UDD, Symbol, Price, Side, OrderQty, OrderType, TimeInForce, OrderID):
        log.info(f"[SpeedyAPI] 📝 委託回報 #{NID} {Symbol} {Side} {Price}x{OrderQty} [{OrderID}]")

    def OnFill(self, NID, UDD, OrderID, ReportSequence, FillPrice, FillQty, FillTime):
        log.info(f"[SpeedyAPI] 💰 成交回報 #{NID} {OrderID} @{FillPrice} x {FillQty}")

    def OnRejectOrder(self, NID, UDD, ActionFrom, ErrCode, ErrMsg):
        log.warning(f"[SpeedyAPI] ❌ 委託拒絕 #{NID} [{ActionFrom}] {ErrCode}: {ErrMsg}")

    def OnReplyCancelOrder(self, NID, UDD, Symbol, Price, Side, OrderID):
        log.info(f"[SpeedyAPI] 🗑️ 取消回報 #{NID} {Symbol} {Side} [{OrderID}]")

    def OnReplyReplaceOrder(self, NID, UDD, Symbol, Price, Side, OrderQty, OrderType, TimeInForce, OrderID):
        log.info(f"[SpeedyAPI] ✏️ 改單回報 #{NID} {Symbol} {Side} {Price}x{OrderQty} [{OrderID}]")

    # ============================================================
    #  公開方法（thread-safe）
    # ============================================================
    def connect_and_login(self, user_id: str, password: str, account: str,
                          broker_id: str, pfx_password: str) -> dict:
        """連線 + 憑證設定 + 登入（同步阻塞，最多 15 秒）

        Args:
            user_id:     身分證字號
            password:    電子交易密碼
            account:     證券帳號 (7 碼)
            broker_id:   分公司代碼 (4 碼)
            pfx_password: 憑證密碼
        """
        with self._lock:
            try:
                # ── 1. 檢查憑證 ──
                if not os.path.exists(MEGA_PFX_FILE):
                    return {"status": "error", "message": f"憑證檔案不存在: {MEGA_PFX_FILE}"}

                # ── 2. 設定憑證 ──
                result = self.EnableMEGACA(MEGA_PFX_FILE, user_id, pfx_password)
                if not result:
                    try:
                        self._last_error = self.GetLastErrorMsg()
                    except Exception:
                        self._last_error = "EnableMEGACA 回傳 False"
                    return {"status": "error", "message": f"憑證設定失敗: {self._last_error}"}

                # ── 3. 連線（需在 DLL 目錄下執行，確保 DLL 能找到 Temp/ 與 speedyAPI_config.json）──
                import socket as _socket
                _prev_cwd = os.getcwd()
                os.chdir(MEGA_SPEEDY_DIR)
                try:
                    # DNS 預檢：區分網路不通 vs DLL 層級問題
                    try:
                        _socket.getaddrinfo("spapi.emega.com.tw", 56789, _socket.AF_INET, _socket.SOCK_STREAM)
                    except _socket.gaierror:
                        return {"status": "error", "message": "DNS 解析失敗: spapi.emega.com.tw:56789"}
                    self.Connect("spapi.emega.com.tw", 56789, 10)
                finally:
                    os.chdir(_prev_cwd)

                # 等待 OnConnected 回呼（最多 8 秒）
                waited = 0
                while not self._connected and waited < 8:
                    time.sleep(0.1)
                    waited += 0.1

                if not self._connected:
                    return {"status": "error", "message": "連線逾時（spapi.emega.com.tw:56789）— 請確認防火牆未阻擋"}

                # ── 4. 登入 ──
                self._logon_event.clear()
                self.LogonProxy(user_id, password, account)

                if not self._logon_event.wait(12):
                    return {"status": "error", "message": "登入逾時：未收到主機回應"}

                if not self._logon_success:
                    return {"status": "error", "message": f"登入失敗: {self._logon_message}"}

                # ── 5. 設定交易帳號 (TWSE 證券) ──
                self.SetAccount("TWSE", broker_id, account)

                self._user_id = user_id
                self._account = account
                self._broker_id = broker_id

                return {
                    "status": "success",
                    "message": f"✅ 已登入兆豐證券（帳號: {account}）",
                    "user_id": user_id,
                    "account": account,
                    "broker_id": broker_id,
                }

            except Exception as e:
                return {"status": "error", "message": f"連線異常: {str(e)}"}

    def disconnect(self) -> dict:
        with self._lock:
            try:
                self.Disconnect()
                self._connected = False
                self._logged_in = False
                return {"status": "success", "message": "已斷線"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "logged_in": self._logged_in,
            "user_id": self._user_id,
            "account": self._account,
            "broker_id": self._broker_id,
        }

    def query_positions(self) -> dict:
        """查詢證券庫存（使用 makeStockAccountInquriy）"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.makeStockAccountInquriy({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def query_orders(self) -> dict:
        """查詢當日委託（使用 queryStkOrder）"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryStkOrder({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "apcode": "1",      # 整股
                    "market": "0",      # 全部
                    "qry_type": "0",    # 全部
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def query_matches(self) -> dict:
        """查詢當日成交（使用 queryStkMatch）"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryStkMatch({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "qry_type": "0",    # 成交明細
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def place_order(self, symbol: str, side: str, price: float,
                    quantity: int, market: str = "tse") -> dict:
        """下單（SendNewOrderEx 正確簽名）

        SendNewOrderEx(Market, UDD, Symbol, Price, Side, OrderQty,
                       OrderType, TimeInForce, TradingSession, PositionEffect, TWSEOrdType)
        """
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                side_code = "B" if side.upper() == "BUY" else "S"
                order_id = self.SendNewOrderEx(
                    market,         # Market: 'tse'/'otc'
                    "",             # UDD
                    symbol,         # Symbol
                    price,          # Price
                    side_code,      # Side: 'B'/'S'
                    quantity,       # OrderQty
                    "L",            # OrderType: 'L'=限價
                    "R",            # TimeInForce: 'R'=ROD
                    "N",            # TradingSession: 'N'=普通
                    "A",            # PositionEffect: 'A'=自動(證券)
                    "0",            # TWSEOrdType: '0'=現股
                )
                if order_id > 0:
                    return {
                        "status": "success",
                        "message": "委託已送出",
                        "order_id": order_id,
                        "symbol": symbol,
                        "side": side.upper(),
                        "price": price,
                        "quantity": quantity,
                    }
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {order_id}）"
                    return {"status": "error", "message": f"委託失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def cancel_order(self, order_id: str, symbol: str = "",
                     side: str = "B", market: str = "tse") -> dict:
        """取消委託（SendCancelOrderEx 正確簽名）

        SendCancelOrderEx(Market, UDD, Symbol, Price, Side, OrderID, TradingSession, TWSEOrdType)
        """
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                result = self.SendCancelOrderEx(
                    market,     # Market
                    "",         # UDD
                    symbol,     # Symbol
                    0,          # Price
                    side,       # Side
                    order_id,   # OrderID
                    "N",        # TradingSession
                    "0",        # TWSEOrdType
                )
                if result > 0:
                    return {"status": "success", "message": "取消委託已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"取消失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  改單 (SendReplaceOrderEx)
    # ============================================================
    def replace_order(self, order_id: str, symbol: str, side: str,
                      new_price: float = 0, new_quantity: int = 0,
                      market: str = "tse") -> dict:
        """改單：SendReplaceOrderEx(Market, UDD, Symbol, OrderID, Side, Price, OrderQty, OrderType, TimeInForce, TradingSession, TWSEOrdType)"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                side_code = "B" if side.upper() == "BUY" else "S"
                result = self.SendReplaceOrderEx(
                    market,         # Market
                    "",             # UDD
                    symbol,         # Symbol
                    order_id,       # OrderID
                    side_code,      # Side
                    new_price,      # Price (改價時填新價，減量時填0)
                    new_quantity,   # OrderQty (減量時填新量，改價時填0)
                    "L",            # OrderType
                    "R",            # TimeInForce
                    "N",            # TradingSession
                    "0",            # TWSEOrdType
                )
                if result > 0:
                    return {"status": "success", "message": "改單已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"改單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票下單 (SendNewForeignOrder)
    # ============================================================
    def place_foreign_order(self, symbol: str, side: str, price: float,
                            quantity: int, exchange: str = "US",
                            order_type: str = "L", time_in_force: str = "R",
                            stop_price: float = 0, currency: str = "2",
                            exec_inst: str = "") -> dict:
        """海外股票下單"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                side_code = "B" if side.upper() == "BUY" else "S"
                result = self.SendNewForeignOrder(
                    exchange,       # Exchange
                    "",             # UDD
                    symbol,         # Symbol
                    price,          # Price
                    stop_price,     # StopPrice
                    side_code,      # Side
                    quantity,       # OrderQty
                    order_type,     # OrderType
                    time_in_force,  # TimeInForce
                    currency,       # Currency
                    exec_inst,      # ExecInst
                )
                if result > 0:
                    return {"status": "success", "message": "海外委託已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"海外下單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票刪單 (SendCancelForeignOrder)
    # ============================================================
    def cancel_foreign_order(self, order_id: str, symbol: str = "",
                             side: str = "B", exchange: str = "US") -> dict:
        """海外股票刪單"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                result = self.SendCancelForeignOrder(exchange, "", symbol, side, order_id)
                if result > 0:
                    return {"status": "success", "message": "海外刪單已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"海外刪單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外期貨下單 (SendNewForeignFOrder)
    # ============================================================
    def place_foreign_fut_order(self, symbol: str, side: str, price: float,
                                quantity: int, maturity: str, exchange: str = "",
                                stop_price: float = 0, price_base: int = 1,
                                order_type: str = "L", position_effect: str = "A") -> dict:
        """海外期貨下單"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                side_code = "B" if side.upper() == "BUY" else "S"
                result = self.SendNewForeignFOrder(
                    exchange, "", symbol, maturity, price, stop_price, price_base,
                    side_code, quantity, order_type, position_effect,
                )
                if result > 0:
                    return {"status": "success", "message": "海外期貨委託已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"海外期貨下單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外期貨刪單 (SendCancelForeignFOrder)
    # ============================================================
    def cancel_foreign_fut_order(self, order_id: str, exchange: str = "",
                                 udd: str = "") -> dict:
        """海外期貨刪單"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                result = self.SendCancelForeignFOrder(exchange, order_id, udd)
                if result > 0:
                    return {"status": "success", "message": "海外期貨刪單已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"海外期貨刪單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外期貨改單 (SendReplaceForeignFOrder)
    # ============================================================
    def replace_foreign_fut_order(self, order_id: str, symbol: str, side: str,
                                  maturity: str, exchange: str = "",
                                  new_price: float = 0, new_quantity: int = 0,
                                  stop_price: float = 0, price_base: int = 1,
                                  order_type: str = "L") -> dict:
        """海外期貨改單"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                side_code = "B" if side.upper() == "BUY" else "S"
                result = self.SendReplaceForeignFOrder(
                    exchange, "", symbol, order_id, maturity,
                    new_price, stop_price, price_base, side_code,
                    new_quantity, order_type,
                )
                if result > 0:
                    return {"status": "success", "message": "海外期貨改單已送出", "order_id": result}
                else:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = f"未知錯誤（代碼: {result}）"
                    return {"status": "error", "message": f"海外期貨改單失敗: {err}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  期貨委託查詢 (queryFutOrder)
    # ============================================================
    def query_fut_orders(self, qry_type: str = "0", apcode: str = "") -> dict:
        """查詢期貨當日委託"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryFutOrder({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "type": qry_type,
                    "apcode": apcode,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  期貨成交查詢 (queryFutMatch)
    # ============================================================
    def query_fut_matches(self, apcode: str = "") -> dict:
        """查詢期貨當日成交"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryFutMatch({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "apcode": apcode,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  期貨未平倉查詢 (queryFutUncover)
    # ============================================================
    def query_fut_uncover(self, password: str = "") -> dict:
        """查詢期貨未平倉"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryFutUncover({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "pwd": password,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  期貨即時未平倉 (queryFutUncoverRT)
    # ============================================================
    def query_fut_uncover_rt(self, symbol: str = "", currency: str = "") -> dict:
        """查詢期貨即時未平倉"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryFutUncoverRT({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "stock": symbol,
                    "currency": currency,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  期貨權益數/保證金查詢 (queryMargin)
    # ============================================================
    def query_margin(self, qry_type: str = "0", password: str = "") -> dict:
        """查詢期貨權益數與保證金"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryMargin({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "pwd": password,
                    "type": qry_type,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票庫存查詢 (queryForeignStockInventory)
    # ============================================================
    def query_foreign_inventory(self) -> dict:
        """查詢海外股票庫存"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryForeignStockInventory({"cust_id": self._account})
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票委託查詢 (queryForeignStockOrder)
    # ============================================================
    def query_foreign_orders(self, qry_kind: str = "0") -> dict:
        """查詢海外股票委託"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryForeignStockOrder({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "qry_kind": qry_kind,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票成交查詢 (queryForeignStockFilled)
    # ============================================================
    def query_foreign_matches(self) -> dict:
        """查詢海外股票成交"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.queryForeignStockFilled({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票商品資料下載 (downloadForeignStockProductData)
    # ============================================================
    def download_foreign_products(self, gz_prefix: str = "foreign_products") -> dict:
        """下載海外股票商品資料"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.downloadForeignStockProductData(
                    {"cust_id": self._account}, gz_prefix
                )
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票幣別資料下載 (downloadForeignStockCurrencyData)
    # ============================================================
    def download_foreign_currency(self) -> dict:
        """下載海外股票幣別資料"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.downloadForeignStockCurrencyData({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "apcode": "",
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  海外股票市場資料下載 (downloadForeignStockMarketData)
    # ============================================================
    def download_foreign_markets(self) -> dict:
        """下載海外股票市場資料"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.downloadForeignStockMarketData({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "apcode": "",
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  變更密碼 (changePassword)
    # ============================================================
    def change_password(self, old_pwd: str, new_pwd: str) -> dict:
        """變更電子交易密碼"""
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入"}
            try:
                raw = self.changePassword({
                    "branch_id": self._broker_id,
                    "cust_id": self._account,
                    "func": "",
                    "oldpwd": old_pwd,
                    "newpwd": new_pwd,
                })
                return {"status": "success", "raw": raw, "parsed": self._parse_result(raw)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ============================================================
    #  K線資料（SpeedyAPI 原生 — 含中文名稱 + 技術指標）
    # ============================================================
    def get_kline(self, symbol: str, period: str = "daily") -> dict:
        """取得 K 線資料（日/周/月），含中文名稱與技術指標。

        Args:
            symbol: 股票代碼（如 '2330'）
            period: 'daily'（日K）, 'weekly'（周K）, 'monthly'（月K）
        """
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入交易主機（K線需登入）"}
            try:
                method_map = {
                    "daily": self.GetDKChartData,
                    "weekly": self.GetWKChartData,
                    "monthly": self.GetMKChartData,
                }
                fn = method_map.get(period)
                if not fn:
                    return {"status": "error", "message": f"不支援的周期: {period}"}

                _prev = os.getcwd()
                os.chdir(MEGA_SPEEDY_DIR)
                try:
                    raw = fn(symbol)
                finally:
                    os.chdir(_prev)

                if not raw:
                    return {"status": "error", "message": f"無 {symbol} 的 {period} K線資料（可能已下市或代碼錯誤）"}

                data = json.loads(raw) if isinstance(raw, str) else raw
                return {"status": "success", "symbol": symbol, "period": period, "data": data}
            except json.JSONDecodeError:
                return {"status": "error", "message": f"K線資料解析失敗（非 JSON 格式）"}
            except Exception as e:
                return {"status": "error", "message": f"K線查詢失敗: {str(e)}"}

    def get_adjusted_kline(self, symbol: str, period: str = "daily") -> dict:
        """取得還原 K 線資料（還原權息），含中文名稱。

        Args:
            symbol: 股票代碼
            period: 'daily', 'weekly', 'monthly'
        """
        with self._lock:
            if not self._logged_in:
                return {"status": "error", "message": "尚未登入交易主機"}
            try:
                method_map = {
                    "daily": self.GetAdjustedDKChartData,
                    "weekly": self.GetAdjustedWKChartData,
                    "monthly": self.GetAdjustedMKChartData,
                }
                fn = method_map.get(period)
                if not fn:
                    return {"status": "error", "message": f"不支援的周期: {period}"}

                _prev = os.getcwd()
                os.chdir(MEGA_SPEEDY_DIR)
                try:
                    raw = fn(symbol)
                finally:
                    os.chdir(_prev)

                if not raw:
                    return {"status": "error", "message": f"無 {symbol} 的還原 {period} K線資料"}
                data = json.loads(raw) if isinstance(raw, str) else raw
                return {"status": "success", "symbol": symbol, "period": f"adjusted_{period}", "data": data}
            except Exception as e:
                return {"status": "error", "message": f"還原K線查詢失敗: {str(e)}"}

    # ============================================================
    #  輔助方法
    # ============================================================
    def _parse_result(self, raw: str) -> list:
        """嘗試解析 API 回傳字串 (JSON) 為結構化資料"""
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return [{"value": str(data)}]
        except (json.JSONDecodeError, TypeError):
            # 可能是分隔符號格式
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            return [{"line": l} for l in lines]


# ============================================================
#  全域 Singleton（DLL 全域狀態限制，只能有一個實例）
# ============================================================
_session: MegaSpeedySession = None
_session_lock = threading.Lock()


def get_session() -> MegaSpeedySession:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = MegaSpeedySession()
    return _session


# ============================================================
#  MegaSpeedyQuoteSession — 行情 API（spdQuoteAPI）
# ============================================================

# 重新切換工作目錄以導入 spdQuoteAPI
_prev_cwd_q = os.getcwd()
os.chdir(MEGA_SPEEDY_DIR)
try:
    from spdQuoteAPI import spdQuoteAPI
finally:
    os.chdir(_prev_cwd_q)


class MegaSpeedyQuoteSession(spdQuoteAPI):
    """兆豐 SpeedyAPI 行情連線 Session（繼承 spdQuoteAPI）。

    功能：
      - 連線行情主機，下載全部商品基本資料
      - 提供 get_all_stocks() → {symbol: {name, exchange, ref_price, category, ...}}
      - 提供 get_stock_name(symbol) → 中文名稱
      - 提供 get_stock_info(symbol) → 完整 ContractInfo 欄位

    合約基本資料（ContractInfo）屬性：
      Exchange, Symbol, DisplayName（中文名稱！）, MaturityDate, Category,
      BullPx, BearPx, RefPx, ContractMultiplier, StrikePx, Market,
      TradeUnit, TradeFlag, DayTrade, IsWarrant, WarringStock, CallPut
    """

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._connected = False
        self._logged_in = False
        self._contracts_ready = False
        self._logon_event = threading.Event()
        self._logon_success = False
        self._contract_event = threading.Event()
        # ── 即時報價儲存（Step 2: 行情即時訂閱）──
        from collections import deque as _deque
        self._orderbook_store = {}    # {symbol: deque(maxlen=50)}
        self._trade_store = {}        # {symbol: deque(maxlen=100)}
        self._subscribed = set()      # 已訂閱 symbol
        self._sub_lock = threading.Lock()
        self._deque = _deque

    # ── 事件回呼 ──
    def OnConnected(self):
        self._connected = True
        log.info("[SpeedyQuote] ✅ 已連線至行情主機")

    def OnDisconnected(self):
        self._connected = False
        self._logged_in = False
        self._contracts_ready = False
        log.info("[SpeedyQuote] ⚠️ 行情主機斷線")

    def OnLogonResponse(self, IsSucceed, ReplyString):
        self._logon_success = IsSucceed
        self._logged_in = IsSucceed
        self._logon_event.set()
        log.info(f"[SpeedyQuote] 登入回應: {'✅' if IsSucceed else '❌'} {ReplyString}")

    def OnContractDownloadComplete(self):
        self._contracts_ready = True
        self._contract_event.set()
        count = len(self.Stocks) if hasattr(self, 'Stocks') and self.Stocks else 0
        log.info(f"[SpeedyQuote] 📋 商品下載完成：{count} 檔股票")

    def OnOrderBook(self, Exchange, Symbol, MsgTime, Msg):
        """五檔回呼：存入 deque，供 SSE 即時推送"""
        try:
            entry = {
                "exchange": str(Exchange),
                "symbol": str(Symbol),
                "time": str(MsgTime),
                "bid1_price": float(getattr(Msg, 'BidPrice1', 0) or 0),
                "bid1_qty": int(getattr(Msg, 'BidQty1', 0) or 0),
                "bid2_price": float(getattr(Msg, 'BidPrice2', 0) or 0),
                "bid2_qty": int(getattr(Msg, 'BidQty2', 0) or 0),
                "bid3_price": float(getattr(Msg, 'BidPrice3', 0) or 0),
                "bid3_qty": int(getattr(Msg, 'BidQty3', 0) or 0),
                "bid4_price": float(getattr(Msg, 'BidPrice4', 0) or 0),
                "bid4_qty": int(getattr(Msg, 'BidQty4', 0) or 0),
                "bid5_price": float(getattr(Msg, 'BidPrice5', 0) or 0),
                "bid5_qty": int(getattr(Msg, 'BidQty5', 0) or 0),
                "ask1_price": float(getattr(Msg, 'AskPrice1', 0) or 0),
                "ask1_qty": int(getattr(Msg, 'AskQty1', 0) or 0),
                "ask2_price": float(getattr(Msg, 'AskPrice2', 0) or 0),
                "ask2_qty": int(getattr(Msg, 'AskQty2', 0) or 0),
                "ask3_price": float(getattr(Msg, 'AskPrice3', 0) or 0),
                "ask3_qty": int(getattr(Msg, 'AskQty3', 0) or 0),
                "ask4_price": float(getattr(Msg, 'AskPrice4', 0) or 0),
                "ask4_qty": int(getattr(Msg, 'AskQty4', 0) or 0),
                "ask5_price": float(getattr(Msg, 'AskPrice5', 0) or 0),
                "ask5_qty": int(getattr(Msg, 'AskQty5', 0) or 0),
                "derived_bid": float(getattr(Msg, 'DerivedBidPrice', 0) or 0),
                "derived_bid_qty": int(getattr(Msg, 'DerivedBidQty', 0) or 0),
                "derived_ask": float(getattr(Msg, 'DerivedAskPrice', 0) or 0),
                "derived_ask_qty": int(getattr(Msg, 'DerivedAskQty', 0) or 0),
                "type": "orderbook",
            }
            sym = str(Symbol)
            with self._sub_lock:
                if sym not in self._orderbook_store:
                    self._orderbook_store[sym] = self._deque(maxlen=50)
                self._orderbook_store[sym].append(entry)
        except Exception:
            pass

    def OnTrade(self, Exchange, Symbol, MatchTime, MatchPrice, MatchQty, IsTestMatch):
        """成交回呼：存入 deque，供 SSE 即時推送"""
        try:
            entry = {
                "exchange": str(Exchange),
                "symbol": str(Symbol),
                "time": str(MatchTime),
                "price": float(MatchPrice) if MatchPrice else 0,
                "qty": int(MatchQty) if MatchQty else 0,
                "is_test": bool(IsTestMatch),
                "type": "trade",
            }
            sym = str(Symbol)
            with self._sub_lock:
                if sym not in self._trade_store:
                    self._trade_store[sym] = self._deque(maxlen=100)
                self._trade_store[sym].append(entry)
        except Exception:
            pass

    # ── 公開方法 ──
    def connect_and_download(self, user_id: str, password: str,
                              host: str = "mq.emega.com.tw",
                              port: int = 34567,
                              timeout: int = 40) -> dict:
        """連線行情主機 + 登入 + 下載全部商品。

        Args:
            user_id:  身分證字號（大寫）
            password: 電子交易密碼
            host:     行情主機 IP/DNS（測試: mq.emega.com.tw）
            port:     行情主機 Port（預設 34567）
            timeout:  整體操作逾時秒數
        """
        with self._lock:
            try:
                # ── 1. DNS 預檢 ──
                import socket as _socket
                try:
                    _socket.getaddrinfo(host, port, _socket.AF_INET, _socket.SOCK_STREAM)
                except _socket.gaierror:
                    return {"status": "error", "message": f"DNS 解析失敗: {host}:{port}"}

                # ── 2. 登入行情主機（第四參數 True = 自動下載商品）──
                self._logon_event.clear()
                self._contract_event.clear()

                _prev = os.getcwd()
                os.chdir(MEGA_SPEEDY_DIR)
                try:
                    login_ok = self.Logon(host, port, user_id, password, True)
                finally:
                    os.chdir(_prev)

                if not login_ok:
                    try:
                        err = self.GetLastErrorMsg()
                    except Exception:
                        err = "Logon 回傳 False"
                    return {"status": "error", "message": f"行情登入失敗: {err}"}

                if not self._logon_event.wait(15):
                    return {"status": "error", "message": "行情登入逾時：未收到主機回應"}

                if not self._logon_success:
                    return {"status": "error", "message": "行情登入失敗：帳號或密碼錯誤"}

                # ── 3. 等待商品下載完成 ──
                if not self._contract_event.wait(timeout):
                    return {"status": "error", "message": f"商品下載逾時（{timeout}秒）"}

                stock_count = len(self.Stocks) if hasattr(self, 'Stocks') and self.Stocks else 0
                return {
                    "status": "success",
                    "message": f"✅ 行情已連線，下載 {stock_count} 檔股票",
                    "stock_count": stock_count,
                }

            except Exception as e:
                return {"status": "error", "message": f"行情連線異常: {str(e)}"}

    def disconnect(self) -> dict:
        with self._lock:
            try:
                self.Disconnect()
                self._connected = False
                self._logged_in = False
                self._contracts_ready = False
                return {"status": "success", "message": "行情已斷線"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "logged_in": self._logged_in,
            "contracts_ready": self._contracts_ready,
            "stock_count": len(self.Stocks) if hasattr(self, 'Stocks') and self.Stocks else 0,
        }

    # ── 即時訂閱方法（Step 2）──

    def subscribe(self, symbols: list) -> dict:
        """訂閱即時報價（上限 20 檔）。

        Args:
            symbols: 股票代碼清單，如 ['2330', '2454']
        """
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return {"status": "error", "message": "尚未下載商品資料"}
            results = []
            for sym in symbols:
                if sym in self._subscribed:
                    results.append({"symbol": sym, "status": "already_subscribed"})
                    continue
                contract = self.Stocks.get(sym)
                if not contract:
                    results.append({"symbol": sym, "status": "not_found"})
                    continue
                try:
                    self.SubscribeContract(contract)
                    self._subscribed.add(sym)
                    # 初始化 store
                    with self._sub_lock:
                        if sym not in self._orderbook_store:
                            self._orderbook_store[sym] = self._deque(maxlen=50)
                        if sym not in self._trade_store:
                            self._trade_store[sym] = self._deque(maxlen=100)
                    results.append({"symbol": sym, "status": "subscribed"})
                except Exception as e:
                    results.append({"symbol": sym, "status": "error", "message": str(e)})
            return {"status": "success", "results": results, "subscribed_count": len(self._subscribed)}

    def unsubscribe(self, symbols: list) -> dict:
        """取消訂閱指定標的。"""
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return {"status": "error", "message": "尚未下載商品資料"}
            results = []
            for sym in symbols:
                if sym not in self._subscribed:
                    results.append({"symbol": sym, "status": "not_subscribed"})
                    continue
                contract = self.Stocks.get(sym)
                if contract:
                    try:
                        # spdQuoteAPI 的取消訂閱需要 UnsubscribeContract 或 Unsubscribe
                        # 嘗試 Unsubscribe(Exchange, Symbol)
                        self.Unsubscribe(contract.Exchange, contract.Symbol)
                    except Exception:
                        pass
                self._subscribed.discard(sym)
                results.append({"symbol": sym, "status": "unsubscribed"})
            return {"status": "success", "results": results, "subscribed_count": len(self._subscribed)}

    def unsubscribe_all(self) -> dict:
        """取消全部訂閱。"""
        with self._lock:
            try:
                self.UnsubscribeAll()
                count = len(self._subscribed)
                self._subscribed.clear()
                return {"status": "success", "message": f"已取消 {count} 檔訂閱"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def get_all_subscribed(self) -> list:
        """取得目前訂閱標的清單。"""
        with self._lock:
            return sorted(self._subscribed)

    def get_realtime_quote(self, symbol: str) -> dict:
        """取得指定標的的最新即時報價快照（五檔 + 最新成交）。"""
        with self._sub_lock:
            ob = list(self._orderbook_store.get(symbol, []))
            tr = list(self._trade_store.get(symbol, []))
        return {
            "symbol": symbol,
            "subscribed": symbol in self._subscribed,
            "latest_orderbook": ob[-1] if ob else None,
            "latest_trade": tr[-1] if tr else None,
            "orderbook_count": len(ob),
            "trade_count": len(tr),
        }

    def pop_new_events(self, symbol: str = None) -> list:
        """取出指定標的（或全部）的新事件（用於 SSE 推送），取出後清空。

        Args:
            symbol: 指定標的（None = 全部）
        Returns:
            新事件清單，每個事件含 type: 'orderbook' 或 'trade'
        """
        events = []
        with self._sub_lock:
            if symbol:
                targets = [symbol]
            else:
                targets = list(set(list(self._orderbook_store.keys()) + list(self._trade_store.keys())))
            for sym in targets:
                ob = self._orderbook_store.get(sym)
                tr = self._trade_store.get(sym)
                if ob:
                    while ob:
                        events.append(ob.popleft())
                if tr:
                    while tr:
                        events.append(tr.popleft())
        return events

    def get_all_stocks(self) -> dict:
        """取得全部股票基本資料。{symbol: {name, exchange, ref_price, ...}}"""
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return {}
            result = {}
            for sym, contract in self.Stocks.items():
                try:
                    result[sym] = {
                        "name": getattr(contract, 'DisplayName', sym),
                        "exchange": getattr(contract, 'Exchange', ''),
                        "ref_price": getattr(contract, 'RefPx', None),
                        "category": getattr(contract, 'Category', ''),
                        "trade_unit": getattr(contract, 'TradeUnit', None),
                        "trade_flag": getattr(contract, 'TradeFlag', 0),
                        "bull_px": getattr(contract, 'BullPx', None),
                        "bear_px": getattr(contract, 'BearPx', None),
                        "market": getattr(contract, 'Market', ''),
                        "is_warrant": getattr(contract, 'IsWarrant', False),
                        "warring_stock": getattr(contract, 'WarringStock', 0),
                        "day_trade": getattr(contract, 'DayTrade', ''),
                    }
                except Exception:
                    result[sym] = {"name": sym}
            return result

    def get_stock_name(self, symbol: str) -> str:
        """取得單一股票的中文名稱"""
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return symbol
            contract = self.Stocks.get(symbol)
            if contract:
                return getattr(contract, 'DisplayName', symbol)
            return symbol

    def get_stock_info(self, symbol: str) -> dict:
        """取得單一股票的完整基本資料"""
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return {"symbol": symbol, "name": symbol}
            contract = self.Stocks.get(symbol)
            if not contract:
                return {"symbol": symbol, "name": symbol}
            return {
                "symbol": symbol,
                "name": getattr(contract, 'DisplayName', symbol),
                "exchange": getattr(contract, 'Exchange', ''),
                "ref_price": getattr(contract, 'RefPx', None),
                "category": getattr(contract, 'Category', ''),
                "trade_unit": getattr(contract, 'TradeUnit', None),
                "trade_flag": getattr(contract, 'TradeFlag', 0),
                "bull_px": getattr(contract, 'BullPx', None),
                "bear_px": getattr(contract, 'BearPx', None),
                "market": getattr(contract, 'Market', ''),
                "is_warrant": getattr(contract, 'IsWarrant', False),
                "warring_stock": getattr(contract, 'WarringStock', 0),
                "day_trade": getattr(contract, 'DayTrade', ''),
            }

    def search_stocks_by_name(self, keyword: str, limit: int = 30) -> list:
        """用關鍵字搜尋股票名稱（模糊匹配）"""
        with self._lock:
            if not self._contracts_ready or not hasattr(self, 'Stocks'):
                return []
            results = []
            for sym, contract in self.Stocks.items():
                name = getattr(contract, 'DisplayName', '')
                if keyword in name:
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "exchange": getattr(contract, 'Exchange', ''),
                        "ref_price": getattr(contract, 'RefPx', None),
                        "category": getattr(contract, 'Category', ''),
                    })
                    if len(results) >= limit:
                        break
            return results


# ── 全域 Singleton（行情 Session）──
_quote_session: MegaSpeedyQuoteSession = None
_quote_session_lock = threading.Lock()


def get_quote_session() -> MegaSpeedyQuoteSession:
    global _quote_session
    if _quote_session is None:
        with _quote_session_lock:
            if _quote_session is None:
                _quote_session = MegaSpeedyQuoteSession()
    return _quote_session
