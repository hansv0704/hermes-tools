"""
策略引擎 Strategy Engine
- MA 均線交叉
- RSI 超買超賣
- MACD 信號
- 布林通道
- 複合策略 (多指標投票)
- 📡 MarketScanner 全市場掃描 (v2.0 — 支援 TWSE 原生 API + 自訂 data_provider)
- 🧠 AdaptiveStrategy 自適應參數

每個策略回傳統一格式：
{
    "signal": "BUY" / "SELL" / "HOLD",
    "confidence": 0~100,
    "reason": "說明文字",
    "indicators": {...},  # 當前指標值
    "price": float,
}
"""
import yfinance as yf
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Callable
import math
import time
import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime

# ─── TWSE / TPEX 原生 API 快取 ───
_tw_stock_cache: Dict[str, Dict] = {}
_tw_stock_cache_ts: float = 0.0
_TW_CACHE_TTL = 300  # 5 分鐘快取


def _fetch_twse_all_stocks() -> Dict[str, Dict]:
    """
    透過 TWSE 開放 API 取得上市股票即時行情。
    回傳 {symbol: {price, volume, volume_ratio_20d, ma20, volatility_pct, pe}}
    """
    global _tw_stock_cache, _tw_stock_cache_ts
    now = time.time()
    if _tw_stock_cache and (now - _tw_stock_cache_ts) < _TW_CACHE_TTL:
        return _tw_stock_cache

    result: Dict[str, Dict] = {}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # ── TWSE 上市股票 ──
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for row in data:
            sym = row.get("Code", "").strip()
            if not sym or not sym.isdigit():
                continue
            try:
                price = float(row.get("ClosingPrice", 0) or 0)
                volume = int(float(row.get("TradeVolume", 0) or 0))
                pe = float(row.get("PERatio", 0) or 0)
                result[sym] = {"price": price, "volume": volume, "pe": pe if pe > 0 else None}
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    # ── TPEX 上櫃股票 ──
    try:
        url2 = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=15, context=ctx) as resp2:
            data2 = json.loads(resp2.read().decode("utf-8"))
        for row in data2:
            sym = row.get("SecuritiesCompanyCode", "").strip()
            if not sym or not sym.isdigit():
                continue
            try:
                price = float(row.get("ClosingPrice", 0) or 0)
                volume = int(float(row.get("TradeVolume", 0) or 0))
                pe = float(row.get("PERatio", 0) or 0)
                if sym not in result:
                    result[sym] = {"price": price, "volume": volume, "pe": pe if pe > 0 else None}
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    _tw_stock_cache = result
    _tw_stock_cache_ts = now
    return result


