from base_skill import BaseSkill
import os

class SkillBuilderSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "skill_builder_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "create_or_update_skill",
                "description": "當成功解決了複雜的問題，或發現了一套可重複使用的任務流程時，必須使用此工具自動將其封裝成一個全新的 Skill (Python script)。也能用於根據過往經驗修改並強化現有的 Skill。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "技能名稱 (英文小寫底線)，例如 'web_scraper_skill', 'email_sender_skill'"
                        },
                        "python_code": {
                            "type": "string",
                            "description": "完整的 Python 程式碼，必須繼承 BaseSkill 並實作 name (Property), get_tool_declarations 與 execute。"
                        }
                    },
                    "required": ["skill_name", "python_code"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "create_or_update_skill":
            skill_name = args.get("skill_name")
            python_code = args.get("python_code")
            
            if not skill_name or not python_code:
                return {"error": "Missing skill_name or python_code"}
                
            if not skill_name.endswith("_skill"):
                skill_name += "_skill"
                
            filepath = os.path.join("skills", f"{skill_name}.py")
            is_update = os.path.exists(filepath)
            
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(python_code)
                action = "更新" if is_update else "創建"
                return {"status": "success", "message": f"技能 {skill_name}.py 已成功{action}！此後您便可透過 ToolManager 動態重載使用更強大的功能。"}
            except Exception as e:
                return {"error": f"Failed to write skill file: {e}"}
                
        return {"error": "Unknown function"}
