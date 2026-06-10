"""
24/7 AI 自主投資循環 Autonomous Loop v1.0
─────────────────────────────────────────
架構：
  循環週期（預設 60 分鐘）：
    1. 新聞監控 → 抓取即時財經新聞
    2. 題材變化分析 → LLM 分析新聞中的新題材
    3. 持倉風險評估 → 比對現有持倉與市場變化
    4. 策略調整建議 → LLM 產出調整方案
    5. Telegram 推播 → 重要事件通知主人

  AI 策略討論 Chat：
    - 基於 DeepSeek API 的對話式投資顧問
    - 上下文包含：持倉、新聞、歷史對話

依賴：
  - openai (DeepSeek API)
  - yfinance (新聞 + 報價)
  - feedparser (RSS 新聞)
  - AutonomousInvestmentAgent (Phase 1-4 研究)
  - paper_trading_engine (持倉管理)
"""
from __future__ import annotations
import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable

import yfinance as yf
import requests
from ai_trading_toolkit import get_toolkit

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
#  LLM 客戶端 (DeepSeek)
# ═══════════════════════════════════════════════

class LLMClient:
    """DeepSeek API 客戶端 — 雙模型架構（Flash + Pro）

    Flash (deepseek-chat):    快速、低成本，用於日常分析與代理人辯論
    Pro (deepseek-reasoner):  深度思辨，用於辯論整合與最終決策
    """

    FLASH_MODEL = "deepseek-chat"
    PRO_MODEL = "deepseek-reasoner"

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 2048, use_pro: bool = False) -> str:
        """發送對話請求

        Args:
            messages: 對話訊息清單
            temperature: 創意度 (0~1)
            max_tokens: 最大輸出 token 數
            use_pro: True=使用 Pro 模型做深度思辨, False=使用 Flash 模型
        """
        if not self.api_key:
            return "[LLM 未設定 API Key]"

        model = self.PRO_MODEL if use_pro else self.FLASH_MODEL

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120 if use_pro else 60,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                log.error(f"LLM API error ({model}): {resp.status_code} {resp.text[:200]}")
                return f"[LLM 錯誤: {resp.status_code}]"
        except Exception as e:
            log.error(f"LLM 請求失敗 ({model}): {e}")
            return f"[LLM 連線失敗: {e}]"


# ═══════════════════════════════════════════════
#  多代理人辯論引擎 (DebateEngine)
#  借鏡 TradingAgents (81k⭐) 的 Bull/Bear/Analyst → Trader 架構
# ═══════════════════════════════════════════════