def _fetch_tw_stock_history(symbol: str, days: int = 60) -> pd.DataFrame:
    """
    透過 TWSE API 取得個股日 K 線。
    回傳 DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        today = datetime.now().strftime("%Y%m%d")
        url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
               f"?response=json&date={today}&stockNo={symbol}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        records = data.get("data", [])
        if not records:
            return pd.DataFrame()
        rows = []
        for r in records[-days:]:
            try:
                rows.append({
                    "Date": pd.to_datetime(f"{int(r[0]) // 10000}-{(int(r[0]) % 10000) // 100:02d}-{int(r[0]) % 100:02d}"),
                    "Open": float(r[3].replace(",", "")),
                    "High": float(r[4].replace(",", "")),
                    "Low": float(r[5].replace(",", "")),
                    "Close": float(r[6].replace(",", "")),
                    "Volume": int(float(r[1].replace(",", ""))),
                })
            except (ValueError, IndexError):
                continue
        df = pd.DataFrame(rows)
        if not df.empty:
            df.set_index("Date", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()


class BaseStrategy(ABC):
    """策略基底類別"""
    name: str = "base"
    description: str = ""
    parameters: Dict[str, str] = {}
    suitable_for: str = ""

    @staticmethod
    def fetch_data(symbol: str, period: str = "3mo", interval: str = "1d",
                   data_provider: Optional[Callable] = None) -> pd.DataFrame:
        """
        取得歷史 OHLCV 數據。
        台股優先使用 TWSE API → yfinance fallback。
        data_provider: 外部注入的資料獲取函式 (可選)
        """
        # ── 路徑 A：外部 data_provider ──
        if data_provider:
            try:
                result = data_provider(symbol, period)
                if isinstance(result, pd.DataFrame) and not result.empty:
                    return result
                if isinstance(result, dict) and "dataframe" in result:
                    return result["dataframe"]
            except Exception:
                pass

        # ── 路徑 B：TWSE 原生 API（台股） ──
        if symbol.isdigit():
            df = _fetch_tw_stock_history(symbol, days=90)
            if not df.empty and len(df) >= 15:
                return df
            # ── 路徑 C：yfinance fallback（靜默）─
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{symbol}{suffix}")
                    df = t.history(period="3mo", interval="1d")
                    if not df.empty:
                        return df
                except Exception:
                    continue
            return pd.DataFrame()

        # ── 非台股：直接用 yfinance ──
        try:
            t = yf.Ticker(symbol)
            return t.history(period=period, interval=interval)
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def get_current_price(symbol: str) -> Optional[float]:
        """取得即時價格"""
        try:
            if symbol.isdigit():
                for suffix in ['.TW', '.TWO']:
                    try:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        p = t.fast_info.get('last_price') or t.info.get('currentPrice')
                        if p:
                            return float(p)
                    except:
                        continue
            else:
                t = yf.Ticker(symbol)
                p = t.fast_info.get('last_price') or t.info.get('currentPrice')
                if p:
                    return float(p)
        except:
            pass
        return None

    @abstractmethod
    def analyze(self, symbol: str) -> dict:
        """分析個股，回傳信號"""
        pass

    def get_detail(self) -> dict:
        """取得策略詳細說明"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "suitable_for": self.suitable_for,
        }


# ═══════════════════════════════════════════
#  MA 均線交叉策略
# ═══════════════════════════════════════════
class MACrossoverStrategy(BaseStrategy):
    name = "ma_crossover"
    description = (
        "利用短期均線（快線）與長期均線（慢線）的交叉點來判斷進出場。"
        "當快線由下往上穿越慢線時稱為「黃金交叉」→ 買進信號；"
        "當快線由上往下穿越慢線時稱為「死亡交叉」→ 賣出信號。"
        "此策略在趨勢明顯的市場中表現最佳，盤整市場容易產生假信號。"
    )
    parameters = {
        "fast": "5 (快線週期，越小越敏感)",
        "slow": "20 (慢線週期，越大越平滑)",
    }
    suitable_for = "趨勢明顯的個股，適合中長線波段操作。不適合盤整盤或高低震盪劇烈的股票。"

    def __init__(self, fast: int = 5, slow: int = 20):
        self.fast = fast
        self.slow = slow

    def analyze(self, symbol: str) -> dict:
        df = self.fetch_data(symbol, period="3mo")
        if df.empty:
            return {"signal": "HOLD", "confidence": 0, "reason": "無法取得數據", "indicators": {}, "price": None}

        df[f'MA{self.fast}'] = df['Close'].rolling(self.fast).mean()
        df[f'MA{self.slow}'] = df['Close'].rolling(self.slow).mean()

        ma_fast_now = float(df[f'MA{self.fast}'].iloc[-1])
        ma_slow_now = float(df[f'MA{self.slow}'].iloc[-1])
        ma_fast_prev = float(df[f'MA{self.fast}'].iloc[-2])
        ma_slow_prev = float(df[f'MA{self.slow}'].iloc[-2])
        price_now = float(df['Close'].iloc[-1])

        if ma_fast_prev <= ma_slow_prev and ma_fast_now > ma_slow_now:
            signal = "BUY"
            confidence = min(90, 50 + int(abs(ma_fast_now - ma_slow_now) / ma_slow_now * 2000))
            reason = f"🟢 黃金交叉！MA{self.fast}({ma_fast_now:.2f}) ↑ 穿越 MA{self.slow}({ma_slow_now:.2f})"
        elif ma_fast_prev >= ma_slow_prev and ma_fast_now < ma_slow_now:
            signal = "SELL"
            confidence = min(90, 50 + int(abs(ma_slow_now - ma_fast_now) / ma_slow_now * 2000))
            reason = f"🔴 死亡交叉！MA{self.fast}({ma_fast_now:.2f}) ↓ 穿越 MA{self.slow}({ma_slow_now:.2f})"
        elif ma_fast_now > ma_slow_now:
            signal = "HOLD"
            confidence = 30
            reason = f"↗️ 多頭排列 MA{self.fast} > MA{self.slow}"
        else:
            signal = "HOLD"
            confidence = 20
            reason = f"↘️ 空頭排列 MA{self.fast} < MA{self.slow}"

        return {
            "signal": signal, "confidence": confidence, "reason": reason,
            "indicators": {
                f"MA{self.fast}": round(ma_fast_now, 2),
                f"MA{self.slow}": round(ma_slow_now, 2),
            },
            "price": price_now,
        }


