"""
Mission Executor — AI 自主決策迴路 v1.0
Phase 2 核心：將 Mission (任務目標) 轉化為持續的 AI 自主投資循環。

架構：
  execute_cycle(mission_id)
    ├─ 1. 讀取 mission 參數 + 計算時間壓力
    ├─ 2. 調用 AutonomousInvestmentAgent.run_mission_aware()
    ├─ 3. 取得當前持倉，計算調倉需求
    ├─ 4. 透過 PaperTradingEngine 執行交易
    ├─ 5. 更新 mission 進度
    └─ 6. 產生 Telegram 格式回報

設計原則：
  - 所有交易透過 PaperTradingEngine（紙上交易）
  - 決策參數由 mission 的風險等級、時間壓力動態調整
  - 每次循環產出完整可稽核的執行報告
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import json
import math


class MissionExecutor:
    """AI 自主決策迴路 — Mission 驅動的投資執行器"""

    def __init__(self, agent=None):
        self.agent = agent  # Alice agent 實例（選填，用於 Telegram 回報）
        self.log: List[Dict] = []
        self.last_cycle: Optional[datetime] = None
        self.cycle_count: int = 0

    # ═══════════════════════════════════════════
    #  主循環：execute_cycle
    # ═══════════════════════════════════════════

    def execute_cycle(self, mission_id: Optional[int] = None,
                       mode: str = "paper") -> Dict:
        """
        執行一個完整的投資決策循環（P1-2: 全步驟例外防護）。

        Args:
            mission_id: 任務 ID（None = 最新活躍任務）
            mode: 交易模式 "paper"（紙上）或 "live"（實盤 Mega SpeedyAPI）

        回傳格式：
        {
            "status": "success" | "error" | "partial",
            "mission": {...},
            "time_pressure": float,
            "strategy_adjustments": {...},
            "plan": {...},
            "trades_executed": [...],
            "report": str (Telegram 格式),
            "errors": [...],
        }
        """
        from paper_trading_engine import paper_engine, mission_tracker
        from live_trading_engine import live_engine, get_live_engine
        from autonomous_investment_agent import AutonomousInvestmentAgent, get_agent
        from mission_parser import MissionParser, MissionParams

        self.cycle_count += 1
        cycle_start = datetime.now()
        self._log("cycle_start", f"第 {self.cycle_count} 次循環開始")
        errors: List[str] = []

        # ── Step 1: 讀取 mission ──
        mission = None
        try:
            mission_result = paper_engine.get_mission_progress(mission_id)
            if mission_result.get("status") != "success":
                return {"status": "error", "message": mission_result.get("message", "找不到活躍任務")}
            mission = mission_result["mission"]
            self._log("mission_loaded", f"任務 #{mission['id']}: {mission['description']}")
        except Exception as e:
            errors.append(f"Step1_mission_load: {e}")
            return {"status": "error", "message": f"讀取任務失敗: {e}", "errors": errors}

        # ── Step 2: 計算時間壓力 ──
        time_pressure = 1.0
        try:
            time_pressure = self._calc_time_pressure(mission)
            self._log("pressure_calc", f"時間壓力: {time_pressure:.2f}")
        except Exception as e:
            errors.append(f"Step2_pressure: {e}")
            time_pressure = 1.0
            self._log("pressure_fallback", f"時間壓力計算失敗，使用預設值 1.0: {e}")

        # ── Step 3: 動態調整策略參數 ──
        adjustments = {}
        try:
            adjustments = self._calc_strategy_adjustments(mission, time_pressure)
            self._log("strategy_adjusted", f"風險調整: {adjustments}")
        except Exception as e:
            errors.append(f"Step3_adjustments: {e}")
            adjustments = {"strategy_name": "combined", "max_positions": 5,
                           "stop_loss_pct": 5.0, "take_profit_pct": 15.0,
                           "risk_level": "medium", "time_pressure": time_pressure}
            self._log("strategy_fallback", f"策略調整失敗，使用預設值: {e}")

        # ── Step 4: 執行投資代理人掃描 ──
        plan = None
        try:
            invest_agent = get_agent()
            invest_agent.reset_agent()
            providers = self._build_providers()

            p1 = invest_agent.phase1_discover_themes(
                search_news_fn=providers.get("search_news"),
                extra_prompts=self._build_search_queries(mission, adjustments),
            )

            p2 = invest_agent.phase2_screen_candidates(
                fetch_stock_info_fn=providers.get("fetch_stock_info"),
                fetch_stock_price_fn=providers.get("fetch_stock_price"),
                min_market_cap_billion=adjustments.get("min_market_cap_billion", 0.5),
                max_pe=adjustments.get("max_pe", 60),
            )

            p3 = invest_agent.phase3_technical_review(
                analyze_fn=providers.get("analyze_symbol"),
                strategy_name=adjustments.get("strategy_name", "combined"),
            )

            p4 = invest_agent.phase4_generate_plan(
                budget=paper_engine.get_account()["total_assets"],
            )

            plan = p4.get("plan") if p4.get("status") == "success" else None
            self._log("plan_generated", f"投資計畫: {'✅' if plan else '❌'}")
        except Exception as e:
            errors.append(f"Step4_agent_scan: {e}")
            self._log("plan_failed", f"投資代理人掃描失敗: {e}")

        # ── Step 5: 調倉決策 ──
        trades = []
        try:
            trading_engine = self._get_trading_engine(mode)
            if plan:
                positions = trading_engine.get_positions()
                account = trading_engine.get_account()
                trades = self._rebalance(
                    plan=plan, positions=positions, account=account,
                    mission=mission, adjustments=adjustments,
                    trading_engine=trading_engine, mode=mode,
                )
        except Exception as e:
            errors.append(f"Step5_rebalance: {e}")
            self._log("rebalance_failed", f"調倉失敗: {e}")

        # ── Step 6: 評估進度 ──
        eval_result = {}
        try:
            eval_result = mission_tracker.evaluate(mission["id"])
        except Exception as e:
            errors.append(f"Step6_evaluate: {e}")
            eval_result = {"status": "error", "message": str(e)}

        # ── Step 7: 產生回報 ──
        report = ""
        try:
            report = self._generate_report(
                mission=mission, time_pressure=time_pressure,
                adjustments=adjustments, plan=plan, trades=trades,
                evaluation=eval_result, cycle_start=cycle_start, mode=mode,
            )
        except Exception as e:
            errors.append(f"Step7_report: {e}")
            report = f"⚠️ 回報產生失敗: {e}"

        self.last_cycle = cycle_start
        status = "partial" if errors else "success"
        self._log("cycle_complete", f"完成，{len(trades)} 筆交易，{len(errors)} 個錯誤")

        return {
            "status": status,
            "mission": mission,
            "time_pressure": round(time_pressure, 2),
            "strategy_adjustments": adjustments,
            "plan": plan,
            "trades_executed": trades,
            "evaluation": eval_result,
            "report": report,
            "cycle_count": self.cycle_count,
            "errors": errors,
        }

    # ═══════════════════════════════════════════
    #  時間壓力計算
    # ═══════════════════════════════════════════

    @staticmethod
    def _calc_time_pressure(mission: Dict) -> float:
        """
        時間壓力 = (已過天數 / 總期限) / max(目前進度%, 1%)
        壓力 > 1.0 → 進度落後，需要更激進的策略
        壓力 < 0.5 → 進度超前，可以收斂風險
        """
        total_days = max(1, mission.get("timeframe_days", 90))
        elapsed = max(1, mission.get("elapsed_days", 0))
        progress_pct = max(1.0, mission.get("progress_pct", 0))

        # 時間消耗率 vs 進度達成率
        time_ratio = elapsed / total_days
        progress_ratio = progress_pct / 100.0

        # 壓力 = 時間消耗 / 進度達成（越大越落後）
        pressure = time_ratio / max(progress_ratio, 0.01)
        return round(min(pressure, 10.0), 2)

    # ═══════════════════════════════════════════
    #  動態策略調整
    # ═══════════════════════════════════════════

    @staticmethod
    def _calc_strategy_adjustments(mission: Dict, time_pressure: float) -> Dict:
        """
        根據時間壓力和風險等級動態調整策略參數。

        調整項目：
        - strategy_name: 技術分析策略 (combined/adaptive/ma_crossover)
        - min_market_cap_billion: 最小市值門檻
        - max_pe: 最大本益比
        - position_concentration: 集中度 (持股數)
        - stop_loss_pct: 停損百分比
        - take_profit_pct: 停利百分比
        - max_positions: 最大持股數
        """
        risk = mission.get("risk_level", "medium")
        base_max_positions = mission.get("max_positions", 5)

        # 基礎參數（依風險等級）
        risk_profiles = {
            "extreme": {
                "strategy_name": "combined",
                "min_market_cap_billion": 0.1,
                "max_pe": 100,
                "stop_loss_mult": 1.5,
                "take_profit_mult": 2.0,
            },
            "high": {
                "strategy_name": "combined",
                "min_market_cap_billion": 0.3,
                "max_pe": 60,
                "stop_loss_mult": 1.0,
                "take_profit_mult": 1.5,
            },
            "medium": {
                "strategy_name": "adaptive",
                "min_market_cap_billion": 1.0,
                "max_pe": 40,
                "stop_loss_mult": 0.7,
                "take_profit_mult": 1.0,
            },
            "low": {
                "strategy_name": "ma_crossover",
                "min_market_cap_billion": 3.0,
                "max_pe": 25,
                "stop_loss_mult": 0.5,
                "take_profit_mult": 0.7,
            },
        }
        profile = risk_profiles.get(risk, risk_profiles["medium"])

        # 時間壓力動態乘數
        if time_pressure > 3.0:
            # 嚴重落後 → 極端激進
            pressure_mult = 2.0
            strategy = "combined"
            max_positions = max(2, base_max_positions // 2)
        elif time_pressure > 1.5:
            # 落後 → 較激進
            pressure_mult = 1.5
            strategy = "combined"
            max_positions = max(3, int(base_max_positions * 0.7))
        elif time_pressure > 1.0:
            # 略落後 → 微調
            pressure_mult = 1.2
            strategy = profile["strategy_name"]
            max_positions = base_max_positions
        elif time_pressure < 0.3:
            # 大幅超前 → 收斂
            pressure_mult = 0.5
            strategy = "ma_crossover"
            max_positions = min(10, base_max_positions + 3)
        elif time_pressure < 0.6:
            # 超前 → 稍微保守
            pressure_mult = 0.7
            strategy = "adaptive"
            max_positions = min(8, base_max_positions + 2)
        else:
            pressure_mult = 1.0
            strategy = profile["strategy_name"]
            max_positions = base_max_positions

        return {
            "strategy_name": strategy,
            "min_market_cap_billion": round(profile["min_market_cap_billion"] / pressure_mult, 2),
            "max_pe": round(profile["max_pe"] * pressure_mult),
            "stop_loss_pct": round(mission.get("stop_loss_pct", 0.05) * profile["stop_loss_mult"] * pressure_mult * 100, 1),
            "take_profit_pct": round(mission.get("take_profit_pct", 0.15) * profile["take_profit_mult"] * pressure_mult * 100, 1),
            "max_positions": max_positions,
            "time_pressure": time_pressure,
            "risk_level": risk,
        }

    # ═══════════════════════════════════════════
    #  交易時間檢查 (P2-4)
    # ═══════════════════════════════════════════

    @staticmethod
    def _is_market_open() -> tuple:
        """檢查台股是否在交易時間內。回傳 (bool, str)"""
        now = datetime.now()
        weekday = now.weekday()  # 0=Mon, 6=Sun
        hour = now.hour
        minute = now.minute

        if weekday >= 5:
            return False, "週末休市"

        # 台股 09:00-13:30
        if hour < 9:
            return False, "尚未開盤 (台股 09:00-13:30)"
        if hour > 13 or (hour == 13 and minute > 30):
            return False, "已收盤 (台股 09:00-13:30)"

        return True, "交易中"

    # ═══════════════════════════════════════════
    #  搜尋查詢建構
    # ═══════════════════════════════════════════

    @staticmethod
    def _build_search_queries(mission: Dict, adjustments: Dict) -> List[str]:
        """根據 mission 建構題材搜尋查詢"""
        market = mission.get("preferred_market", "TW")
        risk = mission.get("risk_level", "medium")

        queries = []

        if market in ("TW", "ALL"):
            queries.extend([
                "2026 台股 熱門題材 強勢股 趨勢",
                "2026 台灣股市 AI 半導體 利多 產業輪動",
            ])

        if market in ("US", "ALL"):
            queries.extend([
                "2026 US stock market hot sectors trends",
                "2026 Nasdaq AI semiconductor growth stocks",
            ])

        # 高風險：加入更激進的搜尋
        if risk in ("high", "extreme"):
            queries.append("2026 飆股 強勢突破 短線 籌碼集中")

        return queries

    # ═══════════════════════════════════════════
    #  Data Providers
    # ═══════════════════════════════════════════

    def _build_providers(self) -> Dict[str, Callable]:
        """建立 data_providers dict，橋接到 Alice 工具（P1-6: 健壯 import）"""
        providers = {}

        # ── search_news ──
        def _search_news(query: str) -> List[Dict]:
            try:
                # P1-6: 多路徑嘗試 import web_search_tool
                web_search_tool = None
                for import_path in [
                    "tools.web_search_tool",
                    "web_search_tool",
                ]:
                    try:
                        mod = __import__(import_path, fromlist=["web_search_tool"])
                        web_search_tool = getattr(mod, "web_search_tool", None)
                        if web_search_tool:
                            break
                    except (ImportError, AttributeError):
                        continue

                if web_search_tool is None:
                    return []

                results = web_search_tool(query, max_results=5)
                if isinstance(results, list):
                    return [{"title": r.get("title", ""), "snippet": r.get("snippet", ""),
                             "summary": r.get("snippet", "")} for r in results]
                return []
            except Exception:
                return []

        providers["search_news"] = _search_news

        # ── fetch_stock_info ──
        def _fetch_stock_info(symbol: str) -> Dict:
            try:
                import yfinance as yf
                if symbol.isdigit():
                    for suffix in ['.TW', '.TWO']:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        info = t.info
                        if info.get('longName'):
                            return {
                                "symbol": symbol,
                                "name": info.get('longName') or info.get('shortName', symbol),
                                "market_cap": info.get('marketCap'),
                                "pe_ratio": info.get('trailingPE') or info.get('forwardPE'),
                                "sector": info.get('sector', ''),
                                "industry": info.get('industry', ''),
                            }
                else:
                    t = yf.Ticker(symbol)
                    info = t.info
                    return {
                        "symbol": symbol,
                        "name": info.get('longName') or info.get('shortName', symbol),
                        "market_cap": info.get('marketCap'),
                        "pe_ratio": info.get('trailingPE') or info.get('forwardPE'),
                        "sector": info.get('sector', ''),
                        "industry": info.get('industry', ''),
                    }
            except Exception:
                pass
            return {"symbol": symbol, "name": symbol}

        providers["fetch_stock_info"] = _fetch_stock_info

        # ── fetch_stock_price ──
        def _fetch_stock_price(symbol: str) -> Optional[float]:
            try:
                import yfinance as yf
                if symbol.isdigit():
                    for suffix in ['.TW', '.TWO']:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        p = t.fast_info.get('last_price')
                        if p:
                            return float(p)
                else:
                    t = yf.Ticker(symbol)
                    p = t.fast_info.get('last_price')
                    if p:
                        return float(p)
            except Exception:
                pass
            return None

        providers["fetch_stock_price"] = _fetch_stock_price

        # ── analyze_symbol ──
        def _analyze_symbol(symbol: str, strategy_name: str = "combined") -> Dict:
            try:
                # P1-6: 多路徑嘗試 import strategy_engine
                engine = None
                for import_path in [
                    "strategy_engine.get_strategy_engine",
                ]:
                    try:
                        parts = import_path.rsplit(".", 1)
                        mod = __import__(parts[0], fromlist=[parts[1]])
                        factory = getattr(mod, parts[1], None)
                        if factory:
                            engine = factory()
                            break
                    except (ImportError, AttributeError):
                        continue

                if engine is None:
                    return {"signal": "HOLD", "confidence": 0, "reason": "策略引擎不可用", "indicators": {}}

                import yfinance as yf
                if symbol.isdigit():
                    ticker = yf.Ticker(f"{symbol}.TW")
                else:
                    ticker = yf.Ticker(symbol)
                hist = ticker.history(period="3mo")
                if hist.empty:
                    return {"signal": "HOLD", "confidence": 0, "reason": "無歷史數據", "indicators": {}}

                result = engine.analyze(symbol, hist, strategy=strategy_name)
                if result:
                    return {
                        "signal": result.get("signal", "HOLD"),
                        "confidence": result.get("confidence", 50),
                        "reason": result.get("reason", ""),
                        "indicators": result.get("indicators", {}),
                        "price": float(hist['Close'].iloc[-1]) if not hist.empty else None,
                    }
            except Exception as e:
                return {"signal": "HOLD", "confidence": 0, "reason": str(e), "indicators": {}}

            return {"signal": "HOLD", "confidence": 0, "reason": "無法分析", "indicators": {}}

        providers["analyze_symbol"] = _analyze_symbol

        # ── call_llm（橋接 autonomous_loop.LLMClient → DeepSeek API）──
        def _call_llm(system_prompt: str, user_prompt: str, model: str = "flash") -> str:
            try:
                from autonomous_loop import LLMClient
                llm = LLMClient()
                use_pro = (model == "pro")
                response = llm.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4 if use_pro else 0.7,
                    max_tokens=2048 if use_pro else 1024,
                    use_pro=use_pro,
                )
                return response
            except Exception as e:
                raise RuntimeError(f"LLM 調用失敗: {e}")

        providers["call_llm"] = _call_llm

        return providers

    # ═══════════════════════════════════════════
    #  交易引擎路由
    # ═══════════════════════════════════════════

    @staticmethod
    def _get_trading_engine(mode: str = "paper"):
        """依模式返回紙上或實盤交易引擎"""
        if mode == "live":
            from live_trading_engine import live_engine
            return live_engine
        else:
            from paper_trading_engine import paper_engine
            return paper_engine

    # ═══════════════════════════════════════════
    #  調倉決策
    # ═══════════════════════════════════════════

    def _rebalance(
        self,
        plan: Dict,
        positions: List[Dict],
        account: Dict,
        mission: Dict,
        adjustments: Dict,
        trading_engine,
        mode: str = "paper",
    ) -> List[Dict]:
        """
        根據投資計畫和當前持倉進行調倉。

        決策邏輯：
        1. 取得計畫中的目標持股清單
        2. 對比當前持倉
        3. 賣出不在計畫中的持股
        4. 買入計畫中的新股（在資金和部位上限內）
        5. 調整既有持股數量

        Args:
            mode: "paper" 或 "live"，影響實際執行的引擎
        """
        trades = []
        max_positions = adjustments.get("max_positions", mission.get("max_positions", 5))
        stop_loss_pct = mission.get("stop_loss_pct", 0.05)
        take_profit_pct = mission.get("take_profit_pct", 0.15)

        # ── 實盤模式安全檢查 ──
        if mode == "live":
            from live_trading_engine import live_engine
            if not live_engine.is_live:
                return [{
                    "action": "error_live_not_ready",
                    "symbol": "N/A",
                    "shares": 0,
                    "result": {
                        "status": "error",
                        "message": "🔴 實盤模式未就緒：請先用 /login_mega 登入兆豐，並確認 /trade_mode live",
                    }
                }]
            # 實盤需雙重確認：engine 是 live_engine 且 _mode == "live"
            if trading_engine is not live_engine:
                return [{
                    "action": "error_engine_mismatch",
                    "symbol": "N/A",
                    "shares": 0,
                    "result": {
                        "status": "error",
                        "message": "🔴 引擎路由錯誤：mode=live 但 trading_engine 非 live_engine",
                    }
                }]

        # 收集計畫所有 picks
        target_symbols: Dict[str, Dict] = {}
        for horizon in ("short_term", "mid_term", "long_term"):
            for pick in plan.get(horizon, {}).get("picks", []):
                sym = pick["symbol"]
                if sym not in target_symbols:
                    target_symbols[sym] = pick
                else:
                    # 合併不同期間的同一標的
                    target_symbols[sym]["shares"] = target_symbols[sym].get("shares", 0) + pick.get("shares", 0)

        current_symbols = {p["symbol"]: p for p in positions}
        cash = account.get("balance", 0) if isinstance(account, dict) else 0

        # ── Step 1: 檢查現有持倉的停損停利 ──
        for sym, pos in list(current_symbols.items()):
            pnl_pct = pos.get("pnl_pct", 0)
            if pnl_pct <= -stop_loss_pct * 100:
                # 觸發停損
                price = pos.get("price") or pos.get("avg_cost", 0)
                if price > 0:
                    result = trading_engine.sell(
                        sym, pos["shares"], price,
                        strategy="mission_stop_loss",
                        note=f"停損: {pnl_pct:.2f}%"
                    )
                    trades.append({"action": "sell_stop_loss", "symbol": sym, "shares": pos["shares"], "result": result})
                    # P3-1: 賣出後更新 cash
                    if result.get("status") in ("success", "partial"):
                        proceeds = result.get("net_proceeds", 0)
                        if proceeds > 0:
                            cash += proceeds
                    del current_symbols[sym]
            elif pnl_pct >= take_profit_pct * 100 and take_profit_pct > 0:
                # 觸發停利
                price = pos.get("price") or pos.get("avg_cost", 0)
                if price > 0:
                    result = trading_engine.sell(
                        sym, pos["shares"], price,
                        strategy="mission_take_profit",
                        note=f"停利: +{pnl_pct:.2f}%"
                    )
                    trades.append({"action": "sell_take_profit", "symbol": sym, "shares": pos["shares"], "result": result})
                    # P3-1: 賣出後更新 cash
                    if result.get("status") in ("success", "partial"):
                        proceeds = result.get("net_proceeds", 0)
                        if proceeds > 0:
                            cash += proceeds
                    del current_symbols[sym]

        # ── Step 2: 賣出不在計畫中的持股 ──
        for sym, pos in list(current_symbols.items()):
            if sym not in target_symbols:
                price = pos.get("price") or pos.get("avg_cost", 0)
                if price > 0:
                    result = trading_engine.sell(
                        sym, pos["shares"], price,
                        strategy="mission_rebalance",
                        note="不在目標計畫中"
                    )
                    trades.append({"action": "sell_rebalance", "symbol": sym, "shares": pos["shares"], "result": result})
                    # P3-1: 賣出後更新 cash
                    if result.get("status") in ("success", "partial"):
                        proceeds = result.get("net_proceeds", 0)
                        if proceeds > 0:
                            cash += proceeds
                    del current_symbols[sym]

        # ── Step 3: 買入計畫中的新股 ──
        # P2-4: 實盤模式檢查交易時間
        if mode == "live":
            is_open, market_msg = self._is_market_open()
            if not is_open:
                trades.append({"action": "market_closed", "symbol": "N/A", "shares": 0,
                               "result": {"status": "info", "message": f"🕐 {market_msg}，跳過自動買入"}})
                return trades

        current_count = len(current_symbols)
        # P2-2: 實盤模式取得 live_engine 持倉做最終校驗
        live_held_symbols = {}
        if mode == "live":
            try:
                live_positions = trading_engine.get_positions()
                live_held_symbols = {p["symbol"]: p for p in live_positions}
            except Exception:
                pass

        # 一次性取得最新帳戶資訊（後續迴圈內用 buy 回傳的 new_balance 遞減）
        account = trading_engine.get_account()
        cash = account.get("balance", 0) if isinstance(account, dict) else 0

        # P1-4: 實盤模式下若 cash 為 0 或無法取得，嘗試從 live_engine 重新查詢
        if mode == "live" and cash <= 0:
            try:
                from live_trading_engine import live_engine as _le
                live_acc = _le.get_account()
                cash = live_acc.get("balance", 0)
                if cash <= 0:
                    # 標記資金來源，仍繼續嘗試（可能有庫存但無現金屬於正常）
                    self._log("live_cash_warning",
                              f"實盤可用資金 ${cash:.0f}（來源: {live_acc.get('balance_source', 'unknown')}），"
                              f"{live_acc.get('note', '')}")
            except Exception as e:
                self._log("live_cash_error", f"查詢實盤資金失敗: {e}")

        # 僅在完全無法取得資金資訊時跳過買入
        if mode == "live" and cash <= 0:
            trades.append({"action": "skip_buy", "symbol": "N/A", "shares": 0,
                           "result": {"status": "info",
                                      "message": "實盤模式可用資金為 0，跳過自動買入（若剛入金請先更新帳戶）"}})
            return trades

        # 依優先序（短 > 中 > 長）買入
        buy_candidates = []
        for horizon in ("short_term", "mid_term", "long_term"):
            for pick in plan.get(horizon, {}).get("picks", []):
                sym = pick["symbol"]
                if sym not in current_symbols and sym not in [b["symbol"] for b in buy_candidates]:
                    # P2-2: 實盤最終校驗
                    if mode == "live" and sym in live_held_symbols:
                        trades.append({"action": "skip_duplicate", "symbol": sym, "shares": 0,
                                       "result": {"status": "info",
                                                  "message": f"{sym} 已在實盤持有 {live_held_symbols[sym].get('shares', '?')} 股，跳過重複買入"}})
                        continue
                    buy_candidates.append(pick)

        slots_available = max_positions - current_count
        for pick in buy_candidates[:slots_available]:
            sym = pick["symbol"]
            price = pick.get("price")
            shares = pick.get("shares", 0)

            if not price or price <= 0 or shares <= 0:
                continue

            total_cost = shares * price * 1.003  # 含手續費
            if total_cost > cash:
                # 根據可用資金調整股數
                affordable_shares = int(cash / (price * 1.003) / 100) * 100
                if affordable_shares < 100:
                    affordable_shares = int(cash / (price * 1.003))
                if affordable_shares <= 0:
                    continue
                shares = affordable_shares

            result = trading_engine.buy(
                sym, shares, price,
                name=pick.get("name", sym),
                strategy=f"mission_{adjustments.get('risk_level', 'medium')}"
            )

            # P2-1: 全狀態處理（success/partial/pending/error 皆記錄）
            status = result.get("status", "error")
            trade_entry = {"action": "buy", "symbol": sym, "shares": shares, "price": price, "result": result}

            if status == "success":
                trades.append(trade_entry)
                # 用回傳的 new_balance 遞減 cash（紙上模式有效；實盤為 None 則保守設 0）
                cash = result.get("new_balance") if result.get("new_balance") is not None else max(0, cash - total_cost)
                current_count += 1
            elif status in ("partial", "pending"):
                trade_entry["action"] = f"buy_{status}"
                trades.append(trade_entry)
                # partial/pending 仍保守扣 cash 避免超買
                cash = max(0, cash - total_cost)
            else:
                trade_entry["action"] = "buy_error"
                trades.append(trade_entry)

        return trades

    # ═══════════════════════════════════════════
    #  回報產生
    # ═══════════════════════════════════════════

    def _generate_report(
        self,
        mission: Dict,
        time_pressure: float,
        adjustments: Dict,
        plan: Optional[Dict],
        trades: List[Dict],
        evaluation: Dict,
        cycle_start: datetime,
        mode: str = "paper",
    ) -> str:
        """產生 Telegram 格式的執行回報"""

        # 壓力指示器
        if time_pressure > 3.0:
            pressure_emoji = "🔴🔴🔴"
            pressure_label = "極度高壓"
        elif time_pressure > 1.5:
            pressure_emoji = "🟠🟠"
            pressure_label = "高度壓力"
        elif time_pressure > 1.0:
            pressure_emoji = "🟡"
            pressure_label = "輕微壓力"
        elif time_pressure > 0.5:
            pressure_emoji = "🟢"
            pressure_label = "正常"
        else:
            pressure_emoji = "💚"
            pressure_label = "大幅超前"

        lines = [
            f"🤖 **AI 自主決策迴路 — 第 {self.cycle_count} 次循環**",
            f"⏰ {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}",
            f"🔧 模式: {'🟢 實盤 (Mega)' if mode == 'live' else '📝 紙上模擬'}",
            f"",
            f"🎯 **任務 #{mission['id']}**",
            f"📝 {mission['description'][:60]}...",
            f"",
            f"📊 **狀態**",
            f"• 進度: {mission['progress_pct']:.1f}%",
            f"• 報酬: {mission['current_return_pct']:+.2f}% / 目標 {mission['target_return_pct']:+.2f}%",
            f"• 剩餘: {mission['remaining_days']} 天 / {mission['timeframe_days']} 天",
            f"• {pressure_emoji} 時間壓力: **{pressure_label}** ({time_pressure:.1f}x)",
            f"",
            f"⚙️ **策略調整**",
            f"• 策略: `{adjustments.get('strategy_name', 'N/A')}`",
            f"• 最大持股: {adjustments.get('max_positions', 'N/A')} 檔",
            f"• 停損/停利: -{adjustments.get('stop_loss_pct', 'N/A')}% / +{adjustments.get('take_profit_pct', 'N/A')}%",
        ]

        # 投資計畫摘要
        if plan:
            lines.append(f"")
            lines.append(f"📋 **投資計畫**")
            for horizon in ("short_term", "mid_term", "long_term"):
                section = plan.get(horizon, {})
                picks = section.get("picks", [])
                if picks:
                    symbols = ", ".join(p["symbol"] for p in picks[:3])
                    budget = section.get("budget", 0)
                    lines.append(f"• {horizon}: {symbols} (${budget:,.0f})")

        # 交易摘要
        if trades:
            lines.append(f"")
            lines.append(f"💹 **本次交易** ({len(trades)} 筆)")
            for t in trades:
                action = t["action"]
                sym = t["symbol"]
                shares = t.get("shares", 0)
                result = t.get("result", {})
                status = result.get("status", "?")
                emoji = "✅" if status == "success" else "❌"
                if "buy" in action:
                    lines.append(f"• {emoji} 📈 買入 {sym} {shares}股")
                else:
                    lines.append(f"• {emoji} 📉 賣出 {sym} {shares}股 ({action})")
        else:
            lines.append(f"")
            lines.append(f"💤 本次無交易")

        # 評估
        eval_data = evaluation.get("evaluation", {}) if evaluation.get("status") == "success" else {}
        if eval_data:
            status_label = eval_data.get("status", "on_track")
            status_map = {"completed": "🎉 已達成", "on_track": "✅ 進度正常", "slightly_behind": "⏳ 略落後", "lagging": "📉 落後", "behind": "⚠️ 嚴重落後"}
            lines.append(f"")
            lines.append(f"📊 **評估**: {status_map.get(status_label, status_label)}")

            for alert in eval_data.get("alerts", []):
                lines.append(f"• {alert}")

        # 進度條
        progress_bar = self._make_progress_bar(mission["progress_pct"])
        lines.append(f"")
        lines.append(f"{progress_bar} {mission['progress_pct']:.1f}%")

        return "\n".join(lines)

    @staticmethod
    def _make_progress_bar(pct: float, width: int = 20) -> str:
        filled = int(pct / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    # ═══════════════════════════════════════════
    #  輔助
    # ═══════════════════════════════════════════

    def _log(self, event: str, detail: str):
        self.log.append({
            "event": event,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })

    def get_log(self, limit: int = 50) -> List[Dict]:
        return self.log[-limit:]


# 全域單例
_mission_executor: Optional[MissionExecutor] = None


def get_executor() -> MissionExecutor:
    global _mission_executor
    if _mission_executor is None:
        _mission_executor = MissionExecutor()
    return _mission_executor