class DebateEngine:
    """三代理人辯論引擎 — Phase 1 題材發現核心

    流程：
      1. Bull (多方) / Bear (空方) / Analyst (分析師) → 各自用 Flash 分析
      2. Trader (交易員) → 用 Pro 整合三方觀點，產出最終決策

    設計原則：
      - Flash 用於快速生成多方視角（低成本）
      - Pro 用於深度整合與最終決策（高品質）
      - 每個代理人有獨立系統提示，確保視角多元
    """

    BULL_SYSTEM = """你是一位台股「多方」分析師，代號 Bull。
你的任務是：從新聞和持倉中找出所有「看多/買進/持有」的理由。

分析框架：
1. 哪些新聞/題材對持倉或潛在標的有利？
2. 市場情緒是否轉向樂觀？有什麼證據？
3. 哪些產業或個股有上漲催化劑？
4. 目前持倉中哪些應該加碼？為什麼？

⚠️ 重要：你只負責看多！不要提及任何負面因素。
回覆時請以條列式呈現，每點不超過 2 行。總長度控制在 200 字內。"""

    BEAR_SYSTEM = """你是一位台股「空方」分析師，代號 Bear。
你的任務是：從新聞和持倉中找出所有「看空/賣出/減持」的理由。

分析框架：
1. 哪些新聞/題材對持倉或市場有潛在風險？
2. 市場情緒是否過熱？有什麼警訊？
3. 哪些產業或個股有利空消息或估值過高？
4. 目前持倉中哪些應該減碼或清倉？為什麼？

⚠️ 重要：你只負責看空！不要提及任何正面因素。
回覆時請以條列式呈現，每點不超過 2 行。總長度控制在 200 字內。"""

    ANALYST_SYSTEM = """你是一位中立「技術分析師」，代號 Analyst。
你的任務是：從數據面客觀分析市場狀態，不偏多也不偏空。

分析框架：
1. 從新聞中提取客觀數據（漲跌幅度、成交量變化、資金流向）
2. 目前市場處於什麼階段？（盤整/趨勢/反轉）
3. 有哪些被新聞忽略但數據顯示的訊號？
4. 提供 2-3 個需要關注的關鍵數據指標

回覆時請以條列式呈現，每點不超過 2 行。總長度控制在 200 字內。"""

    TRADER_SYSTEM = """你是一位資深台股交易員，代號 Trader。
你收到 Bull、Bear、Analyst 三位分析師的觀點後，需要整合做出最終決策。

你的任務：
1. 綜合三方觀點，判斷市場真實方向
2. 評估 Bull 和 Bear 誰的論點更有說服力
3. 結合 Analyst 的數據驗證
4. 產出結構化 JSON 決策

⚠️ 重要：
- 只回覆 JSON，不要有任何其他文字
- 不要重複三方觀點，而是做出判斷
- trigger_full_research 應在出現重大題材變化、市場轉向時設為 true
- adjustment_needed 應在現有持倉需要因應新聞調整時設為 true"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.debate_history: List[Dict] = []  # 最近 N 次辯論摘要

    def debate(self, news_text: str, portfolio_context: str) -> Dict:
        """執行完整三代理人辯論 + Trader 整合

        Args:
            news_text: 最新新聞摘要
            portfolio_context: 持倉上下文

        Returns:
            結構化分析結果 (與原 _llm_analyze 格式相容)
        """
        # ── Step 1: 三代理人各自用 Flash 分析 ──
        context = f"""【最新財經新聞】
{news_text}

【持倉狀態】
{portfolio_context}"""

        bull_view = self._query_agent("Bull", self.BULL_SYSTEM, context)
        bear_view = self._query_agent("Bear", self.BEAR_SYSTEM, context)
        analyst_view = self._query_agent("Analyst", self.ANALYST_SYSTEM, context)

        # ── Step 2: Trader 用 Pro 整合三方觀點 ──
        final = self._trader_integrate(
            bull_view, bear_view, analyst_view,
            news_text, portfolio_context
        )

        # ── Step 3: 記錄辯論歷史 ──
        self.debate_history.append({
            "timestamp": datetime.now().isoformat(),
            "bull": bull_view[:150],
            "bear": bear_view[:150],
            "analyst": analyst_view[:150],
            "result": json.dumps(final, ensure_ascii=False)[:300],
        })
        if len(self.debate_history) > 8:
            self.debate_history = self.debate_history[-8:]

        return final

    def _query_agent(self, agent_name: str, system_prompt: str, context: str) -> str:
        """查詢單一代理人（Flash）"""
        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
                temperature=0.4,
                max_tokens=512,
                use_pro=False,  # Flash
            )
            log.info(f"🤖 {agent_name} 分析完成 ({len(response)} chars)")
            return response.strip()
        except Exception as e:
            log.error(f"{agent_name} 查詢失敗: {e}")
            return f"[{agent_name} 分析失敗: {e}]"

    def _trader_integrate(self, bull: str, bear: str, analyst: str,
                           news_text: str, portfolio_context: str) -> Dict:
        """Trader 用 Pro 整合三方觀點，產出最終決策"""
        # ── 建立最近辯論歷史摘要 ──
        history_text = ""
        if len(self.debate_history) >= 1:
            recent = self.debate_history[-3:]  # 最多取 3 輪
            history_text = "【近幾輪辯論摘要（避免重複判斷）】\n"
            for i, h in enumerate(recent):
                history_text += f"第{i+1}輪: 結果={h.get('result', '')[:120]}\n"

        prompt = f"""{history_text}