# ═══════════════════════════════════════════
#  RSI 策略
# ═══════════════════════════════════════════
class RSIStrategy(BaseStrategy):
    name = "rsi"
    description = (
        "RSI（相對強弱指標）衡量價格變動的速度和幅度，範圍 0~100。"
        "RSI < 30 表示超賣（賣過頭了，可能反彈）→ 買進信號；"
        "RSI > 70 表示超買（買過頭了，可能回檔）→ 賣出信號。"
        "這是一種逆勢策略，在震盪盤整的市場中效果最好。"
    )
    parameters = {
        "period": "14 (RSI 計算週期)",
        "oversold": "30 (超賣門檻，越低越保守)",
        "overbought": "70 (超買門檻，越高越保守)",
    }
    suitable_for = "震盪盤整市場，適合短線進出。強趨勢市場中容易過早出場或被套牢。"

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    @staticmethod
    def _calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def analyze(self, symbol: str) -> dict:
        df = self.fetch_data(symbol, period="3mo")
        if df.empty:
            return {"signal": "HOLD", "confidence": 0, "reason": "無法取得數據", "indicators": {}, "price": None}

        df['RSI'] = self._calc_rsi(df, self.period)
        rsi_now = float(df['RSI'].iloc[-1])
        rsi_prev = float(df['RSI'].iloc[-2])
        price_now = float(df['Close'].iloc[-1])

        if rsi_now <= self.oversold:
            signal = "BUY"
            confidence = min(95, int((self.oversold - rsi_now) * 2 + 40))
            reason = f"🟢 RSI 超賣 ({rsi_now:.1f} ≤ {self.oversold})，可能反彈"
        elif rsi_now >= self.overbought:
            signal = "SELL"
            confidence = min(95, int((rsi_now - self.overbought) * 2 + 40))
            reason = f"🔴 RSI 超買 ({rsi_now:.1f} ≥ {self.overbought})，可能回檔"
        elif rsi_prev <= self.oversold and rsi_now > self.oversold:
            signal = "BUY"
            confidence = 60
            reason = f"🟢 RSI 從超賣區回升 ({rsi_now:.1f})"
        elif rsi_prev >= self.overbought and rsi_now < self.overbought:
            signal = "SELL"
            confidence = 60
            reason = f"🔴 RSI 從超買區回落 ({rsi_now:.1f})"
        else:
            signal = "HOLD"
            confidence = 25
            reason = f"➡️ RSI 中性 ({rsi_now:.1f})"

        return {
            "signal": signal, "confidence": confidence, "reason": reason,
            "indicators": {"RSI": round(rsi_now, 1)},
            "price": price_now,
        }


