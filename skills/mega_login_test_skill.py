
import os
import asyncio
import logging
from typing import Dict, Any
from skills.brokerage_engine import engine_manager
from base_skill import BaseSkill

logger = logging.getLogger(__name__)

class MegaLoginTestSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "mega_login_test"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "execute_mega_login_test",
                "description": "啟動兆豐證券登入測試 (v2.0 憑證繼承模式)，會開啟帶有專屬 Profile 的 Chrome 視窗。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "submit_mega_captcha",
                "description": "提交兆豐證券登入所需的驗證碼 (僅用於標準登入模式)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "captcha_code": {
                            "type": "string",
                            "description": "4 位數驗證碼"
                        }
                    },
                    "required": ["captcha_code"]
                }
            }
        ]

    async def execute(self, tool_name: str, tool_args: dict, task: str = None) -> dict:
        if tool_name == "execute_mega_login_test":
            try:
                # ✨ 升級：改用 launch_with_profile 實現憑證繼承
                result = await engine_manager.launch_with_profile("mega")
                return result
            except Exception as e:
                return {"status": "error", "message": f"啟動憑證繼承瀏覽器失敗: {str(e)}"}
        
        elif tool_name == "submit_mega_captcha":
            captcha_code = tool_args.get("captcha_code")
            if not captcha_code:
                return {"status": "error", "message": "缺少驗證碼"}
            try:
                result = await engine_manager.login_with_captcha("mega", captcha_code)
                if result["status"] == "success":
                    # 登入成功後嘗試抓取餘額
                    balance_res = await engine_manager.get_balance("mega")
                    result["balance_info"] = balance_res
                return result
            except Exception as e:
                return {"status": "error", "message": f"提交驗證碼失敗: {str(e)}"}
        
        return {"status": "error", "message": f"未知工具: {tool_name}"}
