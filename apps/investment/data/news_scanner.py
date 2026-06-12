"""
投資代理人 v3.0 — 新聞掃描器
掃描市場新聞，提取潛在題材與情緒信號
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

log = logging.getLogger("investment.news")

# ═══════════════════════════════════════════════
#  新聞網站掃描
# ═══════════════════════════════════════════════

async def scan_twse_news() -> List[Dict]:
    """掃描證交所重大訊息"""
    try:
        import urllib.request
        import xml.etree.ElementTree as ET
        url = "https://mops.twse.com.tw/mops/web/ajax_t05sr01_1"
        # TWSE 可能需要更複雜的請求，使用簡化版
        return await _scan_yahoo_tw_news()
    except Exception:
        return await _scan_yahoo_tw_news()

async def _scan_yahoo_tw_news() -> List[Dict]:
    """掃描 Yahoo 財經新聞標題（作為備用）"""
    try:
        import yfinance as yf
        # 透過 yfinance 取得新聞
        tickers = ["^TWII", "2330.TW"]
        news_list = []
        for t in tickers:
            ticker = yf.Ticker(t)
            try:
                news = await asyncio.to_thread(lambda: ticker.news)
                for item in (news or [])[:10]:
                    content = item.get("content", {})
                    news_list.append({
                        "title": content.get("title", ""),
                        "summary": content.get("summary", "")[:200],
                        "url": content.get("canonicalUrl", {}).get("url", ""),
                        "source": content.get("provider", {}).get("displayName", ""),
                        "published_at": content.get("pubDate", ""),
                    })
            except Exception:
                pass
        # 去重
        seen = set()
        unique = []
        for n in news_list:
            if n["title"] not in seen:
                seen.add(n["title"])
                unique.append(n)
        return unique[:20]
    except Exception as e:
        log.warning(f"scan_yahoo_tw_news: {e}")
        return []

async def scan_cnyes_news() -> List[Dict]:
    """掃描鉅亨網新聞（簡化版）"""
    # 使用 web_extract 比較重，這裡先留空，由 Hermes layer 處理
    return []

# 對外公開的 Yahoo 新聞掃描
scan_yahoo_tw_news = _scan_yahoo_tw_news

# ═══════════════════════════════════════════════
#  題材/關鍵詞提取
# ═══════════════════════════════════════════════

# 常見台股題材關鍵詞
THEME_KEYWORDS = {
    "AI/伺服器": ["AI", "人工智慧", "伺服器", "GPU", "HPC", "資料中心", "GPU", "算力", "LLM", "大語言模型"],
    "半導體": ["晶圓", "半導體", "先進製程", "3奈米", "2奈米", "封裝", "CoWoS", "矽光子", "HBM"],
    "電動車": ["電動車", "EV", "電池", "自動駕駛", "鋰電池", "充電樁"],
    "綠能": ["太陽能", "風電", "儲能", "綠電", "碳權", "ESG", "碳中和"],
    "網通/5G": ["5G", "6G", "光通訊", "衛星", "低軌", "物聯網"],
    "生技": ["新藥", "生技", "醫材", "疫苗", "CDMO", "精準醫療"],
    "軍工": ["國防", "軍工", "飛彈", "無人機", "航太"],
    "重電": ["重電", "變壓器", "電網", "輸電", "配電"],
    "PCB": ["PCB", "載板", "HDI", "ABF", "軟板"],
    "被動元件": ["被動元件", "MLCC", "電容", "電阻", "電感"],
}

CONCEPT_STOCKS = {
    "AI/伺服器": ["2382", "2356", "2376", "2383", "3037", "2317", "6669", "3231", "2357"],
    "半導體":   ["2330", "2303", "3711", "2454", "3034", "3443", "3661", "5347"],
    "電動車":   ["2201", "2308", "2317", "2351", "3665", "3711"],
    "綠能":     ["1519", "3708", "6869", "6477", "6806", "1590"],
    "網通/5G":  ["2345", "6285", "3596", "5388", "3491", "6285"],
    "生技":     ["6550", "6589", "4147", "6472", "1795", "4123"],
    "軍工":     ["2634", "8033", "6285", "8222", "2645"],
    "重電":     ["1503", "1519", "6285", "9958"],
    "PCB":      ["3037", "2313", "2367", "6274", "3189", "8046"],
    "被動元件": ["2327", "2492", "3026", "6173"],
}

async def extract_themes_from_headlines(headlines: List[str]) -> Dict[str, List[str]]:
    """從新聞標題提取題材與相關標的"""
    themes_found = {}
    all_text = " ".join(headlines)

    for theme, keywords in THEME_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in all_text]
        if matches:
            themes_found[theme] = CONCEPT_STOCKS.get(theme, [])

    return themes_found

async def analyze_sentiment(texts: List[str]) -> Dict:
    """簡單情緒分析（關鍵詞匹配）"""
    bullish_words = ["飆", "漲停", "新高", "突破", "上修", "成長", "利多", "強勢", "翻倍", "爆發"]
    bearish_words = ["崩", "跌停", "新低", "下修", "衰退", "利空", "弱勢", "暴跌", "危機", "砍單"]

    bull_count = sum(1 for t in texts for w in bullish_words if w in t)
    bear_count = sum(1 for t in texts for w in bearish_words if w in t)

    if bull_count > bear_count:
        score = min(1.0, 0.5 + (bull_count - bear_count) * 0.1)
        sentiment = "bullish"
    elif bear_count > bull_count:
        score = max(-1.0, -0.5 - (bear_count - bull_count) * 0.1)
        sentiment = "bearish"
    else:
        score = 0.0
        sentiment = "neutral"

    return {"sentiment": sentiment, "score": score, "bullish_hits": bull_count, "bearish_hits": bear_count}