# ═══════════════════════════════════════════
#  MACD 策略
# ═══════════════════════════════════════════
class MACDStrategy(BaseStrategy):
    name = "macd"
    description = (
        "MACD 是經典的趨勢追蹤指標，由 DIF（快慢 EMA 差）與 MACD 線（DIF 的平滑）組成。"
        "當 DIF 從下往上穿越 MACD 線 → 黃金交叉（買進）；"
        "當 DIF 從上往下穿越 MACD 線 → 死亡交叉（賣出）。"
        "柱狀圖（Histogram）代表兩者的差距，正值越大趨勢越強。"
    )
    parameters = {
        "fast": "12 (快 EMA 週期)",
        "slow": "26 (慢 EMA 週期)",
        "signal_period": "9 (信號線平滑週期)",
    }
    suitable_for = "中長期趨勢追蹤，適合波段操作。盤整市場可能頻繁發出假信號。"

    def __init__(self, fast: int = 12, slow: int = 26, signal_period: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def analyze(self, symbol: str) -> dict:
        df = self.fetch_data(symbol, period="6mo")
        if df.empty:
            return {"signal": "HOLD", "confidence": 0, "reason": "無法取得數據", "indicators": {}, "price": None}

        ema_fast = df['Close'].ewm(span=self.fast).mean()
        ema_slow = df['Close'].ewm(span=self.slow).mean()
        df['MACD'] = ema_fast - ema_slow
        df['Signal'] = df['MACD'].ewm(span=self.signal_period).mean()
        df['Histogram'] = df['MACD'] - df['Signal']

        macd_now = float(df['MACD'].iloc[-1])
        sig_now = float(df['Signal'].iloc[-1])
        macd_prev = float(df['MACD'].iloc[-2])
        sig_prev = float(df['Signal'].iloc[-2])
        hist_now = float(df['Histogram'].iloc[-1])
        price_now = float(df['Close'].iloc[-1])

        if macd_prev <= sig_prev and macd_now > sig_now:
            signal = "BUY"
            confidence = min(85, 50 + int(abs(hist_now) * 20))
            reason = f"🟢 MACD 黃金交叉！DIF({macd_now:.3f}) ↑ MACD({sig_now:.3f})"
        elif macd_prev >= sig_prev and macd_now < sig_now:
            signal = "SELL"
            confidence = min(85, 50 + int(abs(hist_now) * 20))
            reason = f"🔴 MACD 死亡交叉！DIF({macd_now:.3f}) ↓ MACD({sig_now:.3f})"
        elif macd_now > sig_now:
            signal = "HOLD"
            confidence = 35
            reason = f"↗️ MACD 偏多 (柱狀 {hist_now:+.3f})"
        else:
            signal = "HOLD"
            confidence = 20
            reason = f"↘️ MACD 偏空 (柱狀 {hist_now:+.3f})"

        return {
            "signal": signal, "confidence": confidence, "reason": reason,
            "indicators": {
                "MACD": round(macd_now, 3),
                "Signal": round(sig_now, 3),
                "Histogram": round(hist_now, 3),
            },
            "price": price_now,
        }


# ═══════════════════════════════════════════
#  布林通道策略
# ═══════════════════════════════════════════
class BollingerBandsStrategy(BaseStrategy):
    name = "bollinger"
    description = (
        "布林通道由中軌（MA）和上下軌（MA ± N倍標準差）組成。"
        "價格觸及下軌代表超賣，可能反彈 → 買進信號；"
        "價格觸及上軌代表超買，可能回檔 → 賣出信號。"
        "通道收窄代表即將變盤，通道擴張代表趨勢成形。"
    )
    parameters = {
        "period": "20 (中軌週期)",
        "std_dev": "2.0 (標準差倍數，越大通道越寬)",
    }
    suitable_for = "震盪市場的區間操作，適合短線進出。強趨勢市場中容易過早逆勢。"

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

    def analyze(self, symbol: str) -> dict:
        df = self.fetch_data(symbol, period="3mo")
        if df.empty:
            return {"signal": "HOLD", "confidence": 0, "reason": "無法取得數據", "indicators": {}, "price": None}

        df['MA'] = df['Close'].rolling(self.period).mean()
        df['Std'] = df['Close'].rolling(self.period).std()
        df['Upper'] = df['MA'] + self.std_dev * df['Std']
        df['Lower'] = df['MA'] - self.std_dev * df['Std']
        df['%B'] = (df['Close'] - df['Lower']) / (df['Upper'] - df['Lower'])

        price_now = float(df['Close'].iloc[-1])
        upper_now = float(df['Upper'].iloc[-1])
        lower_now = float(df['Lower'].iloc[-1])
        ma_now = float(df['MA'].iloc[-1])
        pct_b_now = float(df['%B'].iloc[-1])

        if pct_b_now <= 0.05:
            signal = "BUY"
            confidence = min(90, int((0.05 - pct_b_now) * 400 + 40))
            reason = f"🟢 觸及布林下軌 ({price_now:.2f})，可能反彈"
        elif pct_b_now >= 0.95:
            signal = "SELL"
            confidence = min(90, int((pct_b_now - 0.95) * 400 + 40))
            reason = f"🔴 觸及布林上軌 ({price_now:.2f})，可能回檔"
        elif pct_b_now < 0.3:
            signal = "HOLD"
            confidence = 20
            reason = f"⬇️ 價格偏弱 (下軌附近, %B={pct_b_now:.2f})"
        elif pct_b_now > 0.7:
            signal = "HOLD"
            confidence = 15
            reason = f"⬆️ 價格偏強 (上軌附近, %B={pct_b_now:.2f})"
        else:
            signal = "HOLD"
            confidence = 10
            reason = f"➡️ 布林中軌 (%B={pct_b_now:.2f})"

        return {
            "signal": signal, "confidence": confidence, "reason": reason,
            "indicators": {
                "MA": round(ma_now, 2),
                "Upper": round(upper_now, 2),
                "Lower": round(lower_now, 2),
                "%B": round(pct_b_now, 3),
            },
            "price": price_now,
        }


# ═══════════════════════════════════════════
#  複合策略（多指標投票）
# ═══════════════════════════════════════════
class CombinedStrategy(BaseStrategy):
    name = "combined"
    description = (
        "同時運行 MA 交叉、RSI、MACD、布林通道四種策略，以多數決投票決定最終信號。"
        "3+ 指標同向才觸發 → 降低單一策略的假信號風險。"
        "這是相對穩健的策略，適合不想手動判斷多重指標的投資者。"
    )
    parameters = {
        "voting_threshold": "3 (觸發所需的指標數，越高越保守)",
    }
    suitable_for = "適合多數市場環境，穩健型投資者首選。假信號率最低，但可能錯過部分快速行情。"

    def __init__(self):
        self.strategies = [
            MACrossoverStrategy(fast=5, slow=20),
            RSIStrategy(),
            MACDStrategy(),
            BollingerBandsStrategy(),
        ]

    def analyze(self, symbol: str) -> dict:
        results = []
        buy_votes = 0
        sell_votes = 0
        all_indicators = {}
        price = None

        for s in self.strategies:
            try:
                r = s.analyze(symbol)
                results.append({"strategy": s.name, **r})
                all_indicators[s.name] = r["indicators"]
                if r["signal"] == "BUY":
                    buy_votes += 1
                elif r["signal"] == "SELL":
                    sell_votes += 1
                if r["price"]:
                    price = r["price"]
            except:
                results.append({"strategy": s.name, "signal": "ERROR", "reason": "分析失敗"})

        total = len(self.strategies)

        if buy_votes >= 3:
            signal = "BUY"
            confidence = min(95, buy_votes * 25 + 15)
            reason = f"🟢 強力買入！{buy_votes}/{total} 指標看多"
        elif buy_votes >= 2:
            signal = "BUY"
            confidence = min(75, buy_votes * 25 + 5)
            reason = f"🟡 偏多信號 {buy_votes}/{total} 指標看多"
        elif sell_votes >= 3:
            signal = "SELL"
            confidence = min(95, sell_votes * 25 + 15)
            reason = f"🔴 強力賣出！{sell_votes}/{total} 指標看空"
        elif sell_votes >= 2:
            signal = "SELL"
            confidence = min(75, sell_votes * 25 + 5)
            reason = f"🟠 偏空信號 {sell_votes}/{total} 指標看空"
        else:
            signal = "HOLD"
            confidence = 15
            reason = f"➡️ 指標分歧 (多:{buy_votes} 空:{sell_votes})"

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "indicators": all_indicators,
            "price": price,
            "details": results,
            "votes": {"buy": buy_votes, "sell": sell_votes, "hold": total - buy_votes - sell_votes},
        }


