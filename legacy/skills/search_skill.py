import asyncio
import httpx
import json
import os
import re
import random
import inspect
from typing import List, Dict, Any, Optional
from datetime import datetime
from skills.base_skill import BaseSkill
from bs4 import BeautifulSoup
from config import logger

class SearchSkill(BaseSkill):
    def __init__(self, agent=None):
        super().__init__(agent)
        # Scira 風格：SearXNG 公共實例叢集
        self.searxng_instances = [
            "https://searx.be",
            "https://search.mdosch.de",
            "https://priv.au",
            "https://searx.info",
            "https://northboot.xyz"
        ]
        
        # 智慧偽裝層：User-Agent 列表
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"
        ]
        

    @property
    def name(self) -> str:
        return "search_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "web_search",
                "description": "【Scira 終極搜尋】執行即時連網搜尋，獲取真實世界最新的新聞、技術動態或資料。支援多引擎並行聚合與智慧偽裝。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "搜尋關鍵字清單 (建議 1-3 個相關查詢以增加覆蓋面)"
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 5,
                            "description": "每個查詢回傳的結果數量"
                        }
                    },
                    "required": ["queries"]
                }
            }
        ]

    async def execute(self, tool_name: str, params: Dict[str, Any], context: Any = None, **kwargs) -> Dict[str, Any]:
        if tool_name == "web_search":
            queries = params.get("queries", [])
            if isinstance(queries, str): queries = [queries]
            max_results = params.get("max_results", 5)
            
            # A3: 查詢預處理 — 中文查詢自動生成英文版（DeepCode 移植）
            expanded_queries = self._preprocess_queries(queries)
            
            results, errors = await self._multi_provider_search(expanded_queries, max_results)
            return {"status": "success", "results": results, "errors": errors, "engine": "Scira-Multi-Provider-v8.0"}
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    def _preprocess_queries(self, queries: List[str]) -> List[str]:
        """查詢預處理：中文查詢自動生成英文版以提高命中率（DeepCode 移植）

        DeepCode 的 webSearchTool 核心機制之一就是在搜尋前用 LLM 判斷語言並翻譯。
        我們在 client 端做輕量版：偵測中文 → 提取英數關鍵字 → 雙軌並行。
        """
        expanded = list(queries)
        for q in queries:
            if re.search(r'[\u4e00-\u9fff]', q):
                en_keywords = re.findall(r'[A-Za-z0-9]+', q)
                if en_keywords:
                    en_query = ' '.join(en_keywords)
                    if en_query not in expanded:
                        expanded.append(en_query)
        return expanded

    async def _multi_provider_search(self, queries: List[str], max_results: int):
        """多 Provider 並行搜尋，回傳 (results, errors)"""
        all_results = []
        all_errors = []
        
        for query in queries:
            tasks = []
            task_sources = []
            
            # 1. DDG HTML (主力，使用 /html/ 端點，反爬寬容度高)
            tasks.append(self._ddg_html_search(query, max_results))
            task_sources.append("DDG-HTML")
            
            # 2. SearXNG 公共實例 (備援標記，目前全掛)
            tasks.append(self._searxng_competitive_search(query, max_results))
            task_sources.append("SearXNG")

            # 並行執行所有 Provider，設定 8 秒超時
            completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task_result, source in zip(completed_tasks, task_sources):
                if isinstance(task_result, Exception):
                    all_errors.append(f"[{source}] 例外: {task_result}")
                elif isinstance(task_result, tuple):
                    # SearXNG 回傳 (results, errors)
                    results, errs = task_result
                    all_results.extend(results)
                    all_errors.extend(errs)
                elif isinstance(task_result, list):
                    if task_result:
                        all_results.extend(task_result)
                    else:
                        all_errors.append(f"[{source}] 回傳空結果 (查詢: {query[:40]}...)")
        
        # 去重與清洗
        return self._deduplicate_and_clean(all_results, max_results * len(queries)), all_errors

    # ─── DDG HTML：直接請求 duckduckgo.com/html/ 無 JS 純 HTML 版 ───
    async def _ddg_html_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """DDG HTML 搜尋：使用 duckduckgo.com/html/ 無 JS 純 HTML 版
        
        模仿 oevortex/ddg_search (Node.js) 的成功架構。HTML 版端點對反爬
        的寬容度遠高於 Lite 版（後者已被實證攔截，HTTP 202 cc=botnet）。
        CSS 選擇器：.result__title a (標題+URL) / .result__snippet (摘要)
        """
        try:
            from urllib.parse import urlparse, parse_qs, unquote
            
            url = "https://duckduckgo.com/html/"
            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }
            params = {"q": query}
            
            async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"[DDG-HTML] HTTP {resp.status_code}")
                    return []
                
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                
                for result_el in soup.select(".result__body"):
                    title_el = result_el.select_one(".result__title a")
                    snippet_el = result_el.select_one(".result__snippet")
                    
                    if title_el:
                        title = title_el.get_text(strip=True)
                        href = title_el.get("href", "")
                        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                        
                        # 解碼 DDG 重導向連結 (/l/?uddg=... → 真實 URL)
                        direct_url = href
                        if '/l/?uddg=' in href or 'uddg=' in href:
                            parsed = urlparse(href)
                            qs_params = parse_qs(parsed.query)
                            uddg_val = qs_params.get('uddg', [None])[0]
                            if uddg_val:
                                direct_url = unquote(uddg_val)
                        elif href.startswith('//'):
                            direct_url = 'https:' + href
                        
                        results.append({
                            "title": title,
                            "link": direct_url,
                            "snippet": snippet,
                            "source": "ddg"
                        })
                    
                    if len(results) >= max_results:
                        break
                
                return results
                
        except Exception as e:
            logger.warning(f"[DDG-HTML] 搜尋失敗: {e}")
            return []



    # ─── SearXNG 競爭式搜尋（備援） ───
    async def _searxng_competitive_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        # 隨機挑選 3 個實例進行競爭
        instances = random.sample(self.searxng_instances, 3)
        tasks = [self._fetch_searxng(inst, query, max_results) for inst in instances]
        
        # 取最快回傳且非空的結果
        errors = []
        for completed in asyncio.as_completed(tasks):
            try:
                res = await completed
                if res: return res, errors
            except Exception as e:
                errors.append(f"[SearXNG] 實例連線失敗: {e}")
                continue
        return [], errors

    async def _fetch_searxng(self, instance: str, query: str, max_results: int) -> List[Dict[str, Any]]:
        url = f"{instance}/search"
        params = {"q": query, "format": "json", "engines": "google,bing,wikipedia"}
        headers = {"User-Agent": random.choice(self.user_agents)}
        async with httpx.AsyncClient(timeout=4.0, headers=headers, verify=False) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return [{"title": item.get("title"), "link": item.get("url"), "snippet": item.get("content"), "source": "searxng"} 
                        for item in data.get("results", [])[:max_results]]
            else:
                logger.warning(f"[SearXNG] {instance} 回傳 HTTP {resp.status_code}")
        return []

    def _deduplicate_and_clean(self, results: List[Dict], limit: int) -> List[Dict]:
        seen_links = set()
        unique_results = []
        for r in results:
            link = r.get("link")
            if link and link not in seen_links:
                seen_links.add(link)
                # 清洗標題 (參考 Scira)
                r["title"] = re.sub(r"\s*[\(\[].*?[\)\]]\s*", "", r.get("title", ""))
                unique_results.append(r)
        return unique_results[:limit]
