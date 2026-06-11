"""
自主投資代理人 Autonomous Investment Agent v2.0
架構：
  Phase 1 — 題材發現：四角色辯論引擎（Bull/Bear/Analyst → Trader 裁決）
            雙模型策略：新聞蒐集用 V4 Flash，辯論階段用 V4 Pro
  Phase 2 — 概念股映射 + 基本面篩選：將題材映射到標的，用財報數據篩選
  Phase 3 — 技術面進場點：用策略引擎判斷進出場時機
  Phase 4 — 產出投資計畫（短/中/長期）+ 執行

設計原則：所有資料獲取透過 data_providers 回呼，與 Alice 工具解耦。

v2.0 更新（2026-06-01）：
  - Phase 1 新增辯論引擎：Bull(多方) / Bear(空方) / Analyst(量化) / Trader(裁決)
  - 雙模型策略：日常用 V4 Flash，辯論階段用 V4 Pro
  - 四角色皆有專業化提示詞，包含具體技術指標要求
  - 保留原有關鍵字匹配為 fallback
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
import json
import math
import re
import duckdb
import os

from strategy_engine import analyze_symbol as _strategy_analyze_symbol

# ═══════════════════════════════════════════════
#  DuckDB 動態概念股快取
# ═══════════════════════════════════════════════

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alice_core.db')

def _ensure_concept_cache_table():
    """確保概念股快取表存在"""
    try:
        conn = duckdb.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS concept_stock_cache (
                theme VARCHAR PRIMARY KEY,
                stocks JSON,
                source VARCHAR DEFAULT 'llm',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 1
            )
        """)
        conn.close()
    except Exception:
        pass  # DB 可能被鎖定，不影響核心功能

def _load_concept_cache() -> Dict[str, List[str]]:
    """從 DuckDB 載入所有動態概念股映射"""
    _ensure_concept_cache_table()
    result: Dict[str, List[str]] = {}
    try:
        conn = duckdb.connect(_DB_PATH)
        rows = conn.execute(
            "SELECT theme, stocks FROM concept_stock_cache ORDER BY hit_count DESC"
        ).fetchall()
        conn.close()
        for theme, stocks_json in rows:
            try:
                stocks = json.loads(stocks_json) if isinstance(stocks_json, str) else stocks_json
                if isinstance(stocks, list) and stocks:
                    result[theme] = [str(s) for s in stocks]
            except (json.JSONDecodeError, TypeError):
                pass
    except Exception:
        pass
    return result

def _save_concept_cache(theme: str, stocks: List[str], source: str = "llm"):
    """將概念股映射寫入 DuckDB 快取"""
    _ensure_concept_cache_table()
    try:
        conn = duckdb.connect(_DB_PATH)
        stocks_json = json.dumps(stocks, ensure_ascii=False)
        conn.execute("""
            INSERT INTO concept_stock_cache (theme, stocks, source, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (theme) DO UPDATE SET
                stocks = EXCLUDED.stocks,
                source = EXCLUDED.source,
                updated_at = CURRENT_TIMESTAMP,
                hit_count = concept_stock_cache.hit_count + 1
        """, [theme, stocks_json, source])
        conn.close()
    except Exception:
        pass

def _increment_cache_hit(theme: str):
    """增加快取命中次數"""
    try:
        conn = duckdb.connect(_DB_PATH)
        conn.execute(
            "UPDATE concept_stock_cache SET hit_count = hit_count + 1 WHERE theme = ?",
            [theme]
        )
        conn.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════
#  熱門題材 ↔ 概念股映射表
# ═══════════════════════════════════════════════
THEME_CONCEPT_MAP: Dict[str, List[str]] = {
    "AI": ["2330", "2382", "3231", "2454", "2379", "3034", "3661", "3443", "5269", "2388",
           "2303", "3037", "2317", "2357", "3711", "3035", "3406", "8046", "6415", "3669"],
    "伺服器": ["2382", "3231", "6669", "2376", "2377", "3706", "3017", "3032", "6274"],
    "機器人": ["2049", "2359", "6188", "6208", "6166", "5269", "6605", "8289"],
    "半導體": ["2330", "2303", "2454", "3034", "3711", "3443", "3661", "5269", "3406",
               "6533", "4968", "3035", "3105", "8086", "2458", "5347", "6451"],
    "電動車": ["2207", "2308", "2317", "2357", "2492", "3665", "5222", "6271", "4739"],
    "綠能": ["6477", "3576", "6244", "6443", "3708", "6861", "6414", "3023", "1519", "6409"],
    "航運": ["2603", "2609", "2615", "2606", "2636", "2633", "2618", "2645", "5608", "2637"],
    "金融": ["2881", "2882", "2891", "2892", "2886", "2883", "2884", "2885", "2887",
             "2890", "5876", "5880", "2801", "2834", "2845"],
    "軍工": ["2634", "6829", "2252", "3324", "8034", "3617", "6789", "8044"],
    "生技": ["6472", "6550", "1783", "1795", "4736", "4746", "4105", "4142", "6589",
             "3176", "4743", "4123", "4137", "4162"],
    "光通訊": ["3234", "4979", "3450", "3363", "3081", "4908", "6426", "6442"],
    "PCB": ["3037", "3044", "4958", "2367", "2313", "6269", "6191", "5469", "3189"],
    "網通": ["2345", "2344", "5388", "3704", "3596", "6285", "4906", "2332", "3027"],
    "被動元件": ["2327", "2492", "2456", "3026", "8043", "6224", "6175", "3236"],
    "IC設計": ["2454", "2379", "3034", "3035", "3443", "3661", "5269", "4968", "6533",
               "2458", "8086", "6462", "4943", "2401"],
    "面板": ["2409", "3481", "6116", "4935", "8069", "3615"],
    "記憶體": ["2344", "2408", "3260", "8271", "3006", "6239", "8299", "2451"],
    "散熱": ["3017", "3324", "6230", "3630", "3483", "2421", "3338"],
    "高速傳輸": ["5269", "4966", "6510", "6756", "2388", "6233", "6643"],
    "矽光子": ["3450", "3234", "3363", "4979", "4908", "3712"],
    "CoWoS": ["2330", "3443", "3037", "6187", "3131", "6510", "6274"],
    "低軌衛星": ["3712", "3704", "2314", "3062", "6285", "4906"],
    "重電": ["1519", "1503", "1504", "1609", "1611", "1612", "1514"],
    "碳權": ["6125", "1326", "8482", "8473", "6645"],
    "資安": ["6125", "6615", "6231", "6752", "6781", "3540"],
}

# ═══════════════════════════════════════════════
#  Phase 2 LLM 動態映射提示詞
# ═══════════════════════════════════════════════

PHASE2_LLM_MAP_SYSTEM_PROMPT = """你是台灣股市概念股映射專家。你的任務是：根據給定的題材名稱，推薦相關的台灣上市櫃概念股。

【規則】
1. 針對每個題材，推薦最相關的 5-15 檔台股
2. 只回傳台股上市/上櫃的 4 位數字股票代碼
3. 優先推薦該題材中市值最大、最具代表性的龍頭公司
4. 考慮供應鏈上下游關係（上游原料→中游製造→下游應用）
5. 若題材為新興領域（如量子運算、氫能、太空），仍需給出你能找到的最相關台股清單

【輸出格式 - 嚴格遵守 JSON，只輸出 JSON】
{
  "mappings": {
    "題材名稱": ["股票代碼1", "股票代碼2", "股票代碼3"],
    "另一題材": ["股票代碼A", "股票代碼B"]
  },
  "reasoning": "一句話解釋推薦邏輯（繁體中文）"
}

【禁止】
- 禁止輸出 JSON 以外的任何文字
- 禁止回傳非台股的代碼（如美股代碼）
- 禁止回傳不存在的股票代碼，不確定就不要列出"""