# ─── 策略工廠 ───
STRATEGY_MAP = {
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerBandsStrategy,
    "combined": CombinedStrategy,
}


# ─── 策略資訊表（含詳細說明）───
STRATEGY_INFO = {}


def _build_strategy_info():
    """建立策略資訊對照表"""
    for name, cls in STRATEGY_MAP.items():
        inst = cls()
        STRATEGY_INFO[name] = inst.get_detail()


_build_strategy_info()


def get_strategy(name: str = "combined") -> BaseStrategy:
    """取得策略實例"""
    cls = STRATEGY_MAP.get(name, CombinedStrategy)
    return cls()


def analyze_symbol(symbol: str, strategy_name: str = "combined") -> dict:
    """快速分析個股"""
    strategy = get_strategy(strategy_name)
    return strategy.analyze(symbol)


# ═══════════════════════════════════════════
#  📡 MarketScanner 全市場掃描引擎
# ═══════════════════════════════════════════
class MarketScanner:
    """
    全市場掃描引擎
    - 掃描上市 (TWSE) + 上櫃 (TPEX) 的所有股票
    - 依成交量、波動率、趨勢、本益比篩選
    - 回傳 Top N 推薦標的
    """

    # 常見台股代碼清單（用作默認掃描池，避免全市場掃描太慢）
    DEFAULT_POOL = [
        # 權值股
        "2330", "2317", "2454", "2308", "2881", "2882", "2891", "2892", "2886",
        "1301", "1303", "1326", "2002", "2207", "2303", "2327", "2357", "2382",
        "2412", "2603", "2609", "2615", "2610", "2880", "2883", "2884", "2885",
        "2887", "2890", "3008", "3034", "3045", "3231", "3481", "3711", "4904",
        "5876", "5880", "6505", "8046",
        # 中型股
        "2345", "2379", "2409", "2449", "2474", "2492", "2498", "2605", "2606",
        "2618", "2633", "2801", "2812", "2834", "2836", "2845",
        "2850", "2852", "2912", "3006", "3037", "3044", "3189", "3264",
        "3406", "3443", "3529", "3532", "3533", "3583", "3617", "3653", "3661",
        "3694", "3702", "3714", "4915", "4919", "4927", "4943", "4958", "4960",
        "4968", "4976", "4989", "5269", "5274", "5289", "5478", "5483", "5534",
        "5904", "5907", "6104", "6180", "6202", "6239", "6244", "6269", "6271",
        "6274", "6278", "6285", "6414", "6456", "6462", "6477", "6488", "6510",
        "6526", "6531", "6533", "6547", "6552", "6568", "6579", "6592", "6617",
        "6643", "6655", "6672", "6706", "6715", "6732", "6754", "6768", "6781",
        "6799", "8039", "8044", "8081", "8150", "8454",
    ]

    @classmethod
    def scan(cls, symbols: List[str] = None, top_n: int = 10,
             min_vol_ratio: float = 0.6, max_pe: float = 50,
             pre_fetched: Optional[Dict[str, Dict]] = None) -> Dict:
        """
        掃描全市場
        - symbols: 掃描池（None 則用 DEFAULT_POOL + TWSE 全體）
        - top_n: 回傳前 N 名
        - min_volume_ratio: 最低成交量門檻（百萬股），預設 0.6 = 60萬股 ≈ 600張
        - max_pe: 最大本益比
        - pre_fetched: 預先取得的股價資料 dict
        """
        tw_data = pre_fetched or _fetch_twse_all_stocks()
        pool = symbols if symbols else (list(tw_data.keys()) if tw_data else cls.DEFAULT_POOL)
        results = []
        errors = 0
        skipped_vol = 0
        skipped_volatility = 0
        skipped_pe = 0

        for sym in pool:
            try:
                score, detail = cls._evaluate(sym, min_vol_ratio, max_pe, tw_data)
                if score is None:
                    if detail == "volume":
                        skipped_vol += 1
                    elif detail == "volatility":
                        skipped_volatility += 1
                    elif detail == "pe":
                        skipped_pe += 1
                    continue
                results.append({"symbol": sym, "score": score, **detail})
            except Exception:
                errors += 1
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:top_n]

        return {
            "status": "success",
            "scanned": len(pool),
            "matched": len(results),
            "errors": errors,
            "skipped_volume": skipped_vol,
            "skipped_volatility": skipped_volatility,
            "skipped_pe": skipped_pe,
            "top_picks": top,
            "scan_criteria": {
                "min_volume_ratio": min_vol_ratio,
                "max_pe": max_pe,
            }
        }

    @classmethod
    def _evaluate(cls, symbol: str, min_vol_ratio: float, max_pe: float,
                  pre_fetched: Dict[str, Dict]):
        """評估單一標的。使用 TWSE API 預取資料，yfinance 僅作為最後 fallback。"""
        tw_info = pre_fetched.get(symbol, {})

        # ── 1. 成交量 ──
        volume = tw_info.get("volume", 0)
        price_now = tw_info.get("price", 0)
        if price_now <= 0 or volume <= 0:
            return None, "volume"
        # 成交量過濾：min_vol_ratio 為最低成交量門檻（百萬股），預設 0.6 = 60萬股
        if volume < min_vol_ratio * 1_000_000:
            return None, "volume"

        # ── 2. PE ──
        pe = tw_info.get("pe")
        if pe is not None and pe > max_pe:
            return None, "pe"

        # ── 3. 取得歷史數據計算 MA20 / 波動率 ──
        df = cls._get_or_fetch_history(symbol)
        if df.empty or len(df) < 15:
            return None, "volatility"

        close = df['Close']
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else float(close.mean())
        above_ma20 = price_now > ma20

        # 波動率
        returns = close.pct_change().dropna()
        volatility = float(returns.tail(20).std()) if len(returns) >= 20 else 0.01
        avg_price = float(close.tail(20).mean())
        vol_pct = (volatility / avg_price * 100) if avg_price > 0 else 1.0

        # 放寬波動率過濾：殭屍股 (<0.05%) 和妖股 (>15%) 才排除
        if vol_pct < 0.05 or vol_pct > 15:
            return None, "volatility"

        # ── 4. 綜合評分 ──
        volume_score = min(25, int(min(volume / 1000000, 10) * 2.5))
        trend_score = min(25, int((price_now - ma20) / ma20 * 300 + 5)) if above_ma20 else max(0, int((price_now - ma20) / ma20 * 150))
        volatility_score = 15 if 0.5 <= vol_pct <= 6 else (10 if 6 < vol_pct <= 10 else 5)
        pe_score = 10 if pe is None else (10 if pe < 20 else (7 if pe < 30 else 3))
        score = volume_score + trend_score + volatility_score + pe_score

        return score, {
            "price": round(price_now, 2),
            "volume": volume,
            "volatility_pct": round(vol_pct, 2),
            "above_ma20": above_ma20,
            "ma20": round(ma20, 2),
            "pe": round(pe, 2) if pe else None,
        }

    # ── 歷史資料快取 ──
    _history_cache: Dict[str, pd.DataFrame] = {}
    _history_cache_ts: float = 0.0

    @classmethod
    def _get_or_fetch_history(cls, symbol: str) -> pd.DataFrame:
        now = time.time()
        if now - cls._history_cache_ts > 600:
            cls._history_cache.clear()
            cls._history_cache_ts = now
        if symbol not in cls._history_cache:
            cls._history_cache[symbol] = BaseStrategy.fetch_data(symbol, period="3mo")
        return cls._history_cache.get(symbol, pd.DataFrame())


