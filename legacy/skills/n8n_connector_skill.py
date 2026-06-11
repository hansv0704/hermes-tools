"""
n8n Connector Skill — Alice ↔ n8n Webhook 雙向通訊
- 觸發 n8n 工作流（POST Webhook）
- 列出活躍 Webhook
- 未來擴充：自動註冊工作流模板
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List

# ─── BaseSkill 雙重匯入（相容 tools.py 的 sys.path）───
try:
    from skills.base_skill import BaseSkill
except ImportError:
    from base_skill import BaseSkill


BASE_DIR = Path(__file__).resolve().parent.parent
N8N_URL = "http://localhost:5678"
N8N_API_KEY = os.getenv("N8N_API_KEY", "")


# ─── 工具函式 ─────────────────────────────────────────────

def _http_request(method: str, path: str, data: Optional[Dict] = None,
                  timeout: int = 15) -> Dict[str, Any]:
    """對 n8n REST API 發送 HTTP 請求"""
    url = f"{N8N_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY

    body = None
    if data:
        body = json.dumps(data).encode('utf-8')

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_data = resp.read().decode('utf-8')
            return {
                "success": True,
                "status_code": resp.status,
                "data": json.loads(response_data) if response_data else {}
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        return {
            "success": False,
            "status_code": e.code,
            "error": f"HTTP {e.code}: {e.reason}",
            "detail": error_body[:500]
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"無法連線到 n8n：{str(e.reason)}",
            "hint": "請確認 n8n 伺服器是否正在運行（可透過 start_n8n_server 啟動）"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"請求失敗：{str(e)}"
        }


def _trigger_webhook(webhook_path: str, payload: Optional[Dict] = None,
                     method: str = "POST") -> Dict[str, Any]:
    """觸發 n8n Webhook 工作流"""
    if not webhook_path.startswith('/'):
        webhook_path = f'/webhook/{webhook_path}'
    elif not webhook_path.startswith('/webhook/'):
        webhook_path = f'/webhook{webhook_path}'

    return _http_request(method.upper(), webhook_path, data=payload)


def _list_webhooks() -> Dict[str, Any]:
    """列出 n8n 中所有活躍的 Webhook 工作流"""
    result = _http_request("GET", "/rest/workflows")

    if not result.get("success"):
        return result

    workflows = result.get("data", {}).get("data", [])
    active_webhooks = []

    for wf in workflows:
        if wf.get("active"):
            webhook_nodes = []
            for node in wf.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    webhook_nodes.append({
                        "name": node.get("name"),
                        "path": node.get("parameters", {}).get("path", "N/A"),
                        "method": node.get("parameters", {}).get("httpMethod", "POST")
                    })
            if webhook_nodes:
                active_webhooks.append({
                    "id": wf.get("id"),
                    "name": wf.get("name"),
                    "active": wf.get("active"),
                    "webhooks": webhook_nodes
                })

    return {
        "success": True,
        "total_workflows": len(workflows),
        "active_webhook_count": len(active_webhooks),
        "webhooks": active_webhooks
    }


# ─── Skill 類別 ─────────────────────────────────────────────

class N8nConnectorSkill(BaseSkill):
    """Alice ↔ n8n Webhook 雙向通訊 Skill"""

    def __init__(self, agent=None):
        super().__init__(agent)

    @property
    def name(self) -> str:
        return "n8n_connector_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "n8n_trigger_webhook",
                "description": "【觸發 n8n 工作流】透過 Webhook 觸發 n8n 中的自動化工作流。傳入路徑與 JSON 資料。常用路徑：github-daily-digest（每日 GitHub 獵頭）、emergency-notify（多管道緊急通知）、alice-webhook-receiver（Alice 觸發接收端點）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "webhook_path": {
                            "type": "string",
                            "description": "Webhook 路徑（例如 'github-daily-digest' 或 '/webhook/emergency-notify'）"
                        },
                        "payload": {
                            "type": "object",
                            "description": "要傳送的 JSON 資料（選填）"
                        },
                        "method": {
                            "type": "string",
                            "enum": ["POST", "GET"],
                            "description": "HTTP 方法，預設 POST",
                            "default": "POST"
                        }
                    },
                    "required": ["webhook_path"]
                }
            },
            {
                "name": "n8n_list_webhooks",
                "description": "【列出 n8n Webhook】列出 n8n 伺服器中所有活躍的 Webhook 工作流及其端點資訊。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute(self, function_name: str, args: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if function_name == "n8n_trigger_webhook":
            webhook_path = args.get("webhook_path", "")
            payload = args.get("payload")
            method = args.get("method", "POST")
            return _trigger_webhook(webhook_path, payload, method)
        elif function_name == "n8n_list_webhooks":
            return _list_webhooks()
        else:
            return {"success": False, "error": f"未知的 n8n connector 操作：{function_name}"}