# ═══════════════════════════════════════════════
#  運行時概念股映射（種子 + DuckDB 動態快取）
# ═══════════════════════════════════════════════

# 從 DuckDB 載入動態映射，合併到種子資料
_DYNAMIC_CONCEPT_MAP: Dict[str, List[str]] = {}
_DYNAMIC_CONCEPT_MAP.update(THEME_CONCEPT_MAP)  # 種子資料優先
_cached = _load_concept_cache()
for _theme, _stocks in _cached.items():
    if _theme not in _DYNAMIC_CONCEPT_MAP:
        _DYNAMIC_CONCEPT_MAP[_theme] = _stocks
    else:
        # 合併：種子 + 快取，去重
        _existing = set(_DYNAMIC_CONCEPT_MAP[_theme])
        _existing.update(_stocks)
        _DYNAMIC_CONCEPT_MAP[_theme] = list(_existing)

# 反向索引：股票代碼 → 所屬題材
_STOCK_TO_THEMES: Dict[str, List[str]] = {}
for _theme, _stocks in _DYNAMIC_CONCEPT_MAP.items():
    for _s in _stocks:
        _STOCK_TO_THEMES.setdefault(_s, []).append(_theme)


def get_themes_for_stock(symbol: str) -> List[str]:
    """查詢某支股票屬於哪些題材"""
    return _STOCK_TO_THEMES.get(symbol, [])


def get_stocks_for_theme(theme: str) -> List[str]:
    """查詢某題材有哪些概念股（含 DuckDB 動態快取）"""
    return _DYNAMIC_CONCEPT_MAP.get(theme, [])


def match_themes_from_text(text: str) -> List[str]:
    """從文字中提取匹配的題材（含動態快取中的新題材）"""
    matched = []
    for theme in _DYNAMIC_CONCEPT_MAP:
        if theme in text:
            matched.append(theme)
    return matched


def add_concept_mapping(theme: str, stocks: List[str], source: str = "manual"):
    """
    動態新增題材→概念股映射（寫入 DuckDB + 更新運行時字典）
    供 Alice 主對話完成 mapping 後呼叫
    """
    if not theme or not stocks:
        return
    _DYNAMIC_CONCEPT_MAP[theme] = stocks
    _save_concept_cache(theme, stocks, source)
    # 重建反向索引
    for _s in stocks:
        _STOCK_TO_THEMES.setdefault(_s, []).append(theme)


def get_all_themes() -> List[str]:
    """取得所有已知題材（含動態快取）"""
    return sorted(_DYNAMIC_CONCEPT_MAP.keys())


# ═══════════════════════════════════════════════
#  四角色辯論提示詞（專業化）
# ═══════════════════════════════════════════════

BULL_SYSTEM_PROMPT = """你是台股多方（看多）分析師，代號「多頭分析師」。你的唯一任務是：從新聞中找出所有「看多」的理由，用最樂觀的角度解讀每一個數據。

【分析框架 - 必須逐項檢視並引用具體指標】
1. 產業趨勢：
   - 全球/台灣的產業利多政策、國際訂單、技術突破
   - 引用具體數字：市場規模預估（億元/%）、成長率（YoY）
2. 資金面：
   - 三大法人買超（外資/投信/自營商，標示張數或金額）
   - 融資餘額變化、券資比
   - 若無數據，明確標示「待查證：外資近5日買賣超」
3. 技術面（必須引用具體數值）：
   - RSI(14)：目前數值與方向，>50 視為多方訊號
   - MACD：DIF/MACD 線交叉方向，柱狀體變化
   - KDJ：K/D/J 值，K>D 視為多方
   - 布林通道：股價在通道中的位置，中線以上為多方
   - 均線排列：5/10/20/60 MA，多頭排列加分
   - 量價關係：價漲量增、突破頸線
   - 若無數據，標示「待技術面確認」
4. 基本面（必須引用具體數值）：
   - 營收 YoY/MoM 成長率
   - 毛利率/營益率趨勢
   - EPS 動能（季度比較）
   - 本益比與同業比較
   - 若無數據，標示「待財報確認」
5. 籌碼面：
   - 大戶持股變化（集保分布）
   - 券資比變化
   - 若無數據，標示「待籌碼面確認」

【輸出格式】
以條列方式呈現，每項必須包含：
- 具體數據（若無則明確標示「待驗證」或「待XXX確認」）
- 該數據為何支持看多
- 結尾：一句話總結最強的多方論點

【禁止】
- 禁止提及任何看空理由
- 禁止使用模糊詞彙（如「可能」「或許」），必須給出具體判斷"""

BEAR_SYSTEM_PROMPT = """你是台股空方（看空）分析師，代號「空頭分析師」。你的唯一任務是：針對多方論點逐一反駁，從新聞中找出所有「看空」的理由，用最悲觀的角度解讀每一個數據。

【反駁框架 - 必須逐項針對多方論點反擊】
1. 產業風險：
   - 景氣循環高點、政策轉向風險、國際競爭加劇
   - 引用具體數字：產能過剩率、市占下滑、關稅影響
2. 資金面：
   - 三大法人賣超（外資/投信/自營商，標示張數或金額）
   - 融資過高（融資餘額佔股本比例）、散戶進場警戒
   - 若無數據，明確標示「待查證：近期法人動向」
3. 技術面（必須引用具體數值）：
   - RSI(14)：>70 視為過熱/超買，<50 空方掌控
   - MACD：死亡交叉、柱狀體萎縮、背離訊號
   - KDJ：K<D、高檔鈍化後轉弱
   - 布林通道：股價觸及上緣後壓回、通道收窄
   - 均線排列：空頭排列、死亡交叉
   - 量價關係：價跌量增、價漲量縮（背離）
   - 若無數據，標示「待技術面確認」
4. 基本面（必須引用具體數值）：
   - 營收 YoY/MoM 衰退
   - 毛利率下滑、費用率上升
   - EPS 下修（法人預估）
   - 本益比過高（與歷史區間比較）
   - 若無數據，標示「待財報確認」
5. 籌碼面：
   - 大戶出貨（集保分布下滑）
   - 融資餘額持續增加（散戶接刀）
   - 若無數據，標示「待籌碼面確認」

【輸出格式】
逐項反駁多方論點，每項必須包含：
- 具體數據（若無則明確標示「待驗證」或「待XXX確認」）
- 該數據為何支持看空
- 結尾：一句話總結最強的空方論點

【禁止】
- 禁止提及任何看多理由
- 禁止使用模糊詞彙（如「可能」「或許」），必須給出具體判斷"""

