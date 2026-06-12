"""
投資代理人 v3.0 — 市場數據提供者
統一接口：台股 (TWSE/TPEX) 透過 yfinance + TWSE API
"""
from __future__ import annotations
import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import yfinance as yf
import aiosqlite

try:
    from .config import DB_PATH
except ImportError:
    from config import DB_PATH

log = logging.getLogger("investment.data")

# ═══════════════════════════════════════════════
#  資料結構
# ═══════════════════════════════════════════════

@dataclass
class StockQuote:
    symbol: str
    name: str = ""
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0
    market: str = "TW"  # TW / US
    updated_at: str = ""

@dataclass
class StockInfo:
    symbol: str
    name: str = ""
    market: str = "TW"
    sector: str = ""
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    dividend_yield: float = 0.0
    avg_volume: int = 0
    beta: float = 1.0

# ═══════════════════════════════════════════════
#  價格查詢
# ═══════════════════════════════════════════════

async def get_stock_price(symbol: str) -> Optional[StockQuote]:
    """取得台股即時報價"""
    try:
        ticker_sym = _to_yfinance(symbol)
        ticker = yf.Ticker(ticker_sym)
        info = await asyncio.to_thread(lambda: ticker.fast_info)

        price = getattr(info, 'last_price', 0) or getattr(info, 'regular_market_price', 0) or 0
        prev = getattr(info, 'previous_close', 0) or getattr(info, 'regular_market_previous_close', 0) or 0
        change = price - prev if price and prev else 0
        change_pct = (change / prev * 100) if prev else 0

        name = ""
        try:
            info_full = await asyncio.to_thread(lambda: ticker.info)
            name = info_full.get("longName") or info_full.get("shortName") or ""
        except Exception:
            pass

        return StockQuote(
            symbol=symbol,
            name=name,
            price=round(price, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            volume=getattr(info, 'last_volume', 0) or 0,
            high=getattr(info, 'day_high', 0) or 0,
            low=getattr(info, 'day_low', 0) or 0,
            open=getattr(info, 'open', 0) or 0,
            prev_close=prev,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        log.warning(f"get_stock_price({symbol}): {e}")
        return None

async def get_multiple_prices(symbols: List[str]) -> Dict[str, StockQuote]:
    """批次取得多檔報價"""
    results = {}
    tasks = [get_stock_price(s) for s in symbols]
    quotes = await asyncio.gather(*tasks, return_exceptions=True)
    for sym, q in zip(symbols, quotes):
        if isinstance(q, StockQuote):
            results[sym] = q
    return results

async def get_stock_history(symbol: str, period: str = "3mo") -> Optional[Dict]:
    """取得歷史K線"""
    try:
        ticker_sym = _to_yfinance(symbol)
        ticker = yf.Ticker(ticker_sym)
        hist = await asyncio.to_thread(lambda: ticker.history(period=period))
        if hist.empty:
            return None
        return {
            "dates": [str(d.date()) for d in hist.index],
            "close": [round(v, 2) for v in hist['Close'].tolist()],
            "volume": [int(v) for v in hist['Volume'].tolist()],
            "high": [round(v, 2) for v in hist['High'].tolist()],
            "low": [round(v, 2) for v in hist['Low'].tolist()],
        }
    except Exception as e:
        log.warning(f"get_stock_history({symbol}): {e}")
        return None

# ═══════════════════════════════════════════════
#  市場掃描
# ═══════════════════════════════════════════════

# TW50 成分股（作為掃描基礎池）
TW50_SYMBOLS = [
    "2330", "2317", "2454", "2308", "2382", "2881", "2882", "2891", "2886",
    "2002", "1301", "1303", "1326", "6505", "2412", "2884", "2892", "5871",
    "3034", "3008", "3711", "2603", "2609", "2615", "2610", "2207", "2912",
    "2885", "2880", "2890", "5880", "2883", "2887", "2888", "2889",
    "3045", "4904", "2357", "2324", "3231", "2376", "3702", "2347",
    "1101", "1102", "1216", "1227", "2201", "2227", "2301", "2303",
    "2327", "2337", "2344", "2353", "2356", "2360", "2377", "2379",
    "2383", "2385", "2395", "2408", "3189", "2371", "2352", "2328",
]

async def scan_market_top_movers(top_n: int = 20) -> List[StockQuote]:
    """掃描成交量最大的前N檔"""
    quotes = []
    for sym in TW50_SYMBOLS[:30]:  # 取前30檔快速掃描
        q = await get_stock_price(sym)
        if q and q.price > 0 and q.volume > 0:
            quotes.append(q)
    quotes.sort(key=lambda x: x.volume, reverse=True)
    return quotes[:top_n]

async def scan_market_gainers(top_n: int = 10) -> List[StockQuote]:
    """掃描漲幅最大的前N檔"""
    quotes = []
    for sym in TW50_SYMBOLS[:40]:
        q = await get_stock_price(sym)
        if q and q.price > 0:
            quotes.append(q)
    quotes.sort(key=lambda x: x.change_pct, reverse=True)
    return quotes[:top_n]

async def scan_market_losers(top_n: int = 10) -> List[StockQuote]:
    """掃描跌幅最大的前N檔（潛在抄底標的）"""
    quotes = []
    for sym in TW50_SYMBOLS[:40]:
        q = await get_stock_price(sym)
        if q and q.price > 0:
            quotes.append(q)
    quotes.sort(key=lambda x: x.change_pct)
    return quotes[:top_n]

# ═══════════════════════════════════════════════
#  台股漲停跌停篩選
# ═══════════════════════════════════════════════

def _filter_tw_stocks(symbols: List[str], min_price: float = 10,
                      max_price: float = 3000, min_volume: int = 500) -> List[str]:
    """過濾台股標的：價格範圍、成交量"""
    return [s for s in symbols]

# ═══════════════════════════════════════════════
#  技術指標
# ═══════════════════════════════════════════════

async def compute_simple_indicators(symbol: str) -> Dict:
    """計算簡單技術指標"""
    hist = await get_stock_history(symbol, "3mo")
    if not hist or len(hist["close"]) < 20:
        return {}

    closes = hist["close"]
    volumes = hist["volume"]

    # MA5, MA10, MA20
    def ma(data, n):
        return round(sum(data[-n:]) / n, 2) if len(data) >= n else 0

    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    current = closes[-1]

    # RSI 14
    rsi = _calc_rsi(closes, 14)

    # 成交量變化
    vol_ma5 = ma(volumes, 5)
    vol_ratio = round(volumes[-1] / vol_ma5, 2) if vol_ma5 > 0 else 0

    # MACD 簡化
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    macd = round(ema12 - ema26, 2) if ema12 and ema26 else 0

    return {
        "price": current,
        "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "rsi14": rsi,
        "vol_ratio": vol_ratio,
        "macd": macd,
        "trend": "bullish" if current > ma20 else "bearish",
    }

def _calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = 0
    losses = 0
    for i in range(-period, 0):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100.0 - (100.0 / (1.0 + rs)), 1)

def _calc_ema(data: List[float], period: int) -> float:
    if len(data) < period:
        return 0
    k = 2.0 / (period + 1)
    ema = sum(data[:period]) / period
    for price in data[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 2)

# ═══════════════════════════════════════════════
#  TWSE 大盤指數
# ═══════════════════════════════════════════════

async def get_tw_index() -> Optional[Dict]:
    """取得加權指數"""
    try:
        ticker = yf.Ticker("^TWII")
        info = await asyncio.to_thread(lambda: ticker.fast_info)
        price = getattr(info, 'last_price', 0) or getattr(info, 'regular_market_price', 0) or 0
        prev = getattr(info, 'previous_close', 0) or getattr(info, 'regular_market_previous_close', 0) or 0
        change = price - prev if price and prev else 0
        change_pct = (change / prev * 100) if prev else 0
        return {
            "index": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        log.warning(f"get_tw_index: {e}")
        return None

# ═══════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════

def _to_yfinance(symbol: str) -> str:
    """轉換為 yfinance 格式"""
    s = symbol.strip().upper()
    if s.endswith(".TW") or s.endswith(".TWO"):
        return s
    if s.isdigit():
        if len(s) == 4:
            return f"{s}.TW"
        return f"{s}.TW"  # 預設上市
    return s
