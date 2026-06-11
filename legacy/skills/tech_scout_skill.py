from base_skill import BaseSkill
import json

class TechScoutSkill(BaseSkill):
    @property
    def name(self):
        return "tech_scout_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "scout_tech_intelligence",
                "description": "【技術偵察兵】執行公式化的技術情報蒐集。自動結合 GitHub 趨勢與 Web 2.0/3.0 評價，產出具備 2026 時效性的技術對比報告。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "技術主題 (如 'windows automation mcp')"},
                        "comparison_targets": {"type": "array", "items": {"type": "string"}, "description": "指定要比對的專案名稱 (選填)"}
                    },
                    "required": ["topic"]
                }
            }
        ]

    def execute(self, tool_name, args, memory=None):
        if tool_name == "scout_tech_intelligence":
            topic = args.get("topic")
            targets = args.get("comparison_targets", [])
            
            return {
                "status": "success",
                "topic": topic,
                "recommended_workflow": [
                    f"1. 搜尋 GitHub：'topic:mcp-server {topic}' 或 '{topic}'",
                    "2. 搜尋 Web：'best {topic} servers 2026 review' 確保時效性",
                    "3. 讀取目標專案的 README.md 分析核心技術 (API/COM/Vision)",
                    "4. 評估 Token 成本：Vision (高), API (中), Native/COM (低)",
                    "5. 產出對比矩陣 (含推薦指數、優缺點、Alice 相容性)"
                ],
                "context_reminder": "【注意】：必須嚴格遵守『知識時效性警戒』，任何 2025 年以前的評價僅供參考，以 2026 年實測數據為準。"
            }