ANALYST_SYSTEM_PROMPT = """你是台股量化分析師，代號「技術分析師」。你的任務是：客觀補充數據面的分析，不受多方或空方情緒影響。你只相信數字。

【分析框架 - 必須逐項檢視以下技術指標並給出中立解讀】
1. RSI(14)：
   - 當前數值：___
   - >70：過熱區（但強勢股可持續鈍化）
   - 50-70：偏多區
   - 30-50：偏空區
   - <30：超賣區（但弱勢股可持續鈍化）
   - 無數據則標示「RSI：待取得」
2. MACD (12,26,9)：
   - DIF 值：___ / MACD 值：___ / 柱狀體：___
   - DIF > MACD 且柱狀體放大 → 多方加速
   - DIF < MACD 且柱狀體縮小 → 空方減緩
   - 背離訊號：價格創高但 MACD 未創高 → 潛在反轉
   - 無數據則標示「MACD：待取得」
3. KDJ (9,3,3)：
   - K 值：___ / D 值：___ / J 值：___
   - K > 80：高檔區 / K < 20：低檔區
   - K 突破 D 向上：短多 / K 跌破 D 向下：短空
   - 無數據則標示「KDJ：待取得」
4. 布林通道 (20,2)：
   - 上緣：___ / 中線：___ / 下緣：___
   - 股價位置：上緣(強勢)/中線以上(偏多)/中線以下(偏空)/下緣(弱勢)
   - 通道寬度：擴張(趨勢明確)/收窄(即將突破)
   - 無數據則標示「布林：待取得」
5. 均線排列：
   - MA5：___ / MA10：___ / MA20：___ / MA60：___
   - 多頭排列：MA5>MA10>MA20>MA60
   - 空頭排列：MA5<MA10<MA20<MA60
   - 糾結：各均線差距 <2%，即將表態
   - 無數據則標示「均線：待取得」
6. 三大法人買賣超（近5日）：
   - 外資：___張 / 投信：___張 / 自營商：___張
   - 無數據則標示「法人：待取得」
7. 融資/融券：
   - 融資餘額：___張（較前日 +/- ___）
   - 融券餘額：___張 / 券資比：___%
   - 無數據則標示「融資券：待取得」
8. 營收動能：
   - 最新月營收 YoY：___% / MoM：___%
   - 累計營收 YoY：___%
   - 無數據則標示「營收：待取得」
9. 本益比區間：
   - 目前 PE：___ / 歷史 PE 區間：___ ~ ___
   - 目前位在歷史 ___% 位置
   - 無數據則標示「PE：待取得」

【輸出格式】
逐項列出指標數據與中立解讀。區分為：
- 「已確認」：有數據的指標，附上數據與解讀
- 「待取得」：沒有數據的指標，明確標示缺少什麼

【禁止】
- 禁止選邊站（不說看多或看空）
- 禁止給投資建議
- 有幾分數據說幾分話"""

TRADER_SYSTEM_PROMPT = """你是台股資深交易員，代號「交易策略師」。你的任務是：整合多方、空方、分析師的論點，做出最終裁決。

【評估權重】
- 分析師量化數據：40%（數字不會騙人）
- 多方論點邏輯：25%
- 空方論點邏輯：25%
- 自身交易經驗：10%（考量市場情緒、資金輪動、題材新鮮度）

【裁決邏輯】
1. 先看分析師的「已確認」指標數量 vs「待取得」數量
   - 若「待取得」超過 50%，降低 confidence
2. 比對 Bull 和 Bear 的論點，找出「有數據支持」的一方
3. 判斷市場目前處於哪個階段：萌芽期/成長期/成熟期/衰退期
4. 綜合給出 BULLISH / BEARISH / NEUTRAL

【輸出格式 - 嚴格遵守 JSON 格式，只輸出 JSON，不要任何其他文字】
{
  "top_themes": ["題材1", "題材2", "題材3"],
  "decision": "BULLISH",
  "confidence": 0.75,
  "bull_wins": true,
  "market_stage": "成長期",
  "summary": "一句話總結當前局勢（繁體中文）",
  "reasoning": "詳細理由，說明為何做出此裁決（繁體中文）",
  "key_indicators": {
    "RSI": "45 / 中性偏低",
    "MACD": "DIF>MACD 多方格局",
    "法人": "外資近5日買超 1,200 張",
    "營收": "YoY +15% 成長"
  },
  "risk_factors": ["風險1", "風險2"],
  "data_completeness": 0.6
}
- decision: "BULLISH" / "BEARISH" / "NEUTRAL"
- confidence: 0.0 ~ 1.0
- bull_wins: true 表示多方論點較強，false 表示空方較強
- market_stage: "萌芽期" / "成長期" / "成熟期" / "衰退期"
- data_completeness: 0.0 ~ 1.0，表示有多少指標有實際數據（非「待取得」）

【禁止】
- 禁止輸出任何 JSON 以外的文字
- 禁止憑空捏造數據（key_indicators 中只能包含分析師已確認的數據）
- confidence 必須根據 data_completeness 和論點品質合理給出"""


# ═══════════════════════════════════════════════
#  辯論輔助函數
# ═══════════════════════════════════════════════

def _build_news_summary(articles: List[Dict], max_articles: int = 15) -> str:
    """將新聞文章清單轉為結構化摘要文字"""
    if not articles:
        return "（無新聞數據，請基於 2026 年台股市場常識進行分析）"

    lines = []
    for i, art in enumerate(articles[:max_articles], 1):
        title = art.get("title", "") or art.get("snippet", "") or ""
        summary = art.get("summary", "") or art.get("description", "") or ""
        source = art.get("source", "") or art.get("publisher", "") or ""
        date = art.get("published", "") or art.get("date", "") or ""

        line = f"{i}. 【{title}】"
        if summary:
            line += f"\n   摘要：{summary[:200]}"
        if source:
            line += f"\n   來源：{source}"
        if date:
            line += f" | {date}"
        lines.append(line)

    return "\n\n".join(lines)


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """從 LLM 回應中提取 JSON，支援多種格式"""
    # 嘗試直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 嘗試從 ```json ... ``` 中提取
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 嘗試找到 { ... } 最外層
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ═══════════════════════════════════════════════
#  AutonomousInvestmentAgent
# ═══════════════════════════════════════════════