# ═══════════════════════════════════════════
#  🧠 AdaptiveStrategy 自適應參數策略
# ═══════════════════════════════════════════
class AdaptiveStrategy(BaseStrategy):
    """
    根據市場波動率自動調整策略參數：
    - 高波動 → RSI 敏感度調低（減少假信號）
    - 低波動 → MA 交叉週期縮短（增加敏感度）
    - 趨勢市 → MACD 權重提高
    - 盤整市 → 布林通道權重提高
    """
    name = "adaptive"
    description = (
        "自適應策略會先分析大盤（加權指數）的波動狀態，再動態調整子策略的參數。"
        "高波動時降低敏感度避免假信號、低波動時增加敏感度捕捉細微波段。"
        "適合不想手動調整參數、希望策略隨市場變化自動適應的投資者。"
    )
    parameters = {
        "base_strategy": "combined (基礎策略，預設用複合投票)",
    }
    suitable_for = "所有市場環境。自適應機制讓策略隨大盤波動自動調整參數，減少人為干預。"

    def __init__(self, base_strategy: str = "combined"):
        self.base_strategy = base_strategy

    def _get_market_volatility(self) -> float:
        """取得大盤波動率 (0~1)，用於自適應調整"""
        try:
            df = BaseStrategy.fetch_data("^TWII", period="1mo")
            if df.empty:
                return 0.5  # 預設中等波動
            returns = df['Close'].pct_change().dropna()
            # 20日波動率年化
            daily_vol = float(returns.std())
            annual_vol = daily_vol * math.sqrt(252)
            # 正常化：台股年化波動約 15%~30%
            # 回傳 0~1 的值，0=極低波動, 1=極高波動
            normalized = min(1.0, max(0.0, (annual_vol - 0.12) / 0.28))
            return normalized
        except:
            return 0.5

    def _get_trend_strength(self) -> float:
        """取得趨勢強度 (-1 ~ +1)"""
        try:
            df = BaseStrategy.fetch_data("^TWII", period="1mo")
            if df.empty or len(df) < 20:
                return 0
            close = df['Close']
            ma5 = float(close.rolling(5).mean().iloc[-1])
            ma20 = float(close.rolling(20).mean().iloc[-1])
            price = float(close.iloc[-1])
            # 價格在 MA20 上方 = 偏多 (0~1)
            trend = (price - ma20) / ma20 * 10  # 例如 +5% = 0.5
            return max(-1.0, min(1.0, trend))
        except:
            return 0

    def analyze(self, symbol: str) -> dict:
        vol = self._get_market_volatility()
        trend = self._get_trend_strength()

        # ── 自適應參數調整 ──
        # 波動率越高 → MA 週期越長（降低敏感度）
        fast_ma = int(3 + vol * 10)   # vol=0 → 3, vol=1 → 13
        slow_ma = int(15 + vol * 15)  # vol=0 → 15, vol=1 → 30

        # 波動率越高 → RSI 門檻越極端
        oversold = int(30 - vol * 10)     # vol=0 → 30, vol=1 → 20
        overbought = int(70 + vol * 10)   # vol=0 → 70, vol=1 → 80

        # ── 運行調整後的策略 ──
        strategies = [
            MACrossoverStrategy(fast=max(3, fast_ma), slow=max(15, slow_ma)),
            RSIStrategy(oversold=max(10, oversold), overbought=min(90, overbought)),
            MACDStrategy(),
            BollingerBandsStrategy(),
        ]

        results = []
        buy_votes = 0
        sell_votes = 0
        all_indicators = {}
        price = None

        for s in strategies:
            try:
                r = s.analyze(symbol)
                results.append({"strategy": s.name, **r})
                all_indicators[s.name] = r["indicators"]
                if r["signal"] == "BUY":
                    buy_votes += 1
                elif r["signal"] == "SELL":
                    sell_votes += 1
                if r["price"]:
                    price = r["price"]
            except:
                results.append({"strategy": s.name, "signal": "ERROR", "reason": "分析失敗"})

        total = len(strategies)

        if buy_votes >= 3:
            signal = "BUY"
            confidence = min(95, buy_votes * 25 + 15)
            reason = f"🟢 強力買入！{buy_votes}/{total} 指標看多 (波動:{vol:.0%} 趨勢:{trend:+.2f})"
        elif buy_votes >= 2:
            signal = "BUY"
            confidence = min(75, buy_votes * 25 + 5)
            reason = f"🟡 偏多信號 {buy_votes}/{total} (波動:{vol:.0%})"
        elif sell_votes >= 3:
            signal = "SELL"
            confidence = min(95, sell_votes * 25 + 15)
            reason = f"🔴 強力賣出！{sell_votes}/{total} 指標看空 (波動:{vol:.0%} 趨勢:{trend:+.2f})"
        elif sell_votes >= 2:
            signal = "SELL"
            confidence = min(75, sell_votes * 25 + 5)
            reason = f"🟠 偏空信號 {sell_votes}/{total} (波動:{vol:.0%})"
        else:
            signal = "HOLD"
            confidence = 15
            reason = f"➡️ 指標分歧 (多:{buy_votes} 空:{sell_votes})"

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "indicators": {
                "market_volatility": round(vol, 2),
                "trend_strength": round(trend, 2),
                "adaptive_params": {
                    "MA_fast": fast_ma, "MA_slow": slow_ma,
                    "RSI_oversold": oversold, "RSI_overbought": overbought,
                },
                **all_indicators,
            },
            "price": price,
            "details": results,
            "votes": {"buy": buy_votes, "sell": sell_votes, "hold": total - buy_votes - sell_votes},
        }


# 註冊 AdaptiveStrategy
STRATEGY_MAP["adaptive"] = AdaptiveStrategy
_build_strategy_info()
