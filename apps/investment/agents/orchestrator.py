"""
投資代理人 v3.0 — 多Agent決策協調器

五個專業 Agent 協作：
  Scout    — 市場掃描，找出潛在標的
  Analyst  — 深度分析（基本面+技術面+題材）
  Risk     — 風險評估，部位計算
  Executor — 交易執行
  Reflector— 績效回顧，策略調整
"""
from __future__ import annotations
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

try:
    from ..data.market_data import (
        get_stock_price, get_multiple_prices, scan_market_top_movers,
        scan_market_gainers, compute_simple_indicators, get_tw_index
    )
    from ..data.news_scanner import scan_yahoo_tw_news, extract_themes_from_headlines, analyze_sentiment
    from ..engine.risk_manager import RiskManager
    from ..database import log_decision
    from ..config import MAX_POSITIONS
except ImportError:
    from data.market_data import (
        get_stock_price, get_multiple_prices, scan_market_top_movers,
        scan_market_gainers, compute_simple_indicators, get_tw_index
    )
    from data.news_scanner import scan_yahoo_tw_news, extract_themes_from_headlines, analyze_sentiment
    from engine.risk_manager import RiskManager
    from database import log_decision
    from config import MAX_POSITIONS

log = logging.getLogger("investment.agents")

# ═══════════════════════════════════════════════
#  Agent 基類
# ═══════════════════════════════════════════════

class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def log(self, mission_id: int, action: str, summary: str,
                  detail: Dict = None, cycle_num: int = 0):
        await log_decision(mission_id, self.role, action, summary, detail, cycle_num)

# ═══════════════════════════════════════════════
#  Scout Agent — 市場偵察員
# ═══════════════════════════════════════════════

