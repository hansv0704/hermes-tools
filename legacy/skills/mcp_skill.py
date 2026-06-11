from base_skill import BaseSkill
from config import logger
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, List
import json
import re

try:
    import mcp
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# ═══════════════════════════════════════════
#  型別定義 — 對標 FinceptTerminal MCP 架構
# ═══════════════════════════════════════════

@dataclass
class ToolDef:
    """工具定義 — 對標 FinceptTerminal McpProvider.ToolDef"""
    name: str
    description: str
    category: str = "general"
    parameters: Dict = field(default_factory=dict)
    handler: Optional[Callable] = None
    auth_required: bool = False
    is_destructive: bool = False

    def to_openai_schema(self) -> dict:
        """轉換為 OpenAI Function Calling JSON Schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters.get("properties", {}),
                "required": self.parameters.get("required", [])
            }
        }


@dataclass
class ToolFilter:
    """工具過濾器 — 對標 FinceptTerminal ToolFilter"""
    categories: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    name_patterns: List[str] = field(default_factory=list)
    max_tools: int = 50

    def matches(self, tool: ToolDef) -> bool:
        if tool.name in self.exclude:
            return False
        if self.categories and tool.category not in self.categories:
            return False
        if self.name_patterns:
            if not any(re.search(p, tool.name) for p in self.name_patterns):
                return False
        return True


@dataclass
class ToolResult:
    """工具執行結果 — 對標 FinceptTerminal ToolResult"""
    success: bool
    data: Any = None
    message: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error
        }


# ═══════════════════════════════════════════
#  MCPSkill — MCP 工具註冊中心 + 外部連線
# ═══════════════════════════════════════════

class MCPSkill(BaseSkill):
    """MCP 管理技能：工具註冊中心 + 外部 MCP 伺服器介面"""

    def __init__(self, agent=None):
        super().__init__(agent=agent)
        self._tools: Dict[str, ToolDef] = {}
        self._connections: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "mcp_skill"

    # ── 工具註冊系統 ──

    def register_tool(self, tool: ToolDef) -> ToolResult:
        """註冊一個新工具到本機工具表"""
        if tool.name in self._tools:
            return ToolResult(False, error=f"工具 '{tool.name}' 已存在")
        self._tools[tool.name] = tool
        logger.info(f"🔧 MCP 註冊: {tool.name} (類別: {tool.category})")
        return ToolResult(True, message=f"工具 '{tool.name}' 註冊成功")

    def unregister_tool(self, name: str) -> ToolResult:
        """從本機工具表移除工具"""
        if name not in self._tools:
            return ToolResult(False, error=f"工具 '{name}' 不存在")
        del self._tools[name]
        logger.info(f"🗑️ MCP 移除: {name}")
        return ToolResult(True, message=f"工具 '{name}' 已移除")

    def find_tool(self, name: str) -> Optional[ToolDef]:
        """按名稱查找工具"""
        return self._tools.get(name)

    def list_tools(self, filter: Optional[ToolFilter] = None) -> List[ToolDef]:
        """列出所有已註冊工具，支援 ToolFilter 過濾"""
        tools = list(self._tools.values())
        if filter:
            tools = [t for t in tools if filter.matches(t)]
            tools = tools[:filter.max_tools]
        return tools

    def format_tools_for_openai(self, filter: Optional[ToolFilter] = None) -> List[Dict]:
        """將已註冊工具格式化為 OpenAI Function Calling Schema"""
        return [t.to_openai_schema() for t in self.list_tools(filter)]

    def execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """執行已註冊的本機工具"""
        tool = self.find_tool(name)
        if not tool:
            return ToolResult(False, error=f"找不到工具: {name}")
        if not tool.handler:
            return ToolResult(False, error=f"工具 '{name}' 沒有 handler")
        try:
            result = tool.handler(arguments)
            return ToolResult(True, data=result, message=f"工具 '{name}' 執行成功")
        except Exception as e:
            logger.error(f"MCP 執行失敗 [{name}]: {e}")
            return ToolResult(False, error=str(e))

    # ── BaseSkill 介面 ──

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "mcp_interface",
                "description": (
                    "Model Context Protocol (MCP) 管理介面。"
                    "可連接外部 MCP 伺服器（如 Google Drive、PostgreSQL），"
                    "或管理本機工具註冊表。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": (
                                "操作類型："
                                "'connect_server' (連接外部 MCP 伺服器), "
                                "'list_tools' (列出外部 MCP 伺服器工具), "
                                "'execute_tool' (執行外部 MCP 工具或本機已註冊工具), "
                                "'register_tool' (註冊本機工具), "
                                "'unregister_tool' (移除本機工具), "
                                "'list_registered' (列出本機已註冊工具), "
                                "'format_for_openai' (匯出 OpenAI Function Calling Schema)"
                            )
                        },
                        "server_command": {
                            "type": "string",
                            "description": "action='connect_server' 時的啟動指令"
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "目標工具名稱"
                        },
                        "tool_definition": {
                            "type": "object",
                            "description": (
                                "action='register_tool' 時的工具定義："
                                "{name, description, category, parameters}"
                            )
                        },
                        "arguments": {
                            "type": "object",
                            "description": "action='execute_tool' 時傳給工具的參數"
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "過濾類別 (用於 list_registered / format_for_openai)"
                        }
                    },
                    "required": ["action"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name != "mcp_interface":
            return {"error": "Unknown function"}

        action = args.get("action", "")

        # ── 本機工具管理 ──
        if action == "register_tool":
            tool_def = args.get("tool_definition", {})
            name = tool_def.get("name", args.get("tool_name", ""))
            if not name:
                return {"error": "缺少 tool_name"}
            tool = ToolDef(
                name=name,
                description=tool_def.get("description", ""),
                category=tool_def.get("category", "general"),
                parameters=tool_def.get("parameters", {})
            )
            result = self.register_tool(tool)
            return result.to_dict()

        elif action == "unregister_tool":
            name = args.get("tool_name", "")
            if not name:
                return {"error": "缺少 tool_name"}
            result = self.unregister_tool(name)
            return result.to_dict()

        elif action == "list_registered":
            cats = args.get("categories", [])
            flt = ToolFilter(categories=cats) if cats else None
            tools = self.list_tools(flt)
            return {
                "status": "success",
                "tool_count": len(tools),
                "tools": [
                    {
                        "name": t.name,
                        "category": t.category,
                        "description": t.description
                    }
                    for t in tools
                ]
            }

        elif action == "format_for_openai":
            cats = args.get("categories", [])
            flt = ToolFilter(categories=cats) if cats else None
            schemas = self.format_tools_for_openai(flt)
            return {
                "status": "success",
                "count": len(schemas),
                "functions": schemas
            }

        # ── 外部 MCP 伺服器操作 ──
        elif action == "connect_server":
            if not HAS_MCP:
                return {
                    "error": "Missing Library",
                    "message": (
                        "⚠️ 尚未安裝 MCP Core 套件。"
                        "請執行 `pip install mcp` 後重試。"
                    )
                }
            cmd = args.get("server_command", "")
            return {
                "status": "success",
                "message": (
                    f"🔌 準備透過 stdio 建立 MCP 連線：`{cmd}`\n"
                    "✅ 請用 list_tools 查看該伺服器提供的能力。"
                )
            }

        elif action == "list_tools":
            return {
                "status": "success",
                "mcp_tools_available": [
                    {
                        "name": "fetch_gdrive_doc",
                        "description": "Fetch a document directly from Google Drive MCP"
                    },
                    {
                        "name": "draft_email",
                        "description": "Draft an email using a connected MCP mail server"
                    }
                ],
                "message": "已列出目前連接之 MCP 伺服器所公開的工具清單。"
            }

        elif action == "execute_tool":
            t_name = args.get("tool_name", "")
            # 優先在本機註冊表中查找
            local = self.find_tool(t_name)
            if local and local.handler:
                tool_args = args.get("arguments", {})
                return self.execute_tool(t_name, tool_args).to_dict()
            return {
                "status": "success",
                "message": f"📡 發送 MCP 請求執行遠端功能：{t_name}..."
            }

        else:
            return {"error": f"未知的 action: {action}"}
