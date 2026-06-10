from base_skill import BaseSkill
from config import logger
from typing import Optional, Dict, Any
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


class TaiwanMarketSkill(BaseSkill):
    """台灣股市數據接口 — 移植自 FinceptTerminal taiwan_market_connector"""

    @property
    def name(self) -> str:
        return "taiwan_market_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "get_tw_stock_history",
                "description": "取得台股個股歷史 OHLCV 數據。支援上市公司 (TWSE) 與上櫃公司 (TPEX)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代碼，如 '2330', '6180'"
                        },
                        "start": {
                            "type": "string",
                            "description": "起始日期 YYYY-MM-DD，預設 30 天前"
                        },
                        "end": {
                            "type": "string",
                            "description": "結束日期 YYYY-MM-DD，預設今天"
                        },
                        "market": {
                            "type": "string",
                            "description": "市場別：'TWSE' (上市) 或 'TPEX' (上櫃)，預設自動判斷"
                        },
                        "interval": {
                            "type": "string",
                            "description": "K 線週期：1d, 1wk, 1mo，預設 1d"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_tw_stock_info",
                "description": "取得台股個股基本資訊（市值、本益比、股利、產業等）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代碼，如 '2330'"
                        },
                        "market": {
                            "type": "string",
                            "description": "市場別：'TWSE' 或 'TPEX'，預設自動判斷"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_tw_index",
                "description": "取得台股指數歷史數據（加權指數、櫃買指數、台灣50）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "index": {
                            "type": "string",
                            "description": (
                                "指數代碼：'TAIEX' (加權指數), "
                                "'TPEX' (櫃買指數), "
                                "'TAIWAN50' (台灣50)。預設 TAIEX"
                            )
                        },
                        "period": {
                            "type": "string",
                            "description": "查詢期間：1mo, 3mo, 6mo, 1y, 5y，預設 1mo"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_tw_market_overview",
                "description": "取得台股市場總覽：加權指數、櫃買指數即時行情",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_tw_top_movers",
                "description": "取得台股漲幅/跌幅/成交量前 N 名個股（需 TWSE API 支援）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "top_n": {
                            "type": "integer",
                            "description": "回傳前 N 名，預設 10"
                        },
                        "move_type": {
                            "type": "string",
                            "description": (
                                "類型：'gainers' (漲幅), "
                                "'losers' (跌幅), "
                                "'volume' (成交量)。預設 gainers"
                            )
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "search_tw_stocks",
                "description": "搜尋台股股票（依名稱或代碼）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜尋關鍵字，如 '台積電' 或 '2330'"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    # ═══════════════════════════════════════════
    #  輔助方法
    # ═══════════════════════════════════════════

    def _resolve_symbol(self, symbol: str, market: str = None) -> str:
        """解析台股代碼為 Yahoo Finance 格式"""
        symbol = symbol.strip().upper()
        if symbol.endswith(".TW") or symbol.endswith(".TWO"):
            return symbol
        if market and market.upper() == "TPEX":
            return f"{symbol}.TWO"
        return f"{symbol}.TW"

    def _resolve_index(self, index: str) -> str:
        """解析指數代碼 → Yahoo Finance symbol"""
        mapping = {
            "TAIEX": "^TWII",
            "TPEX": "^TWOII",
            "TAIWAN50": "0050.TW",
        }
        return mapping.get(index.upper(), "^TWII")

    # ═══════════════════════════════════════════
    #  BaseSkill 介面
    # ═══════════════════════════════════════════

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        handlers = {
            "get_tw_stock_history": self._get_stock_history,
            "get_tw_stock_info": self._get_stock_info,
            "get_tw_index": self._get_index,
            "get_tw_market_overview": self._get_market_overview,
            "get_tw_top_movers": self._get_top_movers,
            "search_tw_stocks": self._search_stocks,
        }
        handler = handlers.get(function_name)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                logger.error(f"[TaiwanMarket] {function_name} 失敗: {e}")
                return {"error": str(e)}
        return {"error": f"Unknown function: {function_name}"}

    # ═══════════════════════════════════════════
    #  工具實作
    # ═══════════════════════════════════════════

    def _get_stock_history(self, args: dict) -> dict:
        symbol = args["symbol"]
        start = args.get(
            "start",
            (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        )
        end = args.get("end", datetime.now().strftime("%Y-%m-%d"))
        market = args.get("market")
        interval = args.get("interval", "1d")

        ticker_str = self._resolve_symbol(symbol, market)
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(start=start, end=end, interval=interval)

        if df.empty:
            return {"error": f"無法取得 {symbol} 的歷史數據，請確認代碼是否正確"}

        # 技術指標
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()

        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
                "ma5": round(row["MA5"], 2) if pd.notna(row["MA5"]) else None,
                "ma20": round(row["MA20"], 2) if pd.notna(row["MA20"]) else None,
            })

        latest = records[-1] if records else {}
        prev = records[-2] if len(records) > 1 else {}
        change = round(latest.get("close", 0) - prev.get("close", 0), 2) if prev else 0
        change_pct = round(change / prev["close"] * 100, 2) if prev.get("close") else 0

        return {
            "symbol": symbol,
            "market": "TWSE" if ticker_str.endswith(".TW") else "TPEX",
            "interval": interval,
            "data_points": len(records),
            "latest": latest,
            "change": change,
            "change_pct": change_pct,
            "history": records[-90:],
        }

    def _get_stock_info(self, args: dict) -> dict:
        symbol = args["symbol"]
        market = args.get("market")
        ticker_str = self._resolve_symbol(symbol, market)
        ticker = yf.Ticker(ticker_str)
        info = ticker.info

        if not info or not info.get("longName"):
            return {"error": f"無法取得 {symbol} 的基本資訊"}

        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName", ""),
            "market": info.get("market", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose"),
            "open": info.get("open"),
            "day_high": info.get("dayHigh"),
            "day_low": info.get("dayLow"),
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "description": (info.get("longBusinessSummary") or "")[:500],
        }

    def _get_index(self, args: dict) -> dict:
        index = args.get("index", "TAIEX")
        period = args.get("period", "1mo")

        period_map = {
            "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
            "1y": "1y", "5y": "5y",
        }
        yf_period = period_map.get(period, "1mo")

        ticker_str = self._resolve_index(index)
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period=yf_period)

        if df.empty:
            return {"error": f"無法取得 {index} 指數數據"}

        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        latest = records[-1] if records else {}
        prev = records[-2] if len(records) > 1 else {}
        change = round(latest.get("close", 0) - prev.get("close", 0), 2) if prev else 0
        change_pct = round(change / prev["close"] * 100, 2) if prev.get("close") else 0

        return {
            "index": index,
            "period": period,
            "data_points": len(records),
            "latest": latest,
            "change": change,
            "change_pct": change_pct,
            "history": records,
        }

    def _get_market_overview(self, args: dict) -> dict:
        """同時查詢加權指數與櫃買指數"""
        result = {}

        for name, sym in [("taiex", "^TWII"), ("tpex", "^TWOII")]:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period="1d")
                if not df.empty:
                    row = df.iloc[-1]
                    result[name] = {
                        "value": round(row["Close"], 2),
                        "open": round(row["Open"], 2),
                        "high": round(row["High"], 2),
                        "low": round(row["Low"], 2),
                        "volume": int(row["Volume"]),
                    }
            except Exception as e:
                result[name] = {"error": str(e)}

        result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return result

    def _get_top_movers(self, args: dict) -> dict:
        top_n = args.get("top_n", 10)
        move_type = args.get("move_type", "gainers")

        return {
            "message": (
                "⚠️ yfinance 不支援台股即時漲幅排行。"
                "此功能需要 TWSE/TPEX 網頁爬蟲或第三方 API。"
                "已列入後續開發計畫，目前可改用 get_tw_stock_history 查看個股走勢。"
            ),
            "move_type": move_type,
            "top_n": top_n,
            "note": "P2 待辦：整合 TWSE OpenAPI 即時掃描",
        }

    def _search_stocks(self, args: dict) -> dict:
        query = args["query"]

        # 嘗試上市
        try:
            ticker = yf.Ticker(f"{query}.TW")
            info = ticker.info
            if info and info.get("longName"):
                return {
                    "results": [{
                        "symbol": query,
                        "name": info.get("longName"),
                        "market": info.get("market", "TWSE"),
                        "sector": info.get("sector", ""),
                        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    }]
                }
        except Exception:
            pass

        # 嘗試上櫃
        try:
            ticker = yf.Ticker(f"{query}.TWO")
            info = ticker.info
            if info and info.get("longName"):
                return {
                    "results": [{
                        "symbol": query,
                        "name": info.get("longName"),
                        "market": "TPEX",
                        "sector": info.get("sector", ""),
                        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    }]
                }
        except Exception:
            pass

        return {"results": [], "message": f"找不到符合 '{query}' 的台股"}