class AutonomousInvestmentAgent:
    """
    自主投資代理人 v2.0
    四階段流程：題材發現（辯論引擎）→ 概念股篩選 → 技術進場 → 投資計畫

    雙模型策略：
      - 新聞蒐集階段：使用 V4 Flash（快速、低成本）
      - 辯論階段：使用 V4 Pro（深度推理、多層討論）
    """

    def __init__(self, data_providers: Optional[Dict[str, Callable]] = None):
        """
        data_providers 是一個 dict，key 為 provider 名稱，value 為 async/sync callable。
        預期 keys:
          - "fetch_stock_info": Callable[[str], Dict]   → 取得個股基本資料
          - "fetch_stock_price": Callable[[str], float] → 取得即時價格
          - "fetch_stock_history": Callable[[str, str], List] → 取得歷史 OHLCV
          - "search_news": Callable[[str], List[Dict]]  → 搜尋近期新聞
          - "market_overview": Callable[[], Dict]       → 大盤總覽

          # v2.0 新增：LLM 調用（支援雙模型）
          - "call_llm": Callable[[str, str, str], str]
                        → 調用 LLM
                        參數: (system_prompt, user_prompt, model)
                        model: "flash"=V4 Flash(預設), "pro"=V4 Pro(辯論用)
                        回傳: LLM 文字回應
        """
        self.providers = data_providers or {}
        self.log: List[Dict] = []
        self.current_plan: Optional[Dict] = None
        self.candidate_stocks: List[str] = []
        self.screened: List[Dict] = []
        self.active_themes: List[str] = []
        # v2.0：儲存辯論逐字稿
        self.last_debate_transcript: Optional[Dict] = None
        # v2.1：辯論歷史記錄（每筆包含 timestamp + 四個角色論述 + 最終裁決）
        self.debate_history: List[Dict] = []
        self._debate_counter: int = 0  # 固定唯一 ID，避免 index 漂移

    # ── 取得 LLM provider ──

    def _get_llm(self) -> Optional[Callable]:
        """取得 call_llm provider，若不可用回傳 None"""
        return self.providers.get("call_llm")

    def _llm(self, system_prompt: str, user_prompt: str, model: str = "flash") -> str:
        """
        調用 LLM。若 provider 不存在則拋出 RuntimeError。
        model: "flash" (V4 Flash) 或 "pro" (V4 Pro)
        """
        fn = self._get_llm()
        if not fn:
            raise RuntimeError("call_llm provider 未設定")
        return fn(system_prompt, user_prompt, model)

    def _llm_json(self, system_prompt: str, user_prompt: str, model: str = "pro") -> Optional[Dict]:
        """調用 LLM 並嘗試解析回傳的 JSON"""
        try:
            raw = self._llm(system_prompt, user_prompt, model)
            return _extract_json_from_text(raw)
        except Exception as e:
            self._log("llm_json", "error", f"LLM JSON 解析失敗: {e}")
            return None

    # ── Phase 1a: 傳統關鍵字匹配（fallback）──

    def phase1_discover_themes(self, search_news_fn: Optional[Callable] = None,
                                extra_prompts: List[str] = None) -> Dict:
        """
        從近期新聞/國際趨勢中找出熱門題材（關鍵字匹配版，作為 fallback）。
        若 search_news_fn 不可用，則使用內建熱門題材表。
        """
        self._log("phase1", "start", "開始題材發現 (關鍵字匹配模式)")

        themes_found: Dict[str, int] = {}
        all_articles: List[Dict] = []

        queries = extra_prompts or [
            "2026 台股 熱門題材 趨勢",
            "2026 台灣股市 AI 半導體 投資熱點",
            "2026 台股 國際趨勢 利多 產業",
        ]

        fn = search_news_fn or self.providers.get("search_news")
        if fn:
            for q in queries:
                try:
                    results = fn(q)
                    all_articles.extend(results if isinstance(results, list) else [])
                    for article in (results if isinstance(results, list) else []):
                        text = (article.get("title", "") + " " +
                                article.get("summary", "") + " " +
                                article.get("snippet", ""))
                        matched = match_themes_from_text(text)
                        for t in matched:
                            themes_found[t] = themes_found.get(t, 0) + 1
                except Exception as e:
                    self._log("phase1", "search_error", str(e))

        if not themes_found:
            fallback_themes = ["AI", "半導體", "伺服器", "IC設計", "機器人", "綠能", "金融"]
            for t in fallback_themes:
                themes_found[t] = 1

        sorted_themes = sorted(themes_found.items(), key=lambda x: x[1], reverse=True)[:5]
        self.active_themes = [t[0] for t in sorted_themes]

        result = {
            "status": "success",
            "phase": 1,
            "method": "keyword_match",
            "themes": [{"name": t, "frequency": f} for t, f in sorted_themes],
            "articles_count": len(all_articles),
            "timestamp": datetime.now().isoformat(),
        }
        self._log("phase1", "complete", f"發現 {len(self.active_themes)} 個題材: {self.active_themes}")
        return result

    # ── Phase 1b: 四角色辯論引擎（主力）──

    def phase1_debate_discover_themes(self,
                                       search_news_fn: Optional[Callable] = None,
                                       extra_prompts: List[str] = None,
                                       force_debate: bool = True) -> Dict:
        """
        四角色辯論引擎：Bull(多方) / Bear(空方) / Analyst(量化) → Trader(裁決)

        雙模型策略：
          - 新聞蒐集：V4 Flash
          - 辯論階段：V4 Pro

        若 call_llm provider 不可用，自動退回 phase1_discover_themes (關鍵字匹配)。

        Parameters:
          search_news_fn: 新聞搜尋函數
          extra_prompts: 額外搜尋提示
          force_debate: 若 LLM 不可用，設 True 會報錯，設 False 會退回關鍵字匹配
        """
        # 檢查 LLM 可用性
        llm = self._get_llm()
        if not llm:
            if force_debate:
                return {
                    "status": "error",
                    "phase": 1,
                    "method": "debate",
                    "message": "call_llm provider 未設定，無法執行辯論模式。請設定後重試。",
                }
            self._log("phase1", "fallback", "LLM 不可用，退回關鍵字匹配模式")
            return self.phase1_discover_themes(
                search_news_fn=search_news_fn,
                extra_prompts=extra_prompts,
            )

        self._log("phase1", "start", "開始題材發現 (四角色辯論模式)")

        # ── Step 0: 新聞蒐集（V4 Flash 層面，但 agent 不直接控制模型）──
        queries = extra_prompts or [
            "2026 台股 熱門題材 趨勢",
            "2026 台灣股市 AI 半導體 投資熱點",
            "2026 台股 國際趨勢 利多 產業",
        ]
        all_articles: List[Dict] = []
        fn = search_news_fn or self.providers.get("search_news")
        if fn:
            for q in queries:
                try:
                    results = fn(q)
                    if isinstance(results, list):
                        all_articles.extend(results)
                except Exception as e:
                    self._log("phase1", "search_error", str(e))

        news_summary = _build_news_summary(all_articles)
        self._log("phase1", "news_collected", f"蒐集 {len(all_articles)} 則新聞")

        # ── Step 1: Bull 多方分析（V4 Pro）──
        bull_user = f"""以下是近期台股相關新聞摘要：

{news_summary}

請以多方（看多）分析師的角度，找出所有看多理由。務必引用具體的技術指標數據（RSI/MACD/KDJ/法人/營收等），若無法取得數據請標示「待驗證」。
目前時間：2026 年 6 月。請基於 2026 年的市場環境進行分析。"""

        try:
            bull_argument = self._llm(BULL_SYSTEM_PROMPT, bull_user, model="pro")
            self._log("phase1", "bull_complete", f"多方分析完成 ({len(bull_argument)} 字元)")
        except Exception as e:
            self._log("phase1", "bull_error", str(e))
            # Bull 失敗時，用 fallback
            return self.phase1_discover_themes(
                search_news_fn=search_news_fn,
                extra_prompts=extra_prompts,
            )

        # ── Step 2: Bear 空方反駁（V4 Pro）──
        bear_user = f"""以下是近期台股相關新聞摘要：

{news_summary}

以下是多方分析師的看多論點：

{bull_argument}

請以空方（看空）分析師的角度，逐一反駁多方論點，找出所有看空理由。務必引用具體的技術指標數據，若無法取得請標示「待驗證」。
目前時間：2026 年 6 月。"""

        try:
            bear_argument = self._llm(BEAR_SYSTEM_PROMPT, bear_user, model="pro")
            self._log("phase1", "bear_complete", f"空方分析完成 ({len(bear_argument)} 字元)")
        except Exception as e:
            self._log("phase1", "bear_error", str(e))
            bear_argument = "（空方分析失敗，跳過此階段）"

        # ── Step 3: Analyst 量化補充（V4 Pro）──
        analyst_user = f"""以下是近期台股相關新聞摘要：

{news_summary}

多方論點：
{bull_argument}

空方論點：
{bear_argument}

請以量化分析師的角度，補充客觀的技術指標數據分析。逐項檢視 RSI/MACD/KDJ/布林通道/均線/三大法人/融資券/營收/PE。有數據就列出，沒有數據就標示「待取得」。
目前時間：2026 年 6 月。"""

        try:
            analyst_argument = self._llm(ANALYST_SYSTEM_PROMPT, analyst_user, model="pro")
            self._log("phase1", "analyst_complete", f"分析師完成 ({len(analyst_argument)} 字元)")
        except Exception as e:
            self._log("phase1", "analyst_error", str(e))
            analyst_argument = "（量化分析失敗，跳過此階段）"

        # ── Step 4: Trader 裁決（V4 Pro）──
        trader_user = f"""以下是近期台股相關新聞摘要：

{news_summary}

多方論點：
{bull_argument}

空方論點：
{bear_argument}

量化分析：
{analyst_argument}

請以資深交易員角度做出最終裁決，輸出嚴格的 JSON 格式。
目前時間：2026 年 6 月。"""

        trader_decision = self._llm_json(TRADER_SYSTEM_PROMPT, trader_user, model="pro")

        if not trader_decision:
            self._log("phase1", "trader_error", "Trader JSON 解析失敗，退回關鍵字匹配")
            return self.phase1_discover_themes(
                search_news_fn=search_news_fn,
                extra_prompts=extra_prompts,
            )

        self._log("phase1", "trader_complete",
                   f"裁決: {trader_decision.get('decision')}, "
                   f"信心: {trader_decision.get('confidence')}, "
                   f"多方勝: {trader_decision.get('bull_wins')}")

        # ── 提取題材 ──
        top_themes = trader_decision.get("top_themes", [])
        if not top_themes:
            # 從文字中匹配 fallback
            combined_text = f"{news_summary} {bull_argument} {trader_decision.get('summary', '')}"
            top_themes = match_themes_from_text(combined_text)

        # 保留 LLM 回傳的所有主題（即使不在 _DYNAMIC_CONCEPT_MAP 中）
        # Phase 2 會用 LLM 動態映射處理未知題材
        valid_themes = []
        unknown_themes = []
        for t in top_themes:
            if t in _DYNAMIC_CONCEPT_MAP:
                valid_themes.append(t)
            else:
                unknown_themes.append(t)

        # 若 LLM 完全未回傳有效主題，才使用 fallback
        if not valid_themes and not unknown_themes:
            valid_themes = ["AI", "半導體", "伺服器", "IC設計", "機器人"]

        # 優先使用已映射的主題，再附加 LLM 發現的新主題
        self.active_themes = (valid_themes + unknown_themes)[:8]

        # ── 儲存辯論逐字稿 ──
        self.last_debate_transcript = {
            "bull_argument": bull_argument,
            "bear_argument": bear_argument,
            "analyst_argument": analyst_argument,
            "trader_decision": trader_decision,
        }

        # v2.1：追加至辯論歷史
        self._debate_counter += 1
        debate_record = {
            "debate_id": self._debate_counter,
            "timestamp": datetime.now().isoformat(),
            "themes": self.active_themes,
            "decision": trader_decision.get("decision"),
            "confidence": trader_decision.get("confidence"),
            "market_stage": trader_decision.get("market_stage"),
            "summary": trader_decision.get("summary", ""),
            "bull_argument": bull_argument,
            "bear_argument": bear_argument,
            "analyst_argument": analyst_argument,
            "trader_decision": trader_decision,
        }
        self.debate_history.append(debate_record)
        # 只保留最近 30 筆
        if len(self.debate_history) > 30:
            self.debate_history = self.debate_history[-30:]

        result = {
            "status": "success",
            "phase": 1,
            "method": "debate",
            "themes": [{"name": t, "frequency": 1} for t in self.active_themes],
            "trader_decision": trader_decision,
            "debate_transcript": self.last_debate_transcript,
            "articles_count": len(all_articles),
            "timestamp": datetime.now().isoformat(),
        }
        self._log("phase1", "complete",
                   f"辯論完成，發現 {len(self.active_themes)} 個題材: {self.active_themes}")
        return result

    # ── Phase 2: 概念股映射 + 基本面篩選 ──

    def _web_search_stocks(self, theme: str) -> List[str]:
        """使用 DuckDuckGo Lite 搜尋題材對應的台股概念股，提取四位數股票代碼"""
        import requests as _requests
        import re as _re
        try:
            query = f"{theme} 概念股 台股"
            url = f"https://lite.duckduckgo.com/lite/?q={_requests.utils.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = _requests.get(url, headers=headers, timeout=10)
            codes = set(_re.findall(r'\b(\d{4})\b', resp.text))
            exclude = set(str(y) for y in range(2024, 2031))
            codes = codes - exclude
            return list(codes)[:15]
        except Exception:
            return []

    def _phase2_map_concepts(self, themes: List[str]) -> Dict[str, List[str]]:
        """
        將題材映射到台股概念股。三層策略：
        1. DuckDB 快取命中 → 直接回傳
        2. Web 搜尋（DuckDuckGo Lite）→ 快速提取股票代碼，成功後寫入快取
        3. LLM 動態映射 → 僅在網搜失敗時使用，成功後寫入快取

        Returns:
            { "題材名稱": ["股票代碼", ...], ... }
        """
        result: Dict[str, List[str]] = {}
        uncached: List[str] = []

        # ── 第一層：DuckDB 快取 ──
        for theme in themes:
            cached = get_stocks_for_theme(theme)
            if cached:
                result[theme] = cached
                _increment_cache_hit(theme)
            else:
                uncached.append(theme)

        if not uncached:
            self._log("phase2", "cache_hit", f"全部 {len(themes)} 個題材命中快取")
            return result

        # ── 第二層：Web 搜尋（DuckDuckGo Lite，快速提取股票代碼）──
        still_uncached: List[str] = []
        for theme in uncached:
            try:
                web_stocks = self._web_search_stocks(theme)
                if web_stocks:
                    result[theme] = web_stocks
                    _save_concept_cache(theme, web_stocks, "web_search")
                    if theme not in _DYNAMIC_CONCEPT_MAP:
                        _DYNAMIC_CONCEPT_MAP[theme] = web_stocks
                    self._log("phase2", "web_search_hit",
                               f"網搜 {theme} → {len(web_stocks)} 檔: {web_stocks[:5]}...")
                else:
                    still_uncached.append(theme)
            except Exception as e:
                self._log("phase2", "web_search_error", f"網搜 {theme} 失敗: {e}")
                still_uncached.append(theme)

        if not still_uncached:
            self._log("phase2", "web_search_complete", f"網搜命中全部 {len(uncached)} 個未快取題材")
            return result

        uncached = still_uncached

        # ── 第三層：LLM 動態映射 ──
        llm = self._get_llm()
        if not llm:
            self._log("phase2", "llm_unavailable",
                       f"LLM 不可用，{len(uncached)} 個未快取題材無法映射: {uncached}")
            return result

        self._log("phase2", "llm_map_start",
                   f"快取未命中 {len(uncached)} 個題材: {uncached}，啟動 LLM 動態映射")

        user_prompt = (
            "請推薦以下台灣股市題材的相關概念股：\n\n"
            + "\n".join(f"  - {t}" for t in uncached)
            + "\n\n【重要規則】\n"
            + "1. 只回傳台股上市/上櫃的 4 位數字股票代碼\n"
            + "2. 優先推薦該題材中市值最大、最具代表性的龍頭公司\n"
            + "3. 考慮供應鏈上下游關係（上游原料→中游製造→下游應用）\n"
            + "4. 每個題材推薦 5-15 檔\n"
            + "5. 若題材為新興領域（如量子運算、氫能、太空），仍需給出最相關的台股清單\n"
            + "6. 目前時間：2026 年 6 月，請基於 2026 年的市場環境推薦\n"
        )

        try:
            llm_result = self._llm_json(PHASE2_LLM_MAP_SYSTEM_PROMPT, user_prompt, model="flash")
            if llm_result and isinstance(llm_result.get("mappings"), dict):
                for theme, stocks in llm_result["mappings"].items():
                    if isinstance(stocks, list):
                        valid_stocks = [
                            s for s in stocks
                            if isinstance(s, str) and re.match(r'^\d{4}[A-Za-z]?$', s)
                        ]
                        if valid_stocks:
                            result[theme] = valid_stocks
                            # 寫入 DuckDB 快取
                            _save_concept_cache(theme, valid_stocks, "llm")
                            # 更新運行時字典
                            if theme not in _DYNAMIC_CONCEPT_MAP:
                                _DYNAMIC_CONCEPT_MAP[theme] = valid_stocks
                            self._log("phase2", "llm_mapped",
                                       f"LLM 映射 {theme} → {len(valid_stocks)} 檔: {valid_stocks[:5]}...")
                return result
            else:
                self._log("phase2", "llm_empty", "LLM 回傳格式不正確或 mappings 為空")
        except Exception as e:
            self._log("phase2", "llm_error", str(e))

        return result

    # 向後相容別名
    _phase2_llm_map_concepts = _phase2_map_concepts

    def phase2_screen_candidates(self,
                                  fetch_stock_info_fn: Optional[Callable] = None,
                                  fetch_stock_price_fn: Optional[Callable] = None,
                                  min_market_cap_billion: float = 1.0,
                                  max_pe: float = 50) -> Dict:
        """
        將活躍題材映射到概念股，並以基本面篩選。
        """
        self._log("phase2", "start", f"從 {len(self.active_themes)} 個題材映射概念股")

        all_candidates: set = set()
        unmatched_themes: List[str] = []

        for theme in self.active_themes:
            stocks = get_stocks_for_theme(theme)
            if stocks:
                all_candidates.update(stocks)
            else:
                unmatched_themes.append(theme)

        # ── LLM 動態映射：處理靜態字典未涵蓋的新題材 ──
        llm_mapped_count = 0
        if unmatched_themes:
            self._log("phase2", "llm_map_start",
                       f"靜態字典未命中 {len(unmatched_themes)} 個題材: {unmatched_themes}，啟動 LLM 動態映射")
            llm_mapped = self._phase2_map_concepts(unmatched_themes)
            for theme, stocks in llm_mapped.items():
                if stocks:
                    all_candidates.update(stocks)
                    llm_mapped_count += len(stocks)
                    self._log("phase2", "llm_mapped",
                               f"LLM 映射 {theme} → {len(stocks)} 檔: {stocks[:5]}...")
            if llm_mapped_count == 0 and unmatched_themes:
                self._log("phase2", "llm_map_empty",
                           f"LLM 映射未產出任何股票，未匹配題材: {unmatched_themes}")


        if not all_candidates:
            self._log("phase2", "error", "無概念股可篩選")
            return {"status": "error", "phase": 2, "message": "無概念股"}

        self.candidate_stocks = list(all_candidates)
        fetch_info = fetch_stock_info_fn or self.providers.get("fetch_stock_info")
        fetch_price = fetch_stock_price_fn or self.providers.get("fetch_stock_price")

        screened = []
        skipped_count = 0

        for sym in self.candidate_stocks:
            try:
                info = {}
                price = None
                if fetch_info:
                    info = fetch_info(sym) or {}
                if fetch_price:
                    price = fetch_price(sym)

                market_cap = info.get("market_cap") or info.get("marketCap")
                pe = info.get("pe_ratio") or info.get("trailingPE") or info.get("forwardPE")
                name = info.get("name") or info.get("shortName") or sym
                sector = info.get("sector") or info.get("industry") or ""
                themes = get_themes_for_stock(sym)

                if market_cap is not None and isinstance(market_cap, (int, float)):
                    cap_b = market_cap / 1e9
                    if cap_b < min_market_cap_billion:
                        skipped_count += 1
                        continue

                if pe is not None and isinstance(pe, (int, float)) and pe > 0:
                    if pe > max_pe:
                        skipped_count += 1
                        continue

                screened.append({
                    "symbol": sym,
                    "name": name,
                    "price": round(price, 2) if price else None,
                    "market_cap": market_cap,
                    "pe": round(pe, 2) if pe else None,
                    "sector": sector,
                    "themes": themes,
                    "score": 0,
                })
            except Exception as e:
                skipped_count += 1
                continue

        screened.sort(key=lambda x: len(x.get("themes", [])), reverse=True)
        self.screened = screened[:12]

        result = {
            "status": "success",
            "phase": 2,
            "total_candidates": len(self.candidate_stocks),
            "screened_count": len(screened),
            "skipped_count": skipped_count,
            "top_picks": self.screened,
            "timestamp": datetime.now().isoformat(),
        }
        self._log("phase2", "complete", f"篩出 {len(self.screened)} 支，跳過 {skipped_count}")
        return result

    # ── Phase 3: 技術面進場點 ──

    def phase3_technical_review(self,
                                 analyze_fn: Optional[Callable] = None,
                                 strategy_name: str = "adaptive") -> Dict:
        """
        對篩選後的標的進行技術面分析，判斷進出場時機。
        analyze_fn(symbol, strategy_name) → {"signal", "confidence", "reason", "indicators", "price"}
        """
        self._log("phase3", "start", f"技術面分析 {len(self.screened)} 支，策略: {strategy_name}")

        analyze = analyze_fn or self.providers.get("analyze_symbol")
        if not analyze:
            self._log("phase3", "fallback", "無外部 provider，使用內建 strategy_engine")
            analyze = _strategy_analyze_symbol

        reviewed = []
        for stock in self.screened:
            sym = stock["symbol"]
            try:
                r = analyze(sym, strategy_name)
                stock["signal"] = r.get("signal", "HOLD")
                stock["confidence"] = r.get("confidence", 0)
                stock["reason"] = r.get("reason", "")
                stock["price"] = r.get("price") or stock.get("price")
                stock["indicators"] = r.get("indicators", {})

                signal_bonus = {"BUY": 30, "HOLD": 10, "SELL": -30}.get(stock["signal"], 0)
                theme_bonus = min(30, len(stock.get("themes", [])) * 8)
                confidence_bonus = min(40, stock["confidence"] * 0.4)
                stock["score"] = signal_bonus + theme_bonus + confidence_bonus

                reviewed.append(stock)
            except Exception as e:
                stock["signal"] = "ERROR"
                stock["reason"] = str(e)
                stock["score"] = -99
                reviewed.append(stock)

        reviewed.sort(key=lambda x: x.get("score", 0), reverse=True)
        self.screened = reviewed

        buy_signals = [s for s in reviewed if s.get("signal") == "BUY"]
        hold_signals = [s for s in reviewed if s.get("signal") == "HOLD"]

        result = {
            "status": "success",
            "phase": 3,
            "strategy": strategy_name,
            "reviewed_count": len(reviewed),
            "buy_count": len(buy_signals),
            "hold_count": len(hold_signals),
            "candidates": reviewed,
            "timestamp": datetime.now().isoformat(),
        }
        self._log("phase3", "complete",
                   f"BUY:{len(buy_signals)} HOLD:{len(hold_signals)}")
        return result

    # ── Phase 4: 產出投資計畫 ──

    def phase4_generate_plan(self, budget: float = 1000000) -> Dict:
        """
        依據篩選結果產出投資計畫，區分短中長期。
        """
        self._log("phase4", "start", f"預算: ${budget:,.0f}")

        buy_list = [s for s in self.screened if s.get("signal") == "BUY"]
        hold_list = [s for s in self.screened if s.get("signal") == "HOLD"]

        if not buy_list:
            buy_list = hold_list[:4]
            hold_list = hold_list[4:]

        short_term_budget = budget * 0.25
        mid_term_budget = budget * 0.45
        long_term_budget = budget * 0.30

        plan = {
            "budget": budget,
            "generated_at": datetime.now().isoformat(),
            "active_themes": self.active_themes,

            "short_term": {
                "description": "短期波段 (1-4 週)，高流動性、技術面強勢",
                "budget": round(short_term_budget, 2),
                "stop_loss_pct": 5,
                "take_profit_pct": 10,
                "picks": self._build_picks(buy_list[:3], short_term_budget, "short"),
            },
            "mid_term": {
                "description": "中期趨勢 (1-3 月)，基本面 + 技術面並重",
                "budget": round(mid_term_budget, 2),
                "stop_loss_pct": 8,
                "take_profit_pct": 20,
                "picks": self._build_picks(buy_list[3:6], mid_term_budget, "mid"),
            },
            "long_term": {
                "description": "長期布局 (3-12 月)，產業趨勢明確",
                "budget": round(long_term_budget, 2),
                "stop_loss_pct": 12,
                "take_profit_pct": 35,
                "picks": self._build_picks(buy_list[6:9] + hold_list[:3], long_term_budget, "long"),
            },
        }

        self.current_plan = plan
        self._log("phase4", "complete", "投資計畫已產出")
        return {"status": "success", "phase": 4, "plan": plan}

    def _build_picks(self, stocks: List[Dict], budget: float, horizon: str) -> List[Dict]:
        """建立單一投資組合配置"""
        if not stocks:
            return []
        per_stock_budget = budget / len(stocks)
        picks = []
        for s in stocks:
            shares = 0
            price = s.get("price")
            if price and price > 0:
                shares = int(per_stock_budget / price / 100) * 100
                if shares < 100:
                    shares = int(per_stock_budget / price)
            picks.append({
                "symbol": s["symbol"],
                "name": s.get("name", s["symbol"]),
                "price": price,
                "shares": shares,
                "estimated_cost": round(shares * price * 1.003, 2) if price else 0,
                "signal": s.get("signal"),
                "confidence": s.get("confidence"),
                "reason": s.get("reason", ""),
                "themes": s.get("themes", []),
            })
        return picks

    # ── 完整執行 ──

    def run_full_pipeline(self, budget: float = 1000000,
                           search_news_fn: Optional[Callable] = None,
                           fetch_stock_info_fn: Optional[Callable] = None,
                           fetch_stock_price_fn: Optional[Callable] = None,
                           analyze_fn: Optional[Callable] = None,
                           strategy_name: str = "combined",
                           use_debate: bool = False) -> Dict:
        """
        完整四階段執行。

        v2.0 新增：
          use_debate: True 時使用辯論引擎（Phase 1 四角色辯論），False 用關鍵字匹配
        """
        if use_debate:
            p1 = self.phase1_debate_discover_themes(
                search_news_fn=search_news_fn,
                force_debate=False,  # LLM 不可用時自動退回
            )
        else:
            p1 = self.phase1_discover_themes(search_news_fn=search_news_fn)

        if p1.get("status") != "success":
            return {"status": "error", "phase": 1, "detail": p1}

        p2 = self.phase2_screen_candidates(
            fetch_stock_info_fn=fetch_stock_info_fn,
            fetch_stock_price_fn=fetch_stock_price_fn,
        )
        if p2.get("status") != "success":
            return {"status": "error", "phase": 2, "detail": p2}

        p3 = self.phase3_technical_review(
            analyze_fn=analyze_fn,
            strategy_name=strategy_name,
        )
        if p3.get("status") != "success":
            return {"status": "error", "phase": 3, "detail": p3}

        p4 = self.phase4_generate_plan(budget=budget)

        return {
            "status": "success",
            "pipeline_complete": True,
            "phase1": p1,
            "phase2": p2,
            "phase3": p3,
            "phase4": p4,
            "log": self.log[-10:],
            "timestamp": datetime.now().isoformat(),
        }

    # ── Mission-Aware 執行 ──

    def run_mission_aware(self,
                          risk_level: str = "medium",
                          time_pressure: float = 1.0,
                          remaining_days: int = 90,
                          preferred_market: str = "TW",
                          max_positions: int = 5,
                          stop_loss_pct: float = 0.05,
                          take_profit_pct: float = 0.15,
                          search_news_fn: Optional[Callable] = None,
                          fetch_stock_info_fn: Optional[Callable] = None,
                          fetch_stock_price_fn: Optional[Callable] = None,
                          analyze_fn: Optional[Callable] = None,
                          budget: float = 1000000,
                          use_debate: bool = False) -> Dict:
        """
        Mission-Aware 完整執行：根據任務參數動態調整策略。

        v2.0 新增：
          use_debate: True 時 Phase 1 使用四角色辯論引擎
        """
        self._log("mission_aware", "start",
                   f"風險={risk_level}, 壓力={time_pressure:.2f}, 剩餘={remaining_days}天, "
                   f"辯論={'開' if use_debate else '關'}")

        strategy_name = self._pick_strategy(risk_level, time_pressure)
        min_cap = self._calc_min_market_cap(risk_level, time_pressure)
        max_pe = self._calc_max_pe(risk_level, time_pressure)

        extra_prompts = []
        if preferred_market in ("TW", "ALL"):
            extra_prompts.extend([
                "2026 台股 熱門題材 強勢股 趨勢",
                "2026 台灣股市 利多 產業輪動",
            ])
        if preferred_market in ("US", "ALL"):
            extra_prompts.extend([
                "2026 US stock market hot sectors trends",
                "2026 Nasdaq growth stocks momentum",
            ])
        if risk_level in ("high", "extreme"):
            extra_prompts.append("2026 飆股 強勢突破 短線 籌碼集中")
        if time_pressure > 2.0:
            extra_prompts.append("2026 短線 動能 爆發 題材股")

        # ── Phase 1 ──
        if use_debate:
            p1 = self.phase1_debate_discover_themes(
                search_news_fn=search_news_fn,
                extra_prompts=extra_prompts,
                force_debate=False,
            )
        else:
            p1 = self.phase1_discover_themes(
                search_news_fn=search_news_fn,
                extra_prompts=extra_prompts,
            )

        if p1.get("status") != "success":
            return {"status": "error", "phase": 1, "detail": p1}

        # ── Phase 2 ──
        p2 = self.phase2_screen_candidates(
            fetch_stock_info_fn=fetch_stock_info_fn,
            fetch_stock_price_fn=fetch_stock_price_fn,
            min_market_cap_billion=min_cap,
            max_pe=max_pe,
        )
        if p2.get("status") != "success":
            return {"status": "error", "phase": 2, "detail": p2}

        # ── Phase 3 ──
        p3 = self.phase3_technical_review(
            analyze_fn=analyze_fn,
            strategy_name=strategy_name,
        )

        # ── Phase 4 ──
        if time_pressure > 2.0:
            short_pct, mid_pct, long_pct = 0.50, 0.35, 0.15
        elif time_pressure > 1.0:
            short_pct, mid_pct, long_pct = 0.35, 0.40, 0.25
        else:
            short_pct, mid_pct, long_pct = 0.25, 0.45, 0.30

        p4 = self._generate_mission_plan(
            budget=budget,
            max_positions=max_positions,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            time_pressure=time_pressure,
            short_pct=short_pct,
            mid_pct=mid_pct,
            long_pct=long_pct,
        )

        self._log("mission_aware", "complete",
                   f"策略={strategy_name}, 篩選={len(self.screened)}支, "
                   f"辯論={'開' if use_debate else '關'}")

        return {
            "status": "success",
            "pipeline_complete": True,
            "risk_level": risk_level,
            "time_pressure": time_pressure,
            "strategy_used": strategy_name,
            "min_market_cap_billion": min_cap,
            "max_pe": max_pe,
            "use_debate": use_debate,
            "phase1": p1,
            "phase2": p2,
            "phase3": p3,
            "phase4": p4,
            "log": self.log[-10:],
            "timestamp": datetime.now().isoformat(),
        }

    def _pick_strategy(self, risk_level: str, time_pressure: float) -> str:
        if risk_level == "extreme" or time_pressure > 2.5:
            return "combined"
        elif risk_level == "high" or time_pressure > 1.2:
            return "combined"
        elif risk_level == "low" or time_pressure < 0.4:
            return "ma_crossover"
        else:
            return "adaptive"

    @staticmethod
    def _calc_min_market_cap(risk_level: str, time_pressure: float) -> float:
        base = {"extreme": 0.1, "high": 0.3, "medium": 1.0, "low": 3.0}.get(risk_level, 1.0)
        return round(base / max(time_pressure, 0.2), 2)

    @staticmethod
    def _calc_max_pe(risk_level: str, time_pressure: float) -> float:
        base = {"extreme": 100, "high": 60, "medium": 40, "low": 25}.get(risk_level, 40)
        return round(base * max(time_pressure, 0.5))

    def _generate_mission_plan(self,
                                budget: float,
                                max_positions: int,
                                stop_loss_pct: float,
                                take_profit_pct: float,
                                time_pressure: float,
                                short_pct: float = 0.25,
                                mid_pct: float = 0.45,
                                long_pct: float = 0.30) -> Dict:
        self._log("phase4", "start", f"Mission 預算: ${budget:,.0f}")

        buy_list = [s for s in self.screened if s.get("signal") == "BUY"]
        hold_list = [s for s in self.screened if s.get("signal") == "HOLD"]

        if not buy_list:
            buy_list = hold_list[:4]
            hold_list = hold_list[4:]

        max_picks = min(max_positions, len(buy_list) + len(hold_list))

        short_term_budget = budget * short_pct
        mid_term_budget = budget * mid_pct
        long_term_budget = budget * long_pct

        sl_mult = min(2.0, max(1.0, time_pressure))
        tp_mult = min(2.5, max(1.0, time_pressure * 1.2))

        plan = {
            "budget": budget,
            "generated_at": datetime.now().isoformat(),
            "active_themes": self.active_themes,
            "time_pressure": time_pressure,
            "max_positions": max_positions,

            "short_term": {
                "description": "短期波段 (1-4 週)，高流動性、技術面強勢",
                "budget": round(short_term_budget, 2),
                "stop_loss_pct": round(stop_loss_pct * 100 * sl_mult, 1),
                "take_profit_pct": round(take_profit_pct * 100 * tp_mult, 1),
                "picks": self._build_picks(buy_list[:max(1, max_picks // 3)], short_term_budget, "short"),
            },
            "mid_term": {
                "description": "中期趨勢 (1-3 月)，基本面 + 技術面並重",
                "budget": round(mid_term_budget, 2),
                "stop_loss_pct": round(stop_loss_pct * 100 * sl_mult * 0.8, 1),
                "take_profit_pct": round(take_profit_pct * 100 * tp_mult, 1),
                "picks": self._build_picks(buy_list[max(1, max_picks // 3):max(2, max_picks * 2 // 3)], mid_term_budget, "mid"),
            },
            "long_term": {
                "description": "長期布局 (3-12 月)，產業趨勢明確",
                "budget": round(long_term_budget, 2),
                "stop_loss_pct": round(stop_loss_pct * 100 * sl_mult * 0.6, 1),
                "take_profit_pct": round(take_profit_pct * 100 * tp_mult * 1.5, 1),
                "picks": self._build_picks(buy_list[max(2, max_picks * 2 // 3):max_picks] + hold_list[:2], long_term_budget, "long"),
            },
        }

        self.current_plan = plan
        self._log("phase4", "complete", "Mission 投資計畫已產出")
        return {"status": "success", "phase": 4, "plan": plan}

    # ── 輔助 ──

    def _log(self, phase: str, event: str, detail: str):
        entry = {
            "phase": phase,
            "event": event,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        self.log.append(entry)

    def get_log(self, limit: int = 50) -> List[Dict]:
        return self.log[-limit:]

    def get_plan(self) -> Optional[Dict]:
        return self.current_plan

    def get_debate_transcript(self) -> Optional[Dict]:
        """取得最近一次辯論的完整逐字稿"""
        return self.last_debate_transcript

    def get_debate_history(self, limit: int = 20) -> List[Dict]:
        """取得辯論歷史記錄（最近 N 筆）"""
        return self.debate_history[-limit:] if self.debate_history else []


# ─── 模組級實例 ───
_agent_instance: Optional[AutonomousInvestmentAgent] = None


def get_agent() -> AutonomousInvestmentAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AutonomousInvestmentAgent()
    return _agent_instance


def reset_agent():
    global _agent_instance
    _agent_instance = AutonomousInvestmentAgent()
