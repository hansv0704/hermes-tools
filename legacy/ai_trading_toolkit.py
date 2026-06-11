"""
AI 交易工具包 AITradingToolkit v1.0
===================================
讓 AI 自主循環能透過統一介面操作紙上/實盤交易。
支援雙模式無縫切換，一個 API 兩套引擎。

模式：
  - paper: 紙上交易（paper_trading_engine）
  - live:  真實交易（mega_speedy_skill → 兆豐 SpeedyAPI）

AI 工具清單（6 個）：
  1. get_account(mode)          → 查詢帳戶
  2. get_positions(mode)        → 查詢庫存
  3. get_orders(mode)           → 查詢委託
  4. place_order(symbol,side,price,qty,mode) → 下單
  5. cancel_order(order_id,symbol,side,mode)  → 刪單
  6. get_stock_price(symbol)    → 取得即時報價
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """統一的交易結果"""
    success: bool
    action: str          # BUY / SELL / CANCEL / QUERY
    mode: str            # paper / live
    symbol: str = ""
    quantity: int = 0
    price: float = 0.0
    order_id: str = ""
    message: str = ""
    raw: Dict = field(default_factory=dict)


class AITradingToolkit:
    """AI 交易工具包 — 雙模式統一介面
    
    使用方式：
        toolkit = AITradingToolkit(default_mode="paper")
        
        # 查詢
        acc = toolkit.get_account()
        positions = toolkit.get_positions()
        
        # 下單
        result = toolkit.place_order("2330", "BUY", 500, 1000)
        
        # 切換模式
        toolkit.set_mode("live")
        result = toolkit.place_order("2330", "BUY", 500, 1000)  # 真實下單
    """
    
    def __init__(self, default_mode: str = "paper"):
        self.default_mode = default_mode
        self._paper_engine = None
        self._speedy_session = None
        self._quote_session = None
        
        # 安全限制
        self.max_order_value_live: float = 100_000   # 實盤單筆上限 10 萬
        self.require_confirmation_live: bool = True    # 實盤需要確認
    
    # ── 延遲導入避免循環依賴 ──
    
    @property
    def paper_engine(self):
        if self._paper_engine is None:
            from paper_trading_engine import paper_engine
            self._paper_engine = paper_engine
        return self._paper_engine
    
    @property
    def speedy_session(self):
        if self._speedy_session is None:
            from skills.mega_speedy_skill import get_session as get_speedy_session
            self._speedy_session = get_speedy_session()
        return self._speedy_session
    
    @property
    def quote_session(self):
        if self._quote_session is None:
            from skills.mega_speedy_skill import get_quote_session
            self._quote_session = get_quote_session()
        return self._quote_session
    
    # ── 模式管理 ──
    
    def set_mode(self, mode: str):
        """切換預設交易模式"""
        if mode not in ("paper", "live"):
            raise ValueError(f"無效模式: {mode}，只能為 paper 或 live")
        self.default_mode = mode
    
    def get_mode(self) -> str:
        return self.default_mode
    
    # ── 1. 帳戶查詢 ──
    
    def get_account(self, mode: str = None) -> Dict:
        """查詢帳戶摘要
        
        Returns:
            {status, mode, balance, total_assets, total_return_pct, ...}
        """
        mode = mode or self.default_mode
        
        if mode == "paper":
            try:
                acc = self.paper_engine.get_account()
                return {
                    "status": "success",
                    "mode": "paper",
                    "balance": acc.get("balance", 0),
                    "total_assets": acc.get("total_assets", 0),
                    "total_return_pct": acc.get("total_return_pct", 0),
                    "raw": acc,
                }
            except Exception as e:
                return {"status": "error", "mode": "paper", "message": str(e)}
        
        else:  # live
            try:
                # 從 DuckDB bank_balance + Speedy positions 計算總資產
                import duckdb
                conn = duckdb.connect('alice_core.db')
                row = conn.execute("SELECT balance FROM bank_balance WHERE id = 1").fetchone()
                bank = float(row[0]) if row and row[0] else 0
                conn.close()
                
                raw = self.speedy_session.query_positions()
                stock_value = 0.0
                if raw.get("status") == "success":
                    stksum = raw.get("parsed", [])
                    if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
                        stksum = stksum[0]['stksumList']
                    for s in stksum:
                        valuemkt = s.get('valuemkt') or s.get('valuenow')
                        if valuemkt and float(valuemkt) > 0:
                            stock_value += float(valuemkt)
                
                return {
                    "status": "success",
                    "mode": "live",
                    "bank_balance": bank,
                    "stock_value": stock_value,
                    "total_assets": bank + stock_value,
                    "raw": raw,
                }
            except Exception as e:
                return {"status": "error", "mode": "live", "message": str(e)}
    
    # ── 2. 庫存查詢 ──
    
    def get_positions(self, mode: str = None) -> Dict:
        """查詢目前持倉"""
        mode = mode or self.default_mode
        
        if mode == "paper":
            try:
                positions = self.paper_engine.get_positions()
                return {"status": "success", "mode": "paper", "positions": positions, "count": len(positions)}
            except Exception as e:
                return {"status": "error", "mode": "paper", "message": str(e)}
        
        else:  # live
            try:
                raw = self.speedy_session.query_positions()
                if raw.get("status") != "success":
                    return {"status": "error", "mode": "live", "message": raw.get("message", "無法取得庫存")}
                
                stksum = raw.get("parsed", [])
                if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
                    stksum = stksum[0]['stksumList']
                
                positions = []
                for s in stksum:
                    positions.append({
                        "symbol": s.get('stkno', '').strip(),
                        "name": s.get('stkna', ''),
                        "shares": int(float(s.get('costqty', 0))),
                        "avg_cost": float(s.get('priceavg', 0)),
                        "market_value": float(s.get('valuemkt', 0)),
                    })
                
                return {"status": "success", "mode": "live", "positions": positions, "count": len(positions)}
            except Exception as e:
                return {"status": "error", "mode": "live", "message": str(e)}
    
    # ── 3. 委託查詢 ──
    
    def get_orders(self, mode: str = None) -> Dict:
        """查詢當日委託"""
        mode = mode or self.default_mode
        
        if mode == "paper":
            try:
                orders = self.paper_engine.get_orders(limit=50)
                return {"status": "success", "mode": "paper", "orders": orders, "count": len(orders)}
            except Exception as e:
                return {"status": "error", "mode": "paper", "message": str(e)}
        
        else:  # live
            try:
                raw = self.speedy_session.query_orders()
                return {"status": raw.get("status", "error"), "mode": "live", **raw}
            except Exception as e:
                return {"status": "error", "mode": "live", "message": str(e)}
    
    # ── 4. 下單 ──
    
    def place_order(self, symbol: str, side: str, price: float, 
                    quantity: int, mode: str = None,
                    market: str = "tse") -> TradeResult:
        """下單（買入/賣出）
        
        Args:
            symbol: 股票代號
            side: BUY / SELL
            price: 委託價格
            quantity: 委託數量（股）
            mode: paper / live（預設使用 default_mode）
            market: tse / otc（僅 live 模式）
        """
        mode = mode or self.default_mode
        side = side.upper()
        
        # ── 安全檢查 ──
        order_value = price * quantity
        
        if mode == "live" and order_value > self.max_order_value_live:
            return TradeResult(
                success=False, action=side, mode=mode,
                symbol=symbol, quantity=quantity, price=price,
                message=f"❌ 實盤單筆超過上限 ${self.max_order_value_live:,.0f}（此筆 ${order_value:,.0f}）"
            )
        
        if mode == "paper":
            try:
                if side == "BUY":
                    result = self.paper_engine.buy(symbol, quantity, price, strategy="ai_autonomous")
                else:
                    result = self.paper_engine.sell(symbol, quantity, price, strategy="ai_autonomous")
                
                success = result.get("status") == "success"
                return TradeResult(
                    success=success, action=side, mode="paper",
                    symbol=symbol, quantity=quantity, price=price,
                    message=result.get("message", ""), raw=result,
                )
            except Exception as e:
                return TradeResult(
                    success=False, action=side, mode="paper",
                    symbol=symbol, quantity=quantity, price=price,
                    message=str(e),
                )
        
        else:  # live
            try:
                result = self.speedy_session.place_order(symbol, side, price, quantity, market)
                success = result.get("status") == "success"
                return TradeResult(
                    success=success, action=side, mode="live",
                    symbol=symbol, quantity=quantity, price=price,
                    order_id=str(result.get("order_id", "")),
                    message=result.get("message", ""), raw=result,
                )
            except Exception as e:
                return TradeResult(
                    success=False, action=side, mode="live",
                    symbol=symbol, quantity=quantity, price=price,
                    message=str(e),
                )
    
    # ── 5. 刪單 ──
    
    def cancel_order(self, order_id: str, symbol: str = "", 
                     side: str = "B", mode: str = None) -> TradeResult:
        """取消委託"""
        mode = mode or self.default_mode
        
        if mode == "paper":
            return TradeResult(
                success=False, action="CANCEL", mode="paper",
                order_id=order_id, message="紙上模式不支援刪單",
            )
        
        else:  # live
            try:
                result = self.speedy_session.cancel_order(order_id, symbol, side)
                return TradeResult(
                    success=result.get("status") == "success",
                    action="CANCEL", mode="live",
                    order_id=order_id, symbol=symbol,
                    message=result.get("message", ""), raw=result,
                )
            except Exception as e:
                return TradeResult(
                    success=False, action="CANCEL", mode="live",
                    order_id=order_id, message=str(e),
                )
    
    # ── 6. 即時報價（輔助工具） ──
    
    def get_stock_price(self, symbol: str) -> Dict:
        """取得即時報價（優先 SpeedyAPI 行情，fallback yfinance）"""
        # 先嘗試 SpeedyAPI 行情
        try:
            quote = self.quote_session
            if quote.get_status().get("contracts_ready"):
                info = quote.get_stock_info(symbol)
                if info and info.get("ref_price"):
                    return {
                        "status": "success", "symbol": symbol,
                        "price": info.get("ref_price"),
                        "name": info.get("name", symbol),
                        "source": "speedy",
                    }
        except Exception:
            pass
        
        # fallback yfinance
        try:
            import yfinance as yf
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{symbol}{suffix}")
                    fast = t.fast_info
                    price = fast.get('last_price') or t.info.get('currentPrice')
                    if price:
                        return {
                            "status": "success", "symbol": symbol,
                            "price": price,
                            "name": t.info.get('shortName', symbol),
                            "source": "yfinance",
                        }
                except:
                    continue
        except:
            pass
        
        return {"status": "error", "symbol": symbol, "message": "無法取得報價"}
    
    # ── 風險檢查 ──
    
    def check_risk(self, symbol: str, side: str, quantity: int, 
                   price: float, mode: str = None) -> Dict:
        """下單前風險檢查
        
        檢查項目：
        1. 資金是否足夠
        2. 是否超過單一標的上限
        """
        mode = mode or self.default_mode
        issues = []
        warnings = []
        
        order_value = price * quantity
        
        if side == "BUY":
            acc = self.get_account(mode)
            if acc.get("status") == "success":
                if mode == "paper":
                    available = acc.get("balance", 0)
                else:
                    available = acc.get("bank_balance", 0)
                
                if order_value > available:
                    issues.append(f"資金不足：需要 ${order_value:,.0f}，可用 ${available:,.0f}")
                elif order_value > available * 0.8:
                    warnings.append(f"⚠️ 此筆佔可用資金 {(order_value/available*100):.0f}%")
        
        # 集中度檢查
        positions = self.get_positions(mode)
        if positions.get("status") == "success":
            total_value = sum(
                p.get("market_value", 0) or p.get("current_value", 0) 
                for p in positions.get("positions", [])
            )
            acc = self.get_account(mode)
            total_assets = acc.get("total_assets", total_value)
            if total_assets > 0 and order_value > total_assets * 0.3:
                warnings.append(f"⚠️ 此筆佔總資產 {(order_value/total_assets*100):.0f}%，超過 30% 警戒線")
        
        return {
            "status": "blocked" if issues else ("warning" if warnings else "ok"),
            "issues": issues,
            "warnings": warnings,
            "order_value": order_value,
        }


# ═══════════════════════════════════════════════
#  全域實例
# ═══════════════════════════════════════════════

_toolkit: Optional[AITradingToolkit] = None


def get_toolkit(default_mode: str = "paper") -> AITradingToolkit:
    """取得全域 AITradingToolkit 實例（延遲初始化）"""
    global _toolkit
    if _toolkit is None:
        _toolkit = AITradingToolkit(default_mode=default_mode)
    return _toolkit


def reset_toolkit():
    """重置全域實例"""
    global _toolkit
    _toolkit = None
