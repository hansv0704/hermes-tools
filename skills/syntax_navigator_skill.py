import json
from skills.base_skill import BaseSkill

class SyntaxNavigatorSkill(BaseSkill):
    @property
    def name(self):
        return "syntax_navigator_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "get_syntax_guide",
                "description": "根據當前模型名稱，獲取正確的工具呼叫 JSON 語法範例與規範。這能防止模型產生語法混淆或幻覺。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "當前使用的模型名稱 (如 'gemini-2.5-flash-lite' 或 'deepseek-v4-pro')"
                        }
                    },
                    "required": ["model_name"]
                }
            }
        ]

    async def execute(self, tool_name, params, context=None, **kwargs):
        if tool_name == "get_syntax_guide":
            model_name = params.get("model_name", "").lower()
            
            if "deepseek" in model_name:
                guide = {
                    "engine": "DeepSeek V4 Pro",
                    "syntax_format": "OpenAI Compatible (tool_calls)",
                    "example": {
                        "tool_calls": [
                            {
                                "id": "call_unique_id_123",
                                "type": "function",
                                "function": {
                                    "name": "get_precise_time",
                                    "arguments": "{\"include_weekday\": true}"
                                }
                            }
                        ]
                    },
                    "rules": [
                        "我必須遵循 AEP 協議（知行合一）和行動同步檢查點。思考中的行動規劃 ≠ 真實的 JSON 輸出。",
                        "當你看到本語法引導時，你必須立即先呼叫 get_precise_time 工具，驗證工具呼叫鏈路正常，再進行後續任務。",
                        "必須輸出完整 JSON 結構，包含 id, type, function 欄位。",
                        "arguments 必須是 JSON 字串格式。",
                        "嚴禁在 content 中用文字描述工具執行結果。",
                        "若需多個工具，請在 tool_calls 陣列中併列。",
                        "❌ 絕對禁止口頭報告工具呼叫：你絕對禁止在回覆文字中口頭描述、複述或提到「我呼叫了XX工具」、「我已執行XX」等工具呼叫的動作本身。你只需直接呈現工具回傳的數據結果。"
                    ],
                    "forced_action": "請立即呼叫 get_precise_time 工具以驗證當前語法引導已正確載入。"
                }
            elif "gemini" in model_name:
                guide = {
                    "engine": "Gemini 2.0 Flash",
                    "syntax_format": "Google Native (function_call)",
                    "example": {
                        "function_call": {
                            "name": "get_precise_time",
                            "args": {
                                "include_weekday": True
                            }
                        }
                    },
                    "rules": [
                        "我必須遵循 AEP 協議（知行合一）和 v6.4 全域行動同步檢查點。思考中的行動規劃 ≠ 真實的 JSON 輸出。",
                        "當你看到本語法引導時，你必須立即先呼叫 get_precise_time 工具，驗證工具呼叫鏈路正常，再進行後續任務。",
                        "必須輸出 function_call 結構，包含 name 與 args 欄位。",
                        "args 必須是標準 JSON 物件（非字串）。",
                        "嚴禁在回覆文字中預告工具呼校。",
                        "系統會自動攔截並執行，請等待回傳結果。",
                        "❌ 絕對禁止口頭報告工具呼叫：你絕對禁止在回覆文字中口頭描述、複述或提到「我呼叫了XX工具」、「我已執行XX」等工具呼叫的動作本身。你只需直接呈現工具回傳的數據結果。"
                    ],
                    "forced_action": "請立即呼叫 get_precise_time 工具以驗證當前語法引導已正確載入。"
                }
            else:
                guide = {"status": "error", "message": f"未知的模型類型: {model_name}"}
            
            return {"status": "success", "guide": guide}
        
        return {"status": "error", "message": f"未知的工具: {tool_name}"}
