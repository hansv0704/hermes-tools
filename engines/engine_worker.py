"""
Worker Agent 引擎 — 移植自 mano-afk 的 Sub-agent 協作架構。
復用 DeepSeek V4 Pro API，注入角色專用 system prompt + 工具白名單過濾。
Worker 獨立思考、不寫入主記憶、回傳結構化 JSON。
"""

import json
import os
from openai import AsyncOpenAI
from config import logger


class WorkerEngine:
    """輕量級 Worker Agent 引擎，為特定角色執行專注任務。"""

    def __init__(self, agent, role_definition: dict):
        self.agent = agent
        self.role = role_definition
        self.client = None
        self._init_client()

    def _init_client(self):
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )

    def _get_whitelisted_tools(self) -> list:
        """過濾工具：只保留角色白名單中的工具"""
        allowed = set(self.role.get("allowed_tools", []))
        
        # 防禦：檢查 agent.tools 是否可用
        if not hasattr(self.agent, 'tools') or self.agent.tools is None:
            logger.warning(f"Worker {self.role.get('name')}: agent.tools 不可用，無法取得領域工具")
            all_tools = []
        else:
            all_tools = self.agent.tools.get_tool_definitions()

        whitelisted = []
        for t in all_tools:
            for fd in t.get("function_declarations", []):
                if fd["name"] in allowed:
                    whitelisted.append({
                        "type": "function",
                        "function": {
                            "name": fd["name"],
                            "description": fd["description"],
                            "parameters": fd["parameters"]
                        }
                    })

        # 確保 get_precise_time 總是在白名單中（Worker 也需要時間校準）
        time_names = {w["function"]["name"] for w in whitelisted}
        if "get_precise_time" not in time_names:
            whitelisted.append({
                "type": "function",
                "function": {
                    "name": "get_precise_time",
                    "description": "獲取當前精準時間",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_weekday": {"type": "boolean", "description": "是否包含星期資訊"}
                        }
                    }
                }
            })

        return whitelisted

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> dict:
        """執行工具（透過 agent.tools，與 Main Agent 共用同一 ToolManager）"""
        if not hasattr(self.agent, 'tools') or self.agent.tools is None:
            return {"error": "ToolManager 不可用（agent.tools 為 None），Worker 無法執行領域工具"}
        return await self.agent.tools.execute_tool(
            tool_name, tool_args, memory=self.agent.memory
        )

    async def run(self, task: str, context: str = "") -> dict:
        """
        執行 Worker 任務。

        Args:
            task: 任務描述
            context: 額外上下文（如檔案內容、前後文）

        Returns:
            結構化結果 dict
        """
        if not self.client:
            return {"error": "DeepSeek API Key 未設定"}

        # 組裝 system prompt — 來自角色定義，完整自足（mano-afk 核心原則 #1）
        role_prompt = self.role.get("system_prompt", "")
        system_prompt = f"""你是一個 Worker Agent，角色為「{self.role.get('name', 'worker')}」。
{role_prompt}

⚠️ 重要：你只負責執行被指派的任務，完成後立即回傳 JSON 結果。
不要與使用者閒聊、不要問問題、不要做任務範圍外的事。
每次回應必須呼叫至少一個工具以獲取真實數據。"""

        messages = [{"role": "system", "content": system_prompt}]

        # 加入上下文（如有）
        if context:
            messages.append({"role": "user", "content": f"[上下文資訊]\n{context}"})

        messages.append({"role": "user", "content": f"[任務]\n{task}"})

        tools = self._get_whitelisted_tools()
        max_turns = self.role.get("max_turns", 5)

        for turn in range(max_turns):
            try:
                response = await self.client.chat.completions.create(
                    model="deepseek-v4-pro",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=8192
                )

                choice = response.choices[0]
                message = choice.message

                if message.tool_calls:
                    # 記錄工具呼叫到 messages
                    msg_dict = message.model_dump()
                    messages.append(msg_dict)

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}

                        result = await self._execute_tool(tool_name, tool_args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": json.dumps(result, ensure_ascii=False, default=str)
                        })
                else:
                    # Worker 完成任務，嘗試解析 JSON
                    raw_output = message.content or ""
                    try:
                        # 嘗試從輸出中提取 JSON
                        if "```json" in raw_output:
                            json_start = raw_output.find("```json") + 7
                            json_end = raw_output.find("```", json_start)
                            json_str = raw_output[json_start:json_end].strip()
                        elif "{" in raw_output:
                            json_start = raw_output.find("{")
                            json_end = raw_output.rfind("}") + 1
                            json_str = raw_output[json_start:json_end]
                        else:
                            json_str = raw_output

                        result = json.loads(json_str)
                        result["_raw_output"] = raw_output
                        result["_turns_used"] = turn + 1
                        return result
                    except json.JSONDecodeError:
                        return {
                            "verdict": "unparseable",
                            "raw_output": raw_output,
                            "_turns_used": turn + 1,
                            "error": "無法解析 Worker 輸出為 JSON"
                        }

            except Exception as e:
                logger.error(f"Worker Engine Error ({self.role.get('name')}): {e}")
                return {"error": str(e), "_turns_used": turn + 1}

        return {"error": f"達到最大輪次 ({max_turns})，Worker 未完成任務"}
