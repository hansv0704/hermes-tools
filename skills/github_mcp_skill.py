import os
import json
import httpx
import logging
from skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

class GithubMCPSkill(BaseSkill):
    """透過 GitHub 官方的遠端 MCP API 來擴展 GitHub 操作能力"""
    
    MCP_ENDPOINT = "https://api.githubcopilot.com/mcp/"
    
    def __init__(self, agent=None):
        super().__init__(agent)
        self.token = os.getenv("GITHUB_PAT")
        self._client = None
        self._mcp_tools = []
        self._initialized = False
    
    @property
    def name(self):
        return "github_mcp_skill"
    
    def get_tool_declarations(self):
        return [
            {
                "name": "github_mcp_call",
                "description": "通用 GitHub MCP 工具呼叫介面。先使用 github_list_mcp_tools 查看可用的工具清單，再呼叫特定工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "要呼叫的 GitHub 工具名稱（從 github_list_mcp_tools 取得）"
                        },
                        "arguments": {
                            "type": "object",
                            "description": "傳遞給工具的參數"
                        }
                    },
                    "required": ["tool_name"]
                }
            },
            {
                "name": "github_list_mcp_tools",
                "description": "列出 GitHub MCP Server 目前提供的所有可用工具",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    async def _init_client(self):
        if self._initialized and self._client:
            return True
        if not self.token:
            logger.warning("GitHub MCP: 未設定 GITHUB_PAT")
            return False
        try:
            self._client = httpx.AsyncClient(timeout=30.0)
            # JSON-RPC 初始化握手
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "clientInfo": {"name": "Alice", "version": "1.0.0"},
                    "capabilities": {}
                }
            }
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "vscode://",
                "User-Agent": "VS Code/1.101.0"
            }
            resp = await self._client.post(self.MCP_ENDPOINT, json=init_req, headers=headers)
            if resp.status_code == 200:
                # 通知伺服器初始化完成
                notify_req = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                }
                await self._client.post(self.MCP_ENDPOINT, json=notify_req, headers=headers)
                self._initialized = True
                return True
            return False
        except Exception as e:
            logger.error(f"GitHub MCP 初始化失敗: {e}")
            return False
    
    async def _list_tools(self):
        if not await self._init_client():
            return []
        try:
            req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "vscode://",
                "User-Agent": "VS Code/1.101.0"
            }
            resp = await self._client.post(self.MCP_ENDPOINT, json=req, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                self._mcp_tools = data.get("result", {}).get("tools", [])
                return self._mcp_tools
            return []
        except Exception as e:
            logger.error(f"GitHub MCP 列出工具失敗: {e}")
            return []
    
    async def execute(self, tool_name, params, context=None, **kwargs):
        if not self.token:
            return {"status": "error", "message": "GitHub MCP: 未設定 GITHUB_PAT 環境變數"}
        
        if tool_name == "github_list_mcp_tools":
            tools = await self._list_tools()
            if tools:
                return {"status": "success", "tools": tools, "count": len(tools)}
            return {"status": "error", "message": "無法獲取 GitHub MCP 工具清單"}
        
        if tool_name == "github_mcp_call":
            target_tool = params.get("tool_name")
            arguments = params.get("arguments", {})
            
            if not await self._init_client():
                return {"status": "error", "message": "GitHub MCP 初始化失敗"}
            
            try:
                req = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": target_tool,
                        "arguments": arguments
                    }
                }
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "vscode://",
                    "User-Agent": "VS Code/1.101.0"
                }
                resp = await self._client.post(self.MCP_ENDPOINT, json=req, headers=headers)
                if resp.status_code == 200:
                    result = resp.json()
                    return {"status": "success", "result": result}
                return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        return {"status": "error", "message": f"未知的 GitHub MCP 工具: {tool_name}"}
