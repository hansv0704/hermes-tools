"""
投資代理人 v3.0 — 自主投資循環引擎
每 N 分鐘執行一次完整的 Scout→Analyze→Risk→Execute→Reflect 流程
"""
from __future__ import annotations
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from ..agents.orchestrator import (
        ScoutAgent, AnalystAgent, RiskAgent, ExecutorAgent, ReflectorAgent
    )
    from ..brokers.paper import PaperBroker
    from ..database import (
        get_mission, get_holdings, get_transactions,
        get_agent_state, set_loop_active, log_decision,
        update_mission_balance, complete_mission
    )
    from ..data.market_data import get_multiple_prices
    from ..config import MARKET_OPEN, MARKET_CLOSE
except ImportError:
    from agents.orchestrator import (
        ScoutAgent, AnalystAgent, RiskAgent, ExecutorAgent, ReflectorAgent
    )
    from brokers.paper import PaperBroker
    from database import (
        get_mission, get_holdings, get_transactions,
        get_agent_state, set_loop_active, log_decision,
        update_mission_balance, complete_mission
    )
    from data.market_data import get_multiple_prices
    from config import MARKET_OPEN, MARKET_CLOSE

log = logging.getLogger("investment.loop")


class AutonomousLoop:
    """自主投資循環引擎"""

    def __init__(self, mission_id: int):
        self.mission_id = mission_id
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.reflector = ReflectorAgent()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.cycle_count = 0

    @property
    def running(self) -> bool:
        return self._running

    async def start(self, interval_minutes: int = 15):
        """啟動自主循環"""
        if self._running:
            log.warning(f"Mission {self.mission_id} 循環已在運行")
            return

        self._running = True
        await set_loop_active(self.mission_id, True)
        self._task = asyncio.create_task(self._loop(interval_minutes))
        log.info(f"Mission {self.mission_id} 自主循環啟動 (每 {interval_minutes} 分鐘)")

    async def stop(self):
        """停止自主循環"""
        self._running = False
        await set_loop_active(self.mission_id, False)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info(f"Mission {self.mission_id} 自主循環已停止")

    async def _loop(self, interval_minutes: int):
        """主循環"""
        while self._running:
            try:
                await self._run_one_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"循環異常: {e}\n{traceback.format_exc()}")
                await log_decision(self.mission_id, "System", "error",
                                   f"循環異常: {str(e)[:200]}",
                                   {"error": str(e), "traceback": traceback.format_exc()[:500]})

            # 等待下一次循環
            await asyncio.sleep(interval_minutes * 60)

    async def _run_one_cycle(self) -> Optional[Dict]:
        """執行一個完整循環"""
        self.cycle_count += 1
        cycle_start = datetime.now()
        cn = self.cycle_count

        # 檢查是否在交易時間
        if not self._is_market_time() and cn > 1:
            log.debug(f"非交易時間，跳過循環 #{cn}")
            return None

        # 載入任務
        mission = await get_mission(self.mission_id)
        if not mission or mission["status"] != "active":
            log.warning(f"任務 {self.mission_id} 非活躍狀態，停止循環")
            await self.stop()
            return None

        risk_level = mission.get("risk_level", "moderate")
        risk_agent = RiskAgent(risk_level)
        executor = ExecutorAgent()
        broker = PaperBroker(self.mission_id)

        # ═══ Phase 1: Scout 掃描 ═══
        await log_decision(self.mission_id, "System", "cycle_start",
                           f"第 {cn} 次循環開始", {"cycle": cn})
        scan_result = await self.scout.scan(self.mission_id, cn)
        candidates = scan_result.get("candidates", [])

        # ═══ Phase 2: Analyst 分析 ═══
        symbols_to_analyze = [c["symbol"] for c in candidates[:12]]
        analyses = await self.analyst.batch_analyze(symbols_to_analyze, self.mission_id, cn)

        # ═══ Phase 3: Risk 評估 ═══
        account = await broker.get_account()
        positions = await broker.get_positions()

        # 更新持倉市價
        if positions:
            all_symbols = [p["symbol"] for p in positions]
            quotes = await get_multiple_prices(all_symbols)
            for p in positions:
                if p["symbol"] in quotes:
                    p["current_price"] = quotes[p["symbol"]].price
                    p["market_value"] = p["shares"] * p["current_price"]
                    p["pnl"] = p["market_value"] - (p["shares"] * p["avg_cost"])
                    p["pnl_pct"] = (p["pnl"] / (p["shares"] * p["avg_cost"]) * 100) if p["shares"] > 0 and p["avg_cost"] > 0 else 0

            # 更新 mission 資產
            mkt_val = sum(p.get("market_value", 0) for p in positions)
            total_asset = account.balance + mkt_val
            total_pnl = total_asset - mission["budget"]
            total_pnl_pct = (total_pnl / mission["budget"] * 100) if mission["budget"] > 0 else 0
            await update_mission_balance(self.mission_id, account.balance,
                                          round(total_asset, 2), round(total_pnl, 2),
                                          round(total_pnl_pct, 2))

        risk_result = await risk_agent.evaluate(
            analyses, positions,
            {"total_asset": account.total_asset, "balance": account.balance},
            self.mission_id, cn
        )

        # ═══ Phase 4: Execute 執行 ═══
        exec_result = await executor.execute(risk_result, broker, self.mission_id, cn)

        # ═══ Phase 5: Reflect 回顧（每5次循環） ═══
        if cn % 5 == 0:
            transactions = await get_transactions(self.mission_id, 50)
            reflect_result = await self.reflector.reflect(
                mission, transactions, self.mission_id, cn
            )

        # 檢查是否達標
        mission_check = await get_mission(self.mission_id)
        if mission_check and mission_check["total_asset"] >= mission_check["target_amount"]:
            await complete_mission(self.mission_id, "completed")
            await log_decision(self.mission_id, "System", "mission_complete",
                               f"🎯 任務達成！總資產 {mission_check['total_asset']:,.0f} >= 目標 {mission_check['target_amount']:,.0f}")

        cycle_time = (datetime.now() - cycle_start).total_seconds()
        await log_decision(self.mission_id, "System", "cycle_end",
                           f"第 {cn} 次循環完成 ({cycle_time:.1f}s): "
                           f"執行 {exec_result.get('total_trades', 0)} 筆交易",
                           {"cycle_time": cycle_time, "cycle": cn})

        return {
            "cycle": cn,
            "scan_candidates": len(candidates),
            "analyzed": len(analyses),
            "buy_candidates": len(risk_result.get("buy_candidates", [])),
            "trades": exec_result.get("total_trades", 0),
            "cycle_time": round(cycle_time, 1),
        }

    def _is_market_time(self) -> bool:
        """檢查是否在台股交易時間"""
        now = datetime.now()
        if now.weekday() >= 5:  # 週末
            return False
        current_minutes = now.hour * 60 + now.minute
        open_minutes = MARKET_OPEN[0] * 60 + MARKET_OPEN[1]
        close_minutes = MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1]
        return open_minutes <= current_minutes <= close_minutes


# ═══════════════════════════════════════════════
#  全局循環管理
# ═══════════════════════════════════════════════

_active_loops: Dict[int, AutonomousLoop] = {}

async def start_loop(mission_id: int, interval_minutes: int = 15):
    """啟動指定任務的自主循環"""
    if mission_id in _active_loops:
        await _active_loops[mission_id].stop()

    loop = AutonomousLoop(mission_id)
    _active_loops[mission_id] = loop
    await loop.start(interval_minutes)
    return loop

async def stop_loop(mission_id: int):
    """停止指定任務的自主循環"""
    if mission_id in _active_loops:
        await _active_loops[mission_id].stop()
        del _active_loops[mission_id]

async def get_loop_status(mission_id: int) -> Dict:
    """取得循環狀態"""
    if mission_id in _active_loops:
        loop = _active_loops[mission_id]
        return {
            "running": loop.running,
            "mission_id": mission_id,
            "cycle_count": loop.cycle_count,
        }
    state = await get_agent_state(mission_id)
    return {
        "running": bool(state["loop_active"]) if state else False,
        "mission_id": mission_id,
        "cycle_count": state["total_cycles"] if state else 0,
    }
