from base_skill import BaseSkill

class SystemSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "system_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "schedule_reminder",
                "description": "設定排程提醒。當使用者指定特定時間呼叫你時使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delay_seconds": {
                            "type": "number",
                            "description": "距離現在還有多少秒 (請自行計算現在到目標時間的秒數差)"
                        },
                        "task": {
                            "type": "string",
                            "description": "屆時要執行的任務內容"
                        },
                        "recurrence": {
                            "type": "string",
                            "description": "重複模式：'daily' 代表每日循環執行，省略或 null 代表一次性任務"
                        }
                    },
                    "required": ["delay_seconds", "task"]
                }
            },
            {
                "name": "system_auto_update",
                "description": "當使用者許可時，從雲端 (如 GitHub) 下載最新程式碼並重啟更新。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "branch": {
                            "type": "string",
                            "description": "要更新的分支或版本，預設為 'main'"
                        }
                    }
                }
            },
            {
                "name": "view_architecture",
                "description": "查看機器人當前的檔案架構清單。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        # Schedule reminder 透過 agent.py 的核心流程特別攔截處理，
        # 如果走到這裡，通常是安全冗餘
        if function_name == "schedule_reminder":
            return {"status": "Redirected", "message": "此功能在核心流程已處理。"}
        elif function_name == "system_auto_update":
            branch = args.get("branch", "main")
            return {
                "status": "success", 
                "message": f"✅ 更新指令已下達：系統將自 {branch} 拉取最新版本碼並重啟。"
            }
        elif function_name == "view_architecture":
            import os
            tree = []
            for root, dirs, files in os.walk("."):
                if "__pycache__" in root or "node_modules" in root or ".git" in root or ".venv" in root:
                    continue
                level = root.replace(".", "").count(os.sep)
                indent = " " * 4 * (level)
                tree.append(f"{indent}{os.path.basename(root)}/")
                subindent = " " * 4 * (level + 1)
                for f in files:
                    tree.append(f"{subindent}{f}")
            
            return {
                "status": "success",
                "message": "已成功獲取當前系統目錄架構：\n" + "\n".join(tree)
            }
        return {"error": "Unknown function in SystemSkill"}