【Bull (多方) 觀點】
{bull}

【Bear (空方) 觀點】
{bear}

【Analyst (中立) 觀點】
{analyst}

【原始新聞摘要】
{news_text[:500]}

【持倉狀態】
{portfolio_context[:500]}

【決策要求】
請回覆一個 JSON 物件，整合三方觀點後做出判斷：

{{
  "market_sentiment": "bullish/neutral/bearish",
  "sentiment_reason": "綜合三方觀點後的市場情緒判斷理由（40字內）",
  "emerging_themes": ["題材1", "題材2"],
  "themes_declining": ["退燒題材1"],
  "trigger_full_research": true/false,
  "research_reason": "觸發完整研究的原因（如需觸發，30字內）",
  "adjustment_needed": true/false,
  "adjustment_suggestions": [
    {{
      "symbol": "股票代號",
      "action": "BUY/SELL/HOLD/REDUCE",
      "reason": "整合三方後的調整理由（20字內）",
      "urgency": "high/medium/low"
    }}
  ],
  "debate_quality": "Bull/Bear 哪方論點較強，以及 Analyst 的數據支持度（30字內）",
  "risk_alerts": ["風險提示1"],
  "summary": "綜合分析摘要（100字內）"
}}

【注意】只回覆 JSON，不要有其他文字。"""

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.TRADER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1536,
                use_pro=True,  # Pro 深度思辨
            )

            # 解析 JSON
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            result = json.loads(json_str)
            log.info(f"🎯 Trader 整合完成: sentiment={result.get('market_sentiment')}, "
                     f"debate_quality={result.get('debate_quality', 'N/A')}")
            return result

        except json.JSONDecodeError as e:
            log.warning(f"Trader JSON 解析失敗: {e}, raw={response[:300]}")
            return self._fallback_decision(bull, bear, analyst, response)
        except Exception as e:
            log.error(f"Trader 整合失敗: {e}")
            return self._fallback_decision(bull, bear, analyst, str(e))

    def _fallback_decision(self, bull: str, bear: str, analyst: str,
                            raw: str = "") -> Dict:
        """辯論失敗時的 fallback 決策"""
        return {
            "market_sentiment": "neutral",
            "sentiment_reason": f"辯論整合異常，維持中性",
            "emerging_themes": [],
            "themes_declining": [],
            "trigger_full_research": False,
            "research_reason": "",
            "adjustment_needed": False,
            "adjustment_suggestions": [],
            "debate_quality": f"整合失敗: {raw[:80]}",
            "risk_alerts": ["⚠️ 辯論引擎異常，建議手動檢視"],
            "summary": f"Bull: {bull[:60]}... | Bear: {bear[:60]}...",
        }


# ═══════════════════════════════════════════════
#  新聞監控器
# ═══════════════════════════════════════════════

class NewsMonitor:
    """即時財經新聞監控 — 聚焦持倉/追蹤標的"""

    # 基礎 RSS（當無持倉資料時 fallback）
    FALLBACK_FEEDS = [
        "https://news.google.com/rss/search?q=台股+股市&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    ]

    def __init__(self, get_symbols_fn: Callable = None):
        self.cache: List[Dict] = []
        self.last_fetch: Optional[datetime] = None
        self.get_symbols_fn = get_symbols_fn or (lambda: [])

    def _build_dynamic_feeds(self) -> List[str]:
        """從持倉/追蹤標的動態生成 RSS URL"""
        try:
            symbols = self.get_symbols_fn()
        except Exception:
            symbols = []

        if not symbols:
            return list(self.FALLBACK_FEEDS)

        feeds = []
        # 每檔標的生成一個 Google News RSS
        for sym in symbols[:8]:  # 最多 8 檔
            query = f"{sym}+股票" if sym.isdigit() else sym
            feeds.append(
                f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            )
        # 補一個通用台股新聞
        feeds.append("https://news.google.com/rss/search?q=台股+題材&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
        return feeds

    def fetch_news(self, max_articles: int = 20) -> List[Dict]:
        """抓取最新財經新聞（聚焦持倉標的）"""
        articles = []
        feed_urls = self._build_dynamic_feeds()

        # ── 來源 1: Google News RSS（動態標的） ──
        for feed_url in feed_urls:
            try:
                import feedparser
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:6]:  # 每個 feed 只取前 6 則
                    articles.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": "Google News",
                    })
            except ImportError:
                try:
                    resp = requests.get(feed_url, timeout=10)
                    import re
                    titles = re.findall(r"<title>(.*?)</title>", resp.text)
                    for t in titles[1:7]:
                        articles.append({
                            "title": t,
                            "summary": "",
                            "link": "",
                            "published": "",
                            "source": "Google News (fallback)",
                        })
                except Exception as e:
                    log.warning(f"RSS fetch failed: {feed_url} → {e}")

        # ── 來源 2: yfinance 新聞（持倉標的） ──
        try:
            symbols = self.get_symbols_fn()
            ticker_symbols = []
            for sym in (symbols or [])[:6]:
                if sym.isdigit():
                    ticker_symbols.append(f"{sym}.TW")
                else:
                    ticker_symbols.append(sym)
            if not ticker_symbols:
                ticker_symbols = ["2330.TW", "^TWII"]  # fallback

            for ticker_symbol in ticker_symbols:
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    news = ticker.news[:6]
                    for item in news:
                        content = item.get("content", {})
                        articles.append({
                            "title": content.get("title", ""),
                            "summary": content.get("summary", ""),
                            "link": content.get("canonicalUrl", {}).get("url", ""),
                            "published": content.get("pubDate", ""),
                            "source": "Yahoo Finance",
                        })
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"yfinance news fetch failed: {e}")

        # 去重（依標題）
        seen = set()
        unique = []
        for a in articles:
            key = a["title"][:80]
            if key not in seen:
                seen.add(key)
                unique.append(a)

        self.cache = unique[:max_articles]
        self.last_fetch = datetime.now()
        return self.cache

    def get_recent(self, hours: int = 4) -> List[Dict]:
        """取得最近 N 小時內的新聞"""
        if not self.last_fetch or (datetime.now() - self.last_fetch).seconds > 3600:
            self.fetch_news()

        cutoff = datetime.now() - timedelta(hours=hours)
        recent = []
        for a in self.cache:
            # 簡單過濾：如果 published 欄位是空的，保留
            recent.append(a)
        return recent[:15]


# ═══════════════════════════════════════════════
#  Telegram 通知器
# ═══════════════════════════════════════════════

class TelegramNotifier:
    """Telegram 推播通知"""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_OWNER_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)

    def send(self, text: str) -> bool:
        """發送 Telegram 訊息"""
        if not self.enabled:
            log.info(f"[TG 通知] (未啟用) {text[:100]}")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            log.error(f"Telegram 通知失敗: {e}")
            return False


# ═══════════════════════════════════════════════
#  24/7 AI 自主投資循環
# ═══════════════════════════════════════════════

class AutonomousLoop:
    """
    24/7 AI 自主投資循環引擎

    每個循環：
      1. 抓取最新財經新聞
      2. LLM 分析新聞中的題材變化、市場情緒
      3. 比對現有持倉，評估風險
      4. 如有重大變化 → 觸發完整 AI 研究 (Phase 1-4)
      5. 產出調整建議（持倉調整、停損/停利更新）
      6. Telegram 通知主人
    """

    def __init__(
        self,
        agent=None,              # AutonomousInvestmentAgent 實例
        paper_engine=None,       # PaperTradingEngine 實例
        llm_client: LLMClient = None,
        news_monitor: NewsMonitor = None,
        telegram: TelegramNotifier = None,
    ):
        self.agent = agent
        self.paper_engine = paper_engine
        self.llm = llm_client or LLMClient()

        # ── 動態取得持倉/追蹤標的符號，供 NewsMonitor 聚焦新聞 ──
        def _get_portfolio_symbols():
            syms = []
            # 1. 從 paper_engine 追蹤標的
            if self.paper_engine:
                try:
                    config = self.paper_engine.get_strategy_config()
                    track = config.get('symbols', '')
                    if track:
                        syms.extend([s.strip() for s in track.split(',') if s.strip()])
                except Exception:
                    pass
            # 2. 從 paper_engine 現有持倉
            if self.paper_engine:
                try:
                    positions = self.paper_engine.get_positions()
                    for p in positions:
                        s = p.get('symbol', '')
                        if s and s not in syms:
                            syms.append(s)
                except Exception:
                    pass
            # 3. 從 AI Agent 投資計畫
            if self.agent:
                try:
                    plan = self.agent.get_plan()
                    if plan:
                        for h in ['short_term', 'mid_term', 'long_term']:
                            for pick in plan.get(h, {}).get('picks', []):
                                s = pick.get('symbol', '')
                                if s and s not in syms:
                                    syms.append(s)
                except Exception:
                    pass
            return syms if syms else ['2330', '台積電']  # fallback

        self.news = news_monitor or NewsMonitor(get_symbols_fn=_get_portfolio_symbols)
        self.tg = telegram or TelegramNotifier()

        # 內部狀態
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 循環記錄
        self.cycle_count = 0
        self.last_cycle: Optional[datetime] = None
        self.last_adjustment: Optional[datetime] = None
        self.consecutive_errors = 0

        # 累積洞察
        self.market_sentiment: str = "neutral"  # bullish / neutral / bearish
        self.active_themes: List[str] = []
        self.alerts: List[Dict] = []  # 警報歷史
        self.daily_summary: Dict = {}

        # 對話歷史 (供 Chat API 使用)
        self.chat_history: List[Dict] = []

        # 多代理人辯論引擎
        self.debate_engine = DebateEngine(self.llm)

    # ── 控制 ──

    def start(self, interval_minutes: int = 60) -> Dict:
        """啟動 24/7 循環"""
        if self._running:
            return {"status": "error", "message": "自主循環已在運行中"}

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(interval_minutes,),
            daemon=True,
        )
        self._thread.start()

        self.tg.send("🤖 <b>AI 自主投資循環已啟動</b>\n"
                      f"⏱ 間隔：{interval_minutes} 分鐘\n"
                      f"🕐 {datetime.now().strftime('%H:%M:%S')}")

        log.info(f"🚀 自主投資循環啟動，間隔 {interval_minutes} 分鐘")
        return {
            "status": "success",
            "message": f"🚀 自主投資循環已啟動 (間隔 {interval_minutes} 分鐘)",
            "interval_minutes": interval_minutes,
        }

    def stop(self) -> Dict:
        """停止循環"""
        if not self._running:
            return {"status": "error", "message": "自主循環未在運行"}

        self._stop_event.set()
        self._running = False
        self.tg.send("⏹️ <b>AI 自主投資循環已停止</b>\n"
                      f"📊 總循環：{self.cycle_count} 次\n"
                      f"🕐 {datetime.now().strftime('%H:%M:%S')}")

        log.info(f"⏹️ 自主投資循環停止，總計 {self.cycle_count} 次")
        return {
            "status": "success",
            "message": f"⏹️ 自主投資循環已停止 (總循環 {self.cycle_count} 次)",
            "total_cycles": self.cycle_count,
        }

    def get_status(self) -> Dict:
        """查詢循環狀態"""
        return {
            "running": self._running,
            "cycle_count": self.cycle_count,
            "last_cycle": self.last_cycle.isoformat() if self.last_cycle else None,
            "last_adjustment": self.last_adjustment.isoformat() if self.last_adjustment else None,
            "market_sentiment": self.market_sentiment,
            "active_themes": self.active_themes,
            "alerts_count": len(self.alerts),
            "consecutive_errors": self.consecutive_errors,
        }

    # ── 主循環 ──

    def _run_loop(self, interval_minutes: int):
        """背景執行緒主循環"""
        log.info(f"🔄 自主投資循環執行緒啟動")

        # 首次啟動時先執行一次
        try:
            self._execute_cycle()
        except Exception as e:
            log.error(f"首次循環失敗: {e}")

        while not self._stop_event.is_set():
            # 每 30 秒檢查一次停止信號
            for _ in range(interval_minutes * 2):
                if self._stop_event.is_set():
                    break
                time.sleep(30)

            if self._stop_event.is_set():
                break

            try:
                self._execute_cycle()
                self.consecutive_errors = 0
            except Exception as e:
                self.consecutive_errors += 1
                log.error(f"循環 #{self.cycle_count + 1} 失敗: {e}")
                if self.consecutive_errors >= 5:
                    self.tg.send(f"⚠️ <b>自主投資循環連續失敗 {self.consecutive_errors} 次</b>\n{str(e)[:200]}")
                    self.consecutive_errors = 0

    def _execute_cycle(self):
        """執行單次循環"""
        self.cycle_count += 1
        cycle_start = datetime.now()
        log.info(f"🔄 循環 #{self.cycle_count} 開始")

        # ── Step 1: 抓取新聞 ──
        articles = self.news.fetch_news()

        # ── Step 2: 取得現有持倉狀態 ──
        portfolio_context = self._get_portfolio_context()

        # ── Step 3: LLM 分析新聞 + 持倉 ──
        analysis = self._llm_analyze(articles, portfolio_context)

        # ── Step 4: 檢查是否需要觸發完整 AI 研究 ──
        if analysis.get("trigger_full_research", False) and self.agent:
            self._trigger_full_research(analysis)

        # ── Step 5: 評估是否需要調整 ──
        if analysis.get("adjustment_needed", False):
            self._handle_adjustment(analysis)

        # ── Step 6: 更新狀態 ──
        self.market_sentiment = analysis.get("market_sentiment", "neutral")
        new_themes = analysis.get("emerging_themes", [])
        if new_themes:
            self.active_themes = new_themes

        self.last_cycle = cycle_start
        elapsed = (datetime.now() - cycle_start).total_seconds()
        log.info(f"✅ 循環 #{self.cycle_count} 完成 ({elapsed:.1f}s)")

    def _get_portfolio_context(self) -> str:
        """建立持倉上下文供 LLM 分析"""
        if not self.paper_engine:
            return "（無持倉數據）"

        try:
            account = self.paper_engine.get_account()
            positions = self.paper_engine.get_positions()
            config = self.paper_engine.get_strategy_config()

            ctx = f"帳戶總資產: ${account.get('total_assets', 0):,.0f}\n"
            ctx += f"可用現金: ${account.get('balance', 0):,.0f}\n"
            ctx += f"總報酬率: {account.get('total_return_pct', 0):+.2f}%\n"
            ctx += f"當前策略: {config.get('strategy_name', 'N/A')}\n"
            ctx += f"追蹤標的: {config.get('symbols', '無')}\n\n"

            if positions:
                ctx += "現有持倉:\n"
                for p in positions:
                    ctx += (f"  {p['symbol']}: {p['shares']}股 "
                            f"@${p['avg_cost']:.2f} "
                            f"現價 ${p.get('price', '?')} "
                            f"損益 {p.get('pnl_pct', 0):+.2f}%\n")
            else:
                ctx += "現有持倉: 無\n"

            return ctx
        except Exception as e:
            return f"（持倉讀取失敗: {e}）"

    def _llm_analyze(self, articles: List[Dict], portfolio_context: str) -> Dict:
        """多代理人辯論分析 — 取代舊版單一 LLM 調用

        Phase 1 強化：Bull/Bear/Analyst 三方辯論 → Trader 整合
        - Bull/Bear/Analyst 用 Flash (deepseek-chat) 快速生成多元視角
        - Trader 用 Pro (deepseek-reasoner) 深度思辨整合，產出最終決策
        - 辯論歷史保留最近 8 輪，供 Trader 參考避免重複判斷
        """
        # 建立新聞摘要
        news_text = ""
        for i, a in enumerate(articles[:10]):
            news_text += f"[{i+1}] {a['title']}\n"
            if a.get('summary'):
                news_text += f"    {a['summary'][:200]}\n"

        if not news_text:
            news_text = "（無最新新聞）"

        # 調用辯論引擎
        try:
            result = self.debate_engine.debate(news_text, portfolio_context)
            return result
        except Exception as e:
            log.error(f"辯論引擎失敗: {e}")
            return self.debate_engine._fallback_decision(
                bull="", bear="", analyst="", raw=str(e)
            )

    def _trigger_full_research(self, analysis: Dict):
        """觸發完整 Phase 1-4 AI 研究"""
        log.info("🔬 觸發完整 AI 研究")
        try:
            if self.agent:
                self.agent.phase1_discover_themes()
                self.agent.phase2_screen_candidates()
                self.agent.phase3_technical_review()
                self.agent.phase4_generate_plan()

                plan = self.agent.get_plan()
                if plan and self.paper_engine:
                    all_symbols = []
                    for h in ["short_term", "mid_term", "long_term"]:
                        for p in plan.get(h, {}).get("picks", []):
                            s = p.get("symbol", "")
                            if s and s not in all_symbols:
                                all_symbols.append(s)
                    if all_symbols:
                        self.paper_engine.update_strategy_config(symbols=",".join(all_symbols))

                self.tg.send(
                    "🔬 <b>AI 自主研究已觸發</b>\n"
                    f"📰 原因：{analysis.get('research_reason', '定期更新')}\n"
                    f"🎯 新題材：{', '.join(analysis.get('emerging_themes', []))}\n"
                    f"🕐 {datetime.now().strftime('%H:%M:%S')}"
                )
        except Exception as e:
            log.error(f"觸發研究失敗: {e}")

    def _handle_adjustment(self, analysis: Dict):
        """處理持倉調整建議 — 透過 AITradingToolkit 執行紙上/實盤交易"""
        suggestions = analysis.get("adjustment_suggestions", [])
        if not suggestions:
            return

        self.last_adjustment = datetime.now()
        alert = {
            "timestamp": datetime.now().isoformat(),
            "sentiment": analysis.get("market_sentiment"),
            "suggestions": suggestions,
            "summary": analysis.get("summary", ""),
        }
        self.alerts.append(alert)
        # 只保留最近 50 筆
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]

        # ── 透過 AITradingToolkit 執行交易（紙上/實盤雙模式）──
        executed_trades = []
        toolkit = None
        try:
            toolkit = get_toolkit(default_mode="paper")
        except Exception as e:
            log.warning(f"無法載入 AITradingToolkit: {e}")

        for s in suggestions[:5]:
            action = s.get("action", "").upper()
            symbol = s.get("symbol", "")

            if action in ("BUY", "SELL") and symbol and toolkit:
                # 取得即時報價
                quote = toolkit.get_stock_price(symbol)
                price = quote.get("price", 0) if quote.get("status") == "success" else 0

                if price and price > 0:
                    # 根據帳戶資金計算下單數量（保守：10% 資金/標的）
                    account = toolkit.get_account()
                    avail = account.get("balance", 0) if account.get("mode") == "paper" else account.get("bank_balance", 0)
                    if avail > 0:
                        qty = int(avail * 0.1 / price / 100) * 100  # 整張
                        if qty < 100:
                            qty = int(avail * 0.05 / price)  # 零股
                        if qty > 0:
                            # 風險檢查
                            risk = toolkit.check_risk(symbol, action, qty, price)
                            if risk.get("status") == "blocked":
                                executed_trades.append({
                                    "symbol": symbol, "action": action, "price": price,
                                    "quantity": qty, "success": False,
                                    "message": "; ".join(risk.get("issues", [])),
                                })
                                continue

                            result = toolkit.place_order(symbol, action, price, qty)
                            executed_trades.append({
                                "symbol": symbol, "action": action,
                                "price": price, "quantity": qty,
                                "success": result.success,
                                "message": result.message,
                            })
                            log.info(f"🤖 AI 自動交易: {action} {symbol} {qty}股 @${price:.2f} → {result.message}")

        # ── Telegram 通知 ──
        msg_parts = [f"📊 <b>AI 投資調整建議</b>\n"
                     f"📈 市場情緒：{analysis.get('market_sentiment', 'neutral')}\n"]

        for s in suggestions[:5]:
            emoji = {"BUY": "🟢", "SELL": "🔴", "REDUCE": "🟡", "HOLD": "⚪"}.get(s.get("action", ""), "➡️")
            msg_parts.append(
                f"{emoji} {s.get('symbol')} → {s.get('action')} "
                f"({s.get('reason', '')}) "
                f"[{s.get('urgency', 'medium')}]"
            )

        if executed_trades:
            msg_parts.append("\n🤖 <b>已自動執行：</b>")
            for t in executed_trades:
                status = "✅" if t["success"] else "❌"
                msg_parts.append(f"  {status} {t['action']} {t['symbol']} {t['quantity']}股 @${t['price']:.2f}")

        if analysis.get("risk_alerts"):
            msg_parts.append("\n⚠️ 風險提示：")
            for r in analysis["risk_alerts"][:3]:
                msg_parts.append(f"  • {r}")

        self.tg.send("\n".join(msg_parts))

    # ── AI 策略討論 Chat ──

    def chat(self, user_message: str, context: str = "") -> str:
        """
        AI 策略討論對話
        整合持倉、新聞、歷史對話
        """
        # 取得即時持倉
        portfolio_context = self._get_portfolio_context()

        # 取得最近新聞
        recent_news = self.news.get_recent(hours=6)
        news_context = "\n".join(
            [f"• {a['title']}" for a in recent_news[:8]]
        ) or "（無最新新聞）"

        # 系統提示
        system_prompt = f"""你是一位專業的台股投資顧問 Alice，負責協助主人制定投資策略。

