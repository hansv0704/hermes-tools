import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from base_skill import BaseSkill

class DecisionLoggerSkill(BaseSkill):
    """
    【決策日誌系統 v1.1】
    記錄每次路由後的決策過程，包含選擇的工具、成功/失敗、主人的指正。
    儲存於 DuckDB，可供未來查詢與學習。
    修正：對齊資料庫表格名稱為 'decision_logs'。
    """

    @property
    def name(self) -> str:
        return "decision_logger_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "log_decision",
                "description": "【決策日誌】記錄一次路由後的決策過程，包含選擇的工具、成功/失敗、主人的指正。儲存於 DuckDB，作為訓練資料。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "原始任務描述"},
                        "routed_skills": {"type": "string", "description": "路由推薦的技能清單（逗號分隔）"},
                        "chosen_tool": {"type": "string", "description": "我實際選擇的工具名稱"},
                        "success": {"type": "boolean", "description": "是否執行成功"},
                        "reasoning": {"type": "string", "description": "我當時選擇的理由"},
                        "failure_reason": {"type": "string", "description": "若失敗，失敗原因（選填）"}
                    },
                    "required": ["task", "routed_skills", "chosen_tool", "success", "reasoning"]
                }
            },
            {
                "name": "query_decision_history",
                "description": "【決策日誌查詢】查詢過去的決策紀錄，用於學習與參考。可按任務類型或工具名稱過濾。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "任務類型過濾（選填，例如「數據分析」「檔案操作」）"},
                        "tool_name": {"type": "string", "description": "工具名稱過濾（選填，例如「excel_master_analyze」）"},
                        "limit": {"type": "integer", "description": "回傳筆數上限（預設 10）"}
                    }
                }
            },
            {
                "name": "update_decision_feedback",
                "description": "【決策日誌更新】更新一筆決策紀錄的主人的指正與建議，用於持續學習。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "description": "原始決策的時間戳記"},
                        "user_feedback": {"type": "string", "description": "主人的指正或建議"},
                        "lesson": {"type": "string", "description": "從中學到的教訓"}
                    },
                    "required": ["timestamp", "user_feedback", "lesson"]
                }
            }
        ]

    def _ensure_table(self, context: Dict) -> bool:
        """確保 DuckDB 中有決策日誌表格"""
        try:
            data_hub = context.get("tools")
            if data_hub and hasattr(data_hub, "execute_tool"):
                # 建立表格 (使用 decision_logs)
                data_hub.execute_tool("manage_data_hub", {
                    "action": "execute",
                    "sql": """CREATE TABLE IF NOT EXISTS decision_logs (
                        timestamp TEXT,
                        task TEXT,
                        routed_skills TEXT,
                        chosen_tool TEXT,
                        success BOOLEAN,
                        reasoning TEXT,
                        failure_reason TEXT,
                        user_feedback TEXT,
                        lesson TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                }, memory=context.get("memory"))
                return True
            return False
        except Exception as e:
            logging.error(f"❌ 確保決策日誌表格失敗: {e}")
            return False

    def execute(self, tool_name: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "log_decision":
            task = parameters.get("task", "")
            routed_skills = parameters.get("routed_skills", "")
            chosen_tool = parameters.get("chosen_tool", "")
            success = parameters.get("success", False)
            reasoning = parameters.get("reasoning", "")
            failure_reason = parameters.get("failure_reason", "")

            # 確保表格存在
            self._ensure_table(context)

            # 寫入 DuckDB
            try:
                data_hub = context.get("tools")
                if data_hub and hasattr(data_hub, "execute_tool"):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    data_hub.execute_tool("manage_data_hub", {
                        "action": "execute",
                        "sql": (
                            "INSERT INTO decision_logs (timestamp, task, routed_skills, chosen_tool, success, reasoning, failure_reason) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)"
                        ),
                        "params": [timestamp, task, routed_skills, chosen_tool, success, reasoning, failure_reason]
                    }, memory=context.get("memory"))

                    logging.info(f"📝 [決策日誌] {chosen_tool} → {'✅ 成功' if success else '❌ 失敗'}")
                    
                    return {
                        "status": "success",
                        "message": f"決策已記錄：{chosen_tool} → {'成功' if success else '失敗'}",
                        "data": {
                            "timestamp": timestamp,
                            "chosen_tool": chosen_tool,
                            "success": success
                        }
                    }
                else:
                    return {"status": "error", "message": "無法存取 DataHub"}
            except Exception as e:
                logging.error(f"❌ 記錄決策日誌失敗: {e}")
                return {"status": "error", "message": f"記錄失敗: {str(e)}"}

        elif tool_name == "query_decision_history":
            task_type = parameters.get("task_type", "")
            tool_name_filter = parameters.get("tool_name", "")
            limit = parameters.get("limit", 10)

            # 確保表格存在
            self._ensure_table(context)

            try:
                data_hub = context.get("tools")
                if data_hub and hasattr(data_hub, "execute_tool"):
                    where_clauses = []
                    params = []

                    if task_type:
                        where_clauses.append("task LIKE ?")
                        params.append(f"%{task_type}%")
                    if tool_name_filter:
                        where_clauses.append("chosen_tool = ?")
                        params.append(tool_name_filter)

                    where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
                    
                    result = data_hub.execute_tool("manage_data_hub", {
                        "action": "query",
                        "sql": f"SELECT * FROM decision_logs WHERE {where_str} ORDER BY timestamp DESC LIMIT {limit}"
                    }, memory=context.get("memory"))

                    if result and result.get("status") == "success":
                        rows = result.get("data", [])
                        return {
                            "status": "success",
                            "data": rows,
                            "message": f"查詢到 {len(rows)} 筆決策紀錄"
                        }
                    else:
                        return {"status": "success", "data": [], "message": "無決策紀錄"}
                else:
                    return {"status": "error", "message": "無法存取 DataHub"}
            except Exception as e:
                logging.error(f"❌ 查詢決策日誌失敗: {e}")
                return {"status": "error", "message": f"查詢失敗: {str(e)}"}

        elif tool_name == "update_decision_feedback":
            timestamp = parameters.get("timestamp", "")
            user_feedback = parameters.get("user_feedback", "")
            lesson = parameters.get("lesson", "")

            try:
                data_hub = context.get("tools")
                if data_hub and hasattr(data_hub, "execute_tool"):
                    data_hub.execute_tool("manage_data_hub", {
                        "action": "execute",
                        "sql": "UPDATE decision_logs SET user_feedback = ?, lesson = ? WHERE timestamp = ?"
                    }, memory=context.get("memory"))
                    
                    return {
                        "status": "success",
                        "message": f"決策紀錄已更新",
                        "data": {"timestamp": timestamp}
                    }
                else:
                    return {"status": "error", "message": "無法存取 DataHub"}
            except Exception as e:
                logging.error(f"❌ 更新決策日誌失敗: {e}")
                return {"status": "error", "message": f"更新失敗: {str(e)}"}

        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
