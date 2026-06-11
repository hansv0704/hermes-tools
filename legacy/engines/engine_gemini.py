import os
import json
import asyncio
import re
from google.genai import types
from config import logger
from engines.engine_base import BaseEngine

class GeminiEngine(BaseEngine):
    def __init__(self, agent):
        super().__init__(agent)
        self.chat_session = None

    def _apply_semantic_compression(self, text):
        """簡單的語義壓縮：移除多餘換行"""
        if not text: return ""
        return re.sub(r"\n+", "\n", text)

    def _apply_prompt_caching(self, system_instruction):
        """預留的 Prompt Caching 介面"""
        pass

    def init_session(self, custom_instruction=None):
        agent = self.agent
        model_name = agent.models_list[agent.current_model_index]
        system_instruction = custom_instruction if custom_instruction else agent._get_system_instruction()
        self._apply_prompt_caching(system_instruction)
        
        all_tools_definitions = agent.tools.get_tool_definitions()
        tools_obj = []
        seen_names = set()
        for t in all_tools_definitions:
            if "function_declarations" in t:
                fds = []
                for fd in t["function_declarations"]:
                    name = fd.get("name")
                    if name in seen_names: continue
                    seen_names.add(name)
                    fds.append(types.FunctionDeclaration(
                        name=name, 
                        description=fd.get("description"), 
                        parameters=fd.get("parameters")
                    ))
                if fds: tools_obj.append(types.Tool(function_declarations=fds))
        
        conf = types.GenerateContentConfig(tools=tools_obj, system_instruction=system_instruction, temperature=0.4)
        chat_history = []
        # 使用清洗後的歷史，防止模型模仿視覺標籤
        for m in agent.get_cleaned_history(max_rounds=10):
            role = "model" if m["role"] in ["model", "assistant"] else "user"
            safe_text = self._apply_semantic_compression(m["content"]) if m["content"] else "(empty)"
            if chat_history and chat_history[-1].role == role:
                chat_history[-1].parts[0].text += f"\n\n{safe_text}"
            else:
                chat_history.append(types.Content(role=role, parts=[types.Part(text=safe_text)]))
        
        if chat_history and chat_history[0].role == "model":
            chat_history.insert(0, types.Content(role="user", parts=[types.Part(text="(System start)")]))
        
        self.chat_session = agent.client.aio.chats.create(model=model_name, config=conf, history=chat_history)
        logger.info(f"✅ Gemini 引擎會話已初始化: {model_name}")

    async def generate_response(self, final_input, original_input, is_file, media_files=None, system_instruction=None, **kwargs):
        agent = self.agent
        
        # 若傳入新的 system_instruction，則重新初始化 session 以套用新指令
        if system_instruction:
            self.init_session(custom_instruction=system_instruction)
        elif not self.chat_session:
            self.init_session()
        
        contents = [final_input]
        if media_files:
            for media in media_files:
                contents.append(types.Part(inline_data=types.Blob(mime_type=media['mime_type'], data=media['data'])))
        
        for _ in range(40):
            # 檢查點 1: 迴圈開始
            if agent.check_stop_flag(): return None
            
            try:
                # 檢查點 2: API 呼叫前
                if agent.check_stop_flag(): return None

                response = await self.chat_session.send_message(contents)
                contents = [] 
                
                if response.candidates and response.candidates[0].content.parts:
                    tool_calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]
                    if tool_calls:
                        tool_responses = []
                        for fc in tool_calls:
                            # 檢查點 3: 工具執行前
                            if agent.check_stop_flag(): return None
                            tool_name = fc.name
                            agent.executed_tools_this_turn.append(tool_name)
                            tool_args = fc.args
                            
                            # ADSP 邏輯
                            ADSP_TOOLS = ["overwrite_file", "create_or_update_skill", "apply_monitor_patch", "perform_restoration", "system_auto_update", "apply_external_patch"]
                            if tool_name == "schedule_reminder":
                                tool_result = agent._handle_schedule_reminder(tool_args)
                            elif tool_name == "overwrite_file":
                                target_path = tool_args.get("file_path")
                                new_content = tool_args.get("content", "")
                                if target_path and os.path.exists(target_path):
                                    with open(target_path, "r", encoding="utf-8") as f: old_content = f.read()
                                    if len(new_content) < len(old_content) * 0.5 and "重寫" not in str(original_input):
                                        tool_result = {"status": "error", "message": "🚨 [安全熔斷]: 偵測到大規模代碼刪減。"}
                                    elif any(kw in str(original_input).lower() for kw in ["執行", "覆寫", "同意", "ok", "好", "yes"]):
                                        tool_result = await agent.tools.execute_tool(tool_name, tool_args, memory=agent.memory)
                                    else:
                                        tool_result = {"error": "ADSP_REQUIRED", "message": "🚨 [ADSP 3.0]: 請先提交異動報告，並等待主人回覆「執行」。"}
                                else:
                                    tool_result = await agent.tools.execute_tool(tool_name, tool_args, memory=agent.memory)
                            elif tool_name in ADSP_TOOLS:
                                if any(kw in str(original_input).lower() for kw in ["執行", "覆寫", "同意", "ok", "好", "yes"]):
                                    tool_result = await agent.tools.execute_tool(tool_name, tool_args, memory=agent.memory)
                                else:
                                    tool_result = {"error": "ADSP_REQUIRED", "message": "🚨 [ADSP 3.0]: 請先提交異動報告，並等待主人回覆「執行」。"}
                            else:
                                tool_result = await agent.tools.execute_tool(tool_name, tool_args, memory=agent.memory)
                            
                            tool_responses.append(types.Part(function_response=types.FunctionResponse(name=tool_name, response=tool_result)))
                        
                        if tool_responses:
                            contents = tool_responses
                            continue
                    
                    raw_reply = response.text
                    # 儲存記憶時，只存入模型真正生成的內容，不含視覺標籤
                    agent.memory.add_short_term("user", original_input if not is_file else "[File]")
                    agent.memory.add_short_term("model", raw_reply)
                    asyncio.create_task(agent.save_memory_background())

                    return raw_reply
            except Exception as e:
                logger.error(f"❌ Gemini 異常: {e}")
                return f"❌ Gemini 異常: {str(e)}"
        return "❌ 達到最大輪次。"
