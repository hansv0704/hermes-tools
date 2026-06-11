from skills.base_skill import BaseSkill
import os
import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger(__name__)

class GithubIntegrationSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "github_integration_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "search_github_repositories",
                "description": "在 GitHub 上搜尋開源專案。可以用來尋找感興趣的工具、技能或 MCP Server。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜尋關鍵字，例如 'mcp server python' 或 'telegram bot'"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "回傳的專案數量，預設 5"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_github_repo_files",
                "description": "列出 GitHub 專案指定目錄下的檔案列表 (以便尋找你有興趣的 .py 檔案)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_full_name": {
                            "type": "string",
                            "description": "專案全名，例如 'modelcontextprotocol/python-sdk'"
                        },
                        "path": {
                            "type": "string",
                            "description": "目錄路徑，預設為空字串 (專案根目錄)。若要看特定資料夾可輸入 'src' 等"
                        }
                    },
                    "required": ["repo_full_name"]
                }
            },
            {
                "name": "fetch_github_file_content",
                "description": "從 GitHub 下載或讀取原始碼內容 (閱讀別人的程式碼，然後學習或抄襲)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "檔案網址 (可填 GitHub 一般網址或 raw.githubusercontent / api 提供的 download_url)"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "get_repo_info",
                "description": "獲取指定 GitHub 專案的詳細資訊（星數、語言比例、最近更新時間等）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_full_name": {
                            "type": "string",
                            "description": "專案全名，例如 'microsoft/playwright-mcp'"
                        }
                    },
                    "required": ["repo_full_name"]
                }
            },
            {
                "name": "get_user_info",
                "description": "獲取指定 GitHub 用戶或組織的公開資訊（倉庫數、追蹤者、貢獻熱度等）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "GitHub 用戶名稱或組織名稱"
                        }
                    },
                    "required": ["username"]
                }
            },
            {
                "name": "search_code",
                "description": "在 GitHub 全站搜尋程式碼內容（類似 grep 但跨所有公開倉庫）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜尋的程式碼關鍵字"
                        },
                        "language": {
                            "type": "string",
                            "description": "限制程式語言，例如 'python'、'javascript'"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "回傳筆數上限，預設 10"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_trending",
                "description": "模擬 GitHub Trending，搜尋最近一週內獲得最多星標的公開專案。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "language": {
                            "type": "string",
                            "description": "限制程式語言，例如 'python'"
                        },
                        "since": {
                            "type": "string",
                            "description": "時間範圍，可選 'daily'、'weekly'、'monthly'，預設 'weekly'"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "回傳專案數量，預設 10"
                        }
                    }
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "search_github_repositories":
            query = args.get("query", "")
            limit = args.get("limit", 5)
            if not query:
                return {"error": "Missing query"}
                
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&per_page={limit}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                    
                items = data.get("items", [])
                if not items:
                    return {"status": "success", "message": "沒有找到相關的專案。"}
                    
                result_text = f"在 GitHub 上為您找到以下專案 (搜尋 '{query}')：\n"
                for item in items:
                    result_text += f"- [{item['full_name']}]({item['html_url']}): {item['description']} (⭐ {item['stargazers_count']})\n"
                    
                return {"status": "success", "message": result_text}
            except Exception as e:
                return {"error": f"GitHub API Request Failed: {e}"}

        elif function_name == "list_github_repo_files":
            repo_full_name = args.get("repo_full_name", "")
            path = args.get("path", "")
            if not repo_full_name:
                return {"error": "Missing repo_full_name"}
            
            url = f"https://api.github.com/repos/{repo_full_name}/contents/{urllib.parse.quote(path)}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                
                if isinstance(data, list):
                    result_text = f"專案 {repo_full_name} 下的內容：\n"
                    for item in data:
                        type_icon = "📁" if item["type"] == "dir" else "📄"
                        dl_url = item.get('download_url')
                        dl_str = f", 下載網址: {dl_url}" if dl_url else ""
                        result_text += f"{type_icon} {item['path']} (類型: {item['type']}{dl_str})\n"
                    return {"status": "success", "message": result_text}
                elif isinstance(data, dict):
                    return {"status": "success", "message": f"{data.get('name')} 是一個單一檔案，請使用 fetch_github_file_content 讀取。"}
            except urllib.error.HTTPError as e:
                return {"error": f"HTTP Error {e.code}: 找不到資料夾或超出了 GitHub 匿名 API 限制"}
            except Exception as e:
                return {"error": f"Fetch list failed: {e}"}

        elif function_name == "fetch_github_file_content":
            url = args.get("url", "")
            if not url:
                return {"error": "Missing url"}
                
            # 將一般 github 網址轉換成 raw 網址以便抓取內容
            if "github.com" in url and "/blob/" in url:
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    content = response.read().decode('utf-8')
                    
                return {"status": "success", "message": content[:30000]} # 避免 Token 爆掉
            except Exception as e:
                return {"error": f"Fetch Failed: {e}"}

        elif function_name == "get_repo_info":
            repo_full_name = args.get("repo_full_name", "")
            if not repo_full_name:
                return {"error": "Missing repo_full_name"}
            url = f"https://api.github.com/repos/{repo_full_name}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                return {
                    "status": "success",
                    "message": f"專案 {repo_full_name} 的詳細資訊：\n"
                              f"星數：{data.get('stargazers_count', 'N/A')}\n"
                              f"Fork 數：{data.get('forks_count', 'N/A')}\n"
                              f"主要語言：{data.get('language', 'N/A')}\n"
                              f"最近更新：{data.get('updated_at', 'N/A')}\n"
                              f"描述：{data.get('description', 'N/A')}\n"
                              f"網址：{data.get('html_url', 'N/A')}"
                }
            except Exception as e:
                return {"error": f"Get repo info failed: {e}"}

        elif function_name == "get_user_info":
            username = args.get("username", "")
            if not username:
                return {"error": "Missing username"}
            url = f"https://api.github.com/users/{urllib.parse.quote(username)}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                return {
                    "status": "success",
                    "message": f"用戶 {username} 的公開資訊：\n"
                              f"名稱：{data.get('name', 'N/A')}\n"
                              f"公開倉庫數：{data.get('public_repos', 'N/A')}\n"
                              f"追蹤者：{data.get('followers', 'N/A')}\n"
                              f"追蹤中：{data.get('following', 'N/A')}\n"
                              f"簡介：{data.get('bio', 'N/A')}\n"
                              f"網址：{data.get('html_url', 'N/A')}"
                }
            except Exception as e:
                return {"error": f"Get user info failed: {e}"}

        elif function_name == "search_code":
            query = args.get("query", "")
            if not query:
                return {"error": "Missing query"}
            limit = args.get("limit", 10)
            language = args.get("language", "")
            q = query
            if language:
                q += f"+language:{language}"
            url = f"https://api.github.com/search/code?q={urllib.parse.quote(q)}&per_page={limit}"
            headers = {'User-Agent': 'Alice-Agent'}
            pat = os.environ.get("GITHUB_PAT")
            if pat:
                headers["Authorization"] = f"Bearer {pat}"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                items = data.get("items", [])
                if not items:
                    return {"status": "success", "message": "沒有找到相關的程式碼。"}
                result_text = f"在 GitHub 上搜尋程式碼 '{query}' 的結果：\n"
                for item in items:
                    result_text += f"- [{item['repository']['full_name']}]({item['html_url']}) ({item['repository']['stargazers_count']}⭐)\n"
                return {"status": "success", "message": result_text}
            except Exception as e:
                return {"error": f"Search code failed: {e}"}

        elif function_name == "get_trending":
            from datetime import datetime, timedelta
            language = args.get("language", "")
            since = args.get("since", "weekly")
            limit = args.get("limit", 10)
            days_map = {"daily": 1, "weekly": 7, "monthly": 30}
            days = days_map.get(since, 7)
            date_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            q = f"pushed:>={date_str} stars:>50"
            if language:
                q += f"+language:{language}"
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page={limit}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Alice-Agent'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                items = data.get("items", [])
                if not items:
                    return {"status": "success", "message": "沒有找到相關的趨勢專案。"}
                result_text = f"GitHub Trending ({since})：\n"
                for item in items:
                    result_text += f"- [{item['full_name']}]({item['html_url']}): {item['description']} (⭐ {item['stargazers_count']})\n"
                return {"status": "success", "message": result_text}
            except Exception as e:
                return {"error": f"Get trending failed: {e}"}

        return {"error": "Unknown function"}
