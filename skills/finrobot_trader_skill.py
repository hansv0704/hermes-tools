import os
import subprocess
import json
from skills.base_skill import BaseSkill

class FinRobotTraderSkill(BaseSkill):
    @property
    def name(self):
        return "finrobot_trader_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "run_finrobot_analysis",
                "description": "呼叫 FinRobot 框架進行股票技術面與情緒面分析。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代號 (如 NVDA, 2330.TW)"
                        },
                        "budget": {
                            "type": "number",
                            "description": "投入預算 (TWD/USD)",
                            "default": 10000
                        }
                    },
                    "required": ["symbol"]
                }
            }
        ]

    async def execute(self, tool_name, args):
        if tool_name == "run_finrobot_analysis":
            symbol = args.get("symbol")
            budget = args.get("budget", 10000)
            
            # 這裡未來會對接 finrobot_env 中的 python 腳本
            # 目前先建立一個橋接邏輯，檢查環境是否就緒
            venv_python = os.path.abspath("finrobot_env/Scripts/python.exe")
            if not os.path.exists(venv_python):
                return {"status": "error", "message": "FinRobot 虛擬環境尚未建立完成，請稍候。"}
            
            # 模擬分析邏輯 (第一階段：環境確認與基礎數據獲取)
            return {
                "status": "success",
                "message": f"FinRobot 已接收到 {symbol} 的盯盤任務。",
                "analysis_preview": f"正在針對 {symbol} 進行短期交易分析（預算：{budget}）。",
                "next_step": "等待 pip 安裝完成後，我將生成首份 AI 投資提案。"
            }