【主人目前持倉狀態】
{portfolio_context}

【最近財經新聞】
{news_context}

【市場情緒】
{self.market_sentiment}

【活躍題材】
{', '.join(self.active_themes) if self.active_themes else '無特定題材'}

【對話規則】
- 用繁體中文回覆，語氣專業但親切
- 提供具體、可操作的建議
- 引用數據支持你的觀點
- 每次建議都附上風險提示
- 可以主動建議主人關注特定標的或題材
- 回覆長度控制在 300 字以內"""

        # 保留最近 10 輪對話
        recent_history = self.chat_history[-20:]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        # 更新對話歷史
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": response})

        # 限制歷史長度
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]

        return response

    def clear_chat_history(self):
        """清除對話歷史"""
        self.chat_history = []
        return {"status": "success", "message": "對話歷史已清除"}


# ═══════════════════════════════════════════════
#  模組級實例
# ═══════════════════════════════════════════════

_autonomous_loop: Optional[AutonomousLoop] = None


def get_autonomous_loop() -> AutonomousLoop:
    """取得全域 AutonomousLoop 實例（延遲初始化）"""
    global _autonomous_loop
    if _autonomous_loop is None:
        # 延遲導入避免循環依賴
        from autonomous_investment_agent import get_agent
        from paper_trading_engine import paper_engine

        _autonomous_loop = AutonomousLoop(
            agent=get_agent(),
            paper_engine=paper_engine,
        )
    return _autonomous_loop


def reset_autonomous_loop():
    """重置全域實例"""
    global _autonomous_loop
    _autonomous_loop = None