class ScoutAgent(BaseAgent):
    """掃描市場，找出潛在投資機會"""

    def __init__(self):
        super().__init__("Scout", "Scout")

    async def scan(self, mission_id: int, cycle_num: int = 0) -> Dict:
        """執行市場掃描"""
        candidates = []
        reasons = []

        # 1. 大盤狀態
        tw_index = await get_tw_index()
        market_status = "neutral"
        if tw_index:
            if tw_index["change_pct"] > 1.5:
                market_status = "bullish"
                reasons.append(f"大盤強勢 +{tw_index['change_pct']}%")
            elif tw_index["change_pct"] < -1.5:
                market_status = "bearish"
                reasons.append(f"大盤弱勢 {tw_index['change_pct']}%")

        # 2. 漲幅排行
        gainers = await scan_market_gainers(15)
        for g in gainers[:8]:
            if g.change_pct > 2:
                indicators = await compute_simple_indicators(g.symbol)
                candidates.append({
                    "symbol": g.symbol, "name": g.name,
                    "price": g.price, "change_pct": g.change_pct,
                    "volume": g.volume,
                    "indicators": indicators,
                    "source": "漲幅排行",
                    "score": min(100, 50 + g.change_pct * 5),
                })

        # 3. 成交量活躍股
        movers = await scan_market_top_movers(15)
        existing_symbols = {c["symbol"] for c in candidates}
        for m in movers[:10]:
            if m.symbol not in existing_symbols and m.volume > 1000000:
                indicators = await compute_simple_indicators(m.symbol)
                candidates.append({
                    "symbol": m.symbol, "name": m.name,
                    "price": m.price, "change_pct": m.change_pct,
                    "volume": m.volume,
                    "indicators": indicators,
                    "source": "成交量活躍",
                    "score": min(100, 40 + (m.volume / 5000000) * 20),
                })

        # 4. 新聞題材
        try:
            news = await scan_yahoo_tw_news()
            headlines = [n["title"] for n in news]
            themes = await extract_themes_from_headlines(headlines)
            sentiment = await analyze_sentiment(headlines)

            if themes:
                theme_list = list(themes.keys())
                reasons.append(f"熱門題材: {', '.join(theme_list[:5])}")

            # 加入題材股
            for theme, symbols in themes.items():
                for sym in symbols[:3]:
                    if sym not in existing_symbols:
                        quote = await get_stock_price(sym)
                        if quote and quote.price > 0:
                            indicators = await compute_simple_indicators(sym)
                            candidates.append({
                                "symbol": sym, "name": quote.name,
                                "price": quote.price, "change_pct": quote.change_pct,
                                "volume": quote.volume,
                                "indicators": indicators,
                                "source": f"題材: {theme}",
                                "score": 55,
                            })
                            existing_symbols.add(sym)
        except Exception as e:
            log.warning(f"新聞掃描異常: {e}")

        # 排序: 分數優先，但也要考慮流動性
        candidates.sort(key=lambda x: (x["score"], x.get("volume", 0)), reverse=True)

        result = {
            "market_status": market_status,
            "tw_index": tw_index,
            "candidates": candidates[:15],
            "scan_reasons": reasons,
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        await self.log(mission_id, "scan_complete",
                       f"掃描完成，找到 {len(candidates)} 個候選標的，市場狀態: {market_status}",
                       result, cycle_num)

        return result

# ═══════════════════════════════════════════════
#  Analyst Agent — 深度分析師
# ═══════════════════════════════════════════════

class AnalystAgent(BaseAgent):
    """對候選標的進行深度分析"""

    def __init__(self):
        super().__init__("Analyst", "Analyst")

    async def analyze(self, symbol: str, mission_id: int = 0,
                      cycle_num: int = 0) -> Optional[Dict]:
        """分析單一標的"""
        quote = await get_stock_price(symbol)
        if not quote or quote.price <= 0:
            return None

        indicators = await compute_simple_indicators(symbol)

        # 評分系統 (0-100)
        score = 50
        signals = []

        if indicators:
            # 趨勢信號
            if indicators.get("trend") == "bullish":
                score += 15
                signals.append("✅ 多頭排列 (MA5>MA10>MA20)")
            else:
                score -= 10
                signals.append("⚠️ 偏空排列")

            # RSI
            rsi = indicators.get("rsi14", 50)
            if 30 <= rsi <= 70:
                signals.append(f"📊 RSI {rsi} 中性區間")
            elif rsi < 30:
                score += 10
                signals.append(f"📉 RSI {rsi} 超賣(潛在反彈)")
            elif rsi > 70:
                score -= 10
                signals.append(f"📈 RSI {rsi} 超買(注意回檔)")

            # MACD
            macd = indicators.get("macd", 0)
            if macd > 0:
                score += 5
                signals.append(f"📈 MACD 正 {macd}")
            else:
                signals.append(f"📉 MACD 負 {macd}")

            # 成交量
            vol_ratio = indicators.get("vol_ratio", 1)
            if vol_ratio > 2:
                score += 10
                signals.append(f"🔥 爆量 {vol_ratio}x")
            elif vol_ratio < 0.5:
                signals.append(f"💤 量縮 {vol_ratio}x")

        # 動能
        if quote.change_pct > 3:
            score += 8
            signals.append(f"🚀 強勢 +{quote.change_pct}%")
        elif quote.change_pct < -3:
            score += 5  # 跌深可能有反彈
            signals.append(f"📉 弱勢 {quote.change_pct}%")

        score = max(0, min(100, score))

        result = {
            "symbol": symbol,
            "name": quote.name,
            "price": quote.price,
            "change_pct": quote.change_pct,
            "score": score,
            "signals": signals,
            "indicators": indicators,
            "verdict": "BUY" if score >= 60 else ("HOLD" if score >= 40 else "PASS"),
        }

        await self.log(mission_id, f"analyze_{symbol}",
                       f"分析 {symbol} {quote.name}: 評分 {score} → {result['verdict']}",
                       result, cycle_num)

        return result

    async def batch_analyze(self, symbols: List[str], mission_id: int = 0,
                            cycle_num: int = 0) -> List[Dict]:
        """批次分析多個標的"""
        tasks = [self.analyze(s, mission_id, cycle_num) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r]
        valid.sort(key=lambda x: x["score"], reverse=True)
        return valid

# ═══════════════════════════════════════════════
#  Risk Agent — 風險評估員
# ═══════════════════════════════════════════════

class RiskAgent(BaseAgent):
    """風險評估、部位計算、停損停利"""

    def __init__(self, risk_level: str = "moderate"):
        super().__init__("Risk", "Risk")
        self.manager = RiskManager(risk_level)

    async def evaluate(self, candidates: List[Dict], current_positions: List[Dict],
                       account: Dict, mission_id: int = 0,
                       cycle_num: int = 0) -> Dict:
        """風險綜合評估"""
        total_asset = account.get("total_asset", 0)
        balance = account.get("balance", 0)
        available = self.manager.available_cash(total_asset, balance)

        # 檢查現有部位風險
        stop_alerts = self.manager.check_stop_conditions(current_positions)

        # 篩選可買標的
        can_add = self.manager.can_add_position(len(current_positions))
        buy_candidates = []

        if can_add and available > 10000:
            for c in candidates[:10]:
                if c.get("verdict") != "BUY":
                    continue
                if c["symbol"] in [p["symbol"] for p in current_positions]:
                    continue

                # 計算部位大小（台股以 1000 股為單位）
                position_size = self.manager.calculate_position_size(
                    total_asset,
                    confidence=c.get("score", 50) / 100,
                )
                price = c["price"]
                raw_shares = int(position_size / price)
                # 向下取整張，若不足一張但資金夠就買一張
                lots = raw_shares // 1000
                if lots == 0 and available >= price * 1000:
                    lots = 1
                shares = lots * 1000

                if shares >= 1000 and shares * price <= available:
                    buy_candidates.append({
                        **c,
                        "suggested_shares": shares,
                        "suggested_amount": round(price * shares, 2),
                        "risk_note": f"投入 {shares*price:,.0f} ({shares*price/total_asset*100:.1f}%)",
                    })

        result = {
            "stop_alerts": stop_alerts,
            "can_add_position": can_add,
            "available_cash": round(available, 2),
            "max_positions": self.manager.profile["max_positions"],
            "current_positions_count": len(current_positions),
            "buy_candidates": buy_candidates[:5],
        }

        await self.log(mission_id, "risk_evaluate",
                       f"風險評估: 可用 {available:,.0f}, 部位 {len(current_positions)}/{self.manager.profile['max_positions']}, "
                       f"買進候選 {len(buy_candidates)}, 停損觸發 {len(stop_alerts)}",
                       result, cycle_num)

        return result

# ═══════════════════════════════════════════════
#  Executor Agent — 交易執行員
# ═══════════════════════════════════════════════

class ExecutorAgent(BaseAgent):
    """執行交易決策"""

    def __init__(self):
        super().__init__("Executor", "Executor")

    async def execute(self, risk_result: Dict, broker, mission_id: int,
                      cycle_num: int = 0) -> Dict:
        """執行交易"""
        trades = []
        errors = []

        # 1. 先處理停損停利
        for alert in risk_result.get("stop_alerts", []):
            pos = next((p for p in await broker.get_positions()
                       if p["symbol"] == alert["symbol"]), None)
            if pos and pos["shares"] > 0:
                result = await broker.place_order(
                    symbol=alert["symbol"],
                    side="SELL",
                    shares=pos["shares"],
                    order_type="M",
                    reason=f"{alert['action']}: {alert['reason']}"
                )
                if result.success:
                    trades.append(result)
                    await self.log(mission_id, f"{alert['action']}_{alert['symbol']}",
                                   f"{alert['action']}: {alert['symbol']} {pos['shares']}股 | {alert['reason']}",
                                   {"result": result.__dict__}, cycle_num)
                else:
                    errors.append(str(result))

        # 2. 買進候選標的（一次最多買1檔，避免過度交易）
        for candidate in risk_result.get("buy_candidates", [])[:1]:
            result = await broker.place_order(
                symbol=candidate["symbol"],
                side="BUY",
                shares=candidate["suggested_shares"],
                order_type="M",
                reason=f"多Agent推薦: 評分{candidate['score']}, {candidate.get('source','')}"
            )
            if result.success:
                trades.append(result)
                await self.log(mission_id, f"BUY_{candidate['symbol']}",
                               f"買進: {candidate['symbol']} {candidate['suggested_shares']}股 @ {candidate['price']} "
                               f"| 評分{candidate['score']} | {candidate.get('source','')}",
                               result.__dict__, cycle_num)
            else:
                errors.append(str(result))

        exec_result = {
            "trades": [t.__dict__ for t in trades],
            "errors": errors,
            "total_trades": len(trades),
            "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        await self.log(mission_id, "execute_complete",
                       f"執行完成: {len(trades)} 筆交易, {len(errors)} 個錯誤",
                       exec_result, cycle_num)

        return exec_result

# ═══════════════════════════════════════════════
#  Reflector Agent — 績效回顧
# ═══════════════════════════════════════════════

class ReflectorAgent(BaseAgent):
    """回顧歷史決策，調整策略參數"""

    def __init__(self):
        super().__init__("Reflector", "Reflector")

    async def reflect(self, mission: Dict, transactions: List[Dict],
                      mission_id: int = 0, cycle_num: int = 0) -> Dict:
        """績效回顧與策略反思"""
        if not transactions:
            return {"verdict": "尚未有交易記錄"}

        total_trades = len(transactions)
        sell_trades = [t for t in transactions if t.get("side") == "SELL"]
        buy_trades = [t for t in transactions if t.get("side") == "BUY"]

        # 交易盈虧分析
        profitable = 0
        losing = 0
        for t in sell_trades:
            # 配對買賣（簡化）
            buy = next((b for b in buy_trades if b["symbol"] == t["symbol"]), None)
            if buy and t.get("total_amount", 0) > buy.get("total_amount", 0):
                profitable += 1
            else:
                losing += 1

        total_sells = profitable + losing
        win_rate = (profitable / total_sells * 100) if total_sells > 0 else 0

        # 策略建議
        suggestions = []
        if total_sells > 0 and win_rate < 40:
            suggestions.append("⚠️ 勝率偏低，建議降低單筆投入比例")
        if len(buy_trades) > len(sell_trades) * 2:
            suggestions.append("⚠️ 買入遠多於賣出，建議適時停利")

        pnl_pct = mission.get("start_pnl_pct", 0)
        if pnl_pct > 10:
            suggestions.append("✅ 績效優異，維持現有策略")
        elif pnl_pct < -5:
            suggestions.append("🔴 虧損擴大，建議縮減部位並檢討選股邏輯")

        # 週轉率
        total_bought = sum(t.get("total_amount", 0) for t in buy_trades)
        budget = mission.get("budget", 0)
        turnover = (total_bought / budget) if budget > 0 else 0

        result = {
            "total_trades": total_trades,
            "profitable_trades": profitable,
            "losing_trades": losing,
            "win_rate": round(win_rate, 1),
            "turnover_rate": round(turnover, 2),
            "suggestions": suggestions,
            "pnl_pct": round(pnl_pct, 2),
        }

        await self.log(mission_id, "reflect",
                       f"績效回顧: 勝率 {win_rate:.0f}%, 交易 {total_trades} 筆, "
                       f"損益 {pnl_pct:+.1f}%",
                       result, cycle_num)

        return result
