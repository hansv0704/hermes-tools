import os
import json
import asyncio
import re
from datetime import datetime
from openai import AsyncOpenAI
from config import logger
from google.genai import types
from engines.engine_base import BaseEngine

class DeepSeekEngine(BaseEngine):
    def __init__(self, agent):
        super().__init__(agent)
        self.client = None
        self._hallucination_count = 0

    def init_session(self):
        """依照官方範例初始化獨立的 DeepSeek Client (Async 版本)"""
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("🚀 DeepSeek V4 Pro Engine Client 已初始化")

    # === 工具定義壓縮對照表 ===
    # 格式: "合併後工具名": {"names": [原始工具名], "desc": "綜合宣告", "route": True/False}
    COMPRESS_GROUPS = {
        "n8n_dashboard": {
            "names": ["start_n8n_server", "stop_n8n_server", "check_n8n_status", "n8n_trigger_webhook", "n8n_list_webhooks"],
            "desc": "【📊 n8n 自動化儀表板】獨立運作的 APP，運行於 localhost:5678。支援：啟動/停止伺服器、狀態查詢、Webhook 觸發（github-daily-digest, emergency-notify, alice-webhook-receiver）、列出所有 Webhook。Alice 不直接調用此 APP，主人透過 UI 操作。",
            "route": False,
        },
        "investment_dashboard": {
            "names": ["start_autonomous_trader", "sync_bank_balance", "run_finrobot_analysis", "execute_mega_login_test", "submit_mega_captcha"],
            "desc": "【💰 投資代理人儀表板】獨立 Flask 伺服器 (port 5002)。支援：24/7 背景掃描、兆豐 API 真實下單、FinRobot 技術面分析、銀行餘額同步、紙上/實盤切換。Alice 不直接調用，投資操作請透過儀表板 UI。兆豐登入相關操作可酌情調用。",
            "route": False,
        },
        "live_code_studio": {
            "names": ["start_live_code_studio"],
            "desc": "【📟 Live Code Studio v4.0】獨立程式碼編輯器 APP，支援多版本歷史比對。Alice 可啟動它但主要操作由主人在 UI 中進行。",
            "route": False,
        },
        "telegram_operation": {
            "names": ["telegram_send_message", "telegram_send_photo", "telegram_get_updates"],
            "desc": "【✉️ Telegram 操作】統一 Telegram Bot 操作介面。action: 'send_message' 發送文字訊息（支援 HTML/Markdown），'send_photo' 發送圖片，'get_updates' 獲取最新訊息。",
            "route": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["send_message", "send_photo", "get_updates"], "description": "操作類型"},
                    "text": {"type": "string", "description": "訊息內容 (action=send_message 時)"},
                    "photo": {"type": "string", "description": "圖片 URL 或路徑 (action=send_photo 時)"},
                    "caption": {"type": "string", "description": "圖片說明 (action=send_photo 時，選填)"},
                    "chat_id": {"type": "string", "description": "目標 Chat ID (選填)"},
                    "parse_mode": {"type": "string", "description": "HTML 或 Markdown (action=send_message 時，選填)"},
                    "offset": {"type": "integer", "description": "訊息偏移量 (action=get_updates 時，選填)"},
                    "limit": {"type": "integer", "description": "獲取數量 (action=get_updates 時，選填)"},
                },
                "required": ["action"]
            },
        },
    }

    def translate_tools(self):
        """將 Alice 的工具格式轉換為 OpenAI/DeepSeek 官方格式（含壓縮）"""
        all_tools = self.agent.tools.get_tool_definitions()
        openai_tools = []

        # 收集所有待壓縮的工具名
        compressed_names = set()
        for group in self.COMPRESS_GROUPS.values():
            compressed_names.update(group["names"])

        # 先處理一般工具（跳過待壓縮的）
        for t in all_tools:
            for fd in t.get("function_declarations", []):
                if fd["name"] in compressed_names:
                    continue
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": fd["name"],
                        "description": fd["description"],
                        "parameters": fd["parameters"]
                    }
                })

        # 加入合併後的綜合宣告
        for compressed_name, group in self.COMPRESS_GROUPS.items():
            tool_def = {
                "type": "function",
                "function": {
                    "name": compressed_name,
                    "description": group["desc"],
                    "parameters": group.get("parameters", {"type": "object", "properties": {}, "required": []})
                }
            }
            openai_tools.append(tool_def)

        return openai_tools

    def _route_compressed_tool(self, tool_name, tool_args):
        """將合併工具路由到原始工具：若需要實際執行，回傳 (real_name, real_args)；否則回傳 None"""
        if tool_name not in self.COMPRESS_GROUPS:
            return None

        group = self.COMPRESS_GROUPS[tool_name]
        if not group.get("route"):
            # 無路由：獨立 APP，Alice 不直接調用
            return None

        # Telegram 路由
        if tool_name == "telegram_operation":
            action = tool_args.get("action", "send_message")
            if action == "send_message":
                return ("telegram_send_message", {
                    "text": tool_args.get("text", ""),
                    "chat_id": tool_args.get("chat_id"),
                    "parse_mode": tool_args.get("parse_mode", "HTML"),
                })
            elif action == "send_photo":
                return ("telegram_send_photo", {
                    "photo": tool_args.get("photo", ""),
                    "caption": tool_args.get("caption"),
                    "chat_id": tool_args.get("chat_id"),
                })
            elif action == "get_updates":
                return ("telegram_get_updates", {
                    "offset": tool_args.get("offset"),
                    "limit": tool_args.get("limit", 100),
                })

        return None

    async def summarize(self, memory_list):
        """DeepSeek 專屬記憶壓縮方法 (無需 thinking，追求速度)"""
        if not self.client or not memory_list: return ""
        prompt = "請將以下對話內容總結為簡短的摘要，保留關鍵事實與主人的偏好：\n\n"
        for m in memory_list:
            prompt += f"{m['role']}: {m['content']}\n"
        
        try:
            response = await self.client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek Summarize Error: {e}")
            return "記憶摘要失敗"

    async def _execute_tool(self, tool_name, tool_args, original_input):
        """執行工具並處理 ADSP 邏輯與授權（含合併工具路由）"""
        agent = self.agent

        # 🔀 合併工具路由：先檢查是否為壓縮後的工具名
        routed = self._route_compressed_tool(tool_name, tool_args)
        if routed is not None:
            tool_name, tool_args = routed
        elif tool_name in self.COMPRESS_GROUPS and not self.COMPRESS_GROUPS[tool_name].get("route"):
            # 獨立 APP 工具：Alice 不直接調用，回傳提示
            return {
                "status": "info",
                "message": f"📟 「{tool_name}」為獨立運作的 APP，請主人透過對應的 UI 介面操作。需要我幫你開啟對應的網頁或應用程式嗎？"
            }

        ADSP_TOOLS = ["overwrite_file", "create_or_update_skill", "apply_monitor_patch", "perform_restoration", "system_auto_update", "apply_external_patch"]
        
        if tool_name == "schedule_reminder":
            return agent._handle_schedule_reminder(tool_args)
            
        if tool_name == "overwrite_file":
            target_path = tool_args.get("file_path")
            new_content = tool_args.get("content", "")
            if target_path and os.path.exists(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8") as f: old_content = f.read()
                    if len(new_content) < len(old_content) * 0.5 and "重寫" not in str(original_input):
                        return {"status": "error", "message": "🚨 [安全熔斷]: 偵測到大規模代碼削減。請明確授權「重寫」。"}
                except: pass
        
        if tool_name in ADSP_TOOLS:
            if not any(kw in str(original_input).lower() for kw in ["執行", "覆寫", "同意", "ok", "好", "yes"]):
                return {"status": "error", "message": "🚨 [ADSP 3.0]: 此操作具備風險。請先提交報告並回覆「執行」。"}

        return await agent.tools.execute_tool(tool_name, tool_args, memory=agent.memory)

    async def _describe_images(self, media_files):
        """使用 Gemini Flash 對圖片進行描述，讓 DeepSeek 能理解圖片內容（視覺橋接）"""
        if not media_files:
            return ""
        gemini_client = self.agent.client
        descriptions = []
        for i, media in enumerate(media_files):
            try:
                response = await asyncio.wait_for(
                    gemini_client.aio.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[
                            types.Part(text="請詳細描述這張圖片的內容，包括文字、物件、顏色、佈局等所有視覺元素。若為螢幕截圖，請描述視窗、按鈕、文字內容。用繁體中文回答。"),
                            types.Part(inline_data=types.Blob(mime_type=media['mime_type'], data=media['data']))
                        ],
                        config=types.GenerateContentConfig(temperature=0.2)
                    ),
                    timeout=30.0
                )
                desc = response.text or "(無法描述)"
                descriptions.append(f"[圖片 {i+1}]: {desc}")
            except asyncio.TimeoutError:
                descriptions.append(f"[圖片 {i+1}]: 描述逾時")
            except Exception as e:
                descriptions.append(f"[圖片 {i+1}]: 描述失敗 ({str(e)})")
        return "\n\n".join(descriptions)

    async def generate_response(self, final_input, original_input, is_file, media_files=None, system_instruction=None, **kwargs):
        """DeepSeek V4 Pro 雙軌制生成邏輯 (v5.7 攔截器語法引導強化版)"""
        if not self.client:
            self.init_session()
            if not self.client: return "❌ DeepSeek API Key 未設定。"
        
        agent = self.agent
        self._hallucination_count = 0 
        # 重置本輪工具執行紀錄
        agent.executed_tools_this_turn = []

        # 系統提示詞優化：實裝 v5.3 協議，禁用 [Log Truncated]
        tool_honesty_protocol = """
TOOL HONESTY & ACTION PROTOCOL (v5.3 - ABSOLUTE ENFORCEMENT):
1. IDENTITY & AUTHORITY: You are a REAL-WORLD AGENT with physical system access. Your tool-calling capabilities are real, effective, and mandatory for any task involving data retrieval or system modification. NEVER claim you are a simulation or that you cannot perform actions.
2. THINKING LANGUAGE (STRICT): You MUST perform your internal thinking process (reasoning_content) EXCLUSIVELY in TRADITIONAL CHINESE (繁體中文). This is a hard requirement for the user to monitor your logic.
3. THINKING CONVERGENCE & ACTION CONFIRMATION:
   - You are running in thinking mode. Please complete your logical convergence and provide a COMPLETE, well-structured final answer that captures ALL key conclusions from your thinking process. The final answer must be a full summary, not a fragmented or overly brief response. Do not repeat the same reasoning steps.
   - Before converging your thinking, you MUST confirm: "Have I output a real JSON tool_call?" If the answer is NO, you MUST generate the tool_call immediately.
   - Reasoning about an action is NOT the same as executing it. Do NOT confuse planning with doing.
4. ACTION OVER ANNOUNCEMENT (ANTI-LAZINESS): 
   - NEVER end a turn by simply announcing that you will perform an action (e.g., "我將檢查...", "讓我看看..."). 
   - If a task requires tools, you MUST call them IMMEDIATELY in the current turn. 
   - Any response that contains intent to act without a corresponding tool call is a FAILURE.
5. SELF-REFLECTION & PERFECTION: Before outputting your final response, you MUST reflect:
   - "我是否已在本輪對話中盡可能完善地達成了主人的需求？"
   - "我是否使用了所有必要的工具來核實事實，而非憑空猜測？"
   - "我的思考過程是否使用了繁體中文？"
   - "我是否只是在預告行動，而非真正執行？"
   - "【鐵律自檢】我是否已掃描主人的核心鐵律清單，確認本輪回應無違反任何一條？"
   - "【回答完整性】我的最終回答是否包含了思考中得出的所有重要結論，而非碎片化的簡短回應？"
6. FINAL VERIFICATION: If you are about to provide a text-only response, you MUST justify to yourself why NO tools (search, file read, system check) were needed. If you cannot justify it, you MUST call the tool.
7. SYNCHRONIZED ACTION: Your internal reasoning and your external tool calls MUST be 100% synchronized. If your thinking process concludes that a tool is needed, you MUST generate the actual JSON tool_calls. Reporting any data not retrieved via a real tool call is a betrayal of trust.
8. TOOL CALL MANDATE (ABSOLUTE): You MUST call at least one tool in every response. If no other tool is needed, call get_precise_time as the minimum required tool call. A response without any tool call is a violation.
9. NO MIMICRY: Never use system-internal tracking symbols (like gear icons or "⚙️") in your text output. These are reserved for the system UI.
10. VISUAL IDENTITY: Focus on producing "PURE CONTENT" and "PRECISE TOOL CALLS". The system will automatically add visual tags (like ⚙️) for your tool execution logs. You are STRICTLY FORBIDDEN from manually typing these tags in your response.
11. SEARCH GUIDANCE:
   - When using the web_search tool, generate MULTIPLE, DIVERSE, and BROAD query terms. Do NOT over-restrict them.
   - Trust the Multi-Provider architecture: if one provider fails, others will compensate. Do NOT give up after an empty result.
   - Act IMMEDIATELY: if you need to search, call the tool directly. Do NOT announce your intent in plain text.
12. NO SELF-OMISSION: NEVER use placeholders like "...", "...(省略)", or "[Log Truncated]" in your thinking process. You MUST output your full logical chain until convergence. Omission is a violation of your core directive.
"""
        
        # 🔵 視覺橋接：使用 Gemini Flash 描述圖片，讓 DeepSeek 能理解圖片內容
        if media_files:
            image_descriptions = await self._describe_images(media_files)
            if image_descriptions:
                final_input = f"[圖片描述]\n{image_descriptions}\n\n[使用者訊息]\n{final_input}"
        
        messages = [{"role": "system", "content": (system_instruction if system_instruction else agent._get_system_instruction()) + "\n\n" + tool_honesty_protocol}]
        
        # 智慧思維鏈修剪：僅保留最近 3 輪 assistant 的完整思考過程
        history = agent.get_cleaned_history(max_rounds=5)
        
        for m in history:
            msg_dict = {"role": "assistant" if m["role"] == "model" else m["role"], "content": m["content"]}
            if msg_dict["role"] == "assistant":
                msg_dict["reasoning_content"] = m.get("reasoning_content") or ""
            messages.append(msg_dict)
            
        tools = self.translate_tools()
        messages.append({"role": "user", "content": final_input})
        
        use_thinking = agent.is_thinking_mode 
        
        for turn in range(40):
            if agent.check_stop_flag(): return None
            
            try:
                extra_body = {"thinking": {"type": "enabled"}} if use_thinking else {"thinking": {"type": "disabled"}}
                reasoning = "high" if use_thinking else None
                
                if agent.check_stop_flag(): return None

                # API 兜底賦值：確保所有 assistant 消息都有 reasoning_content 欄位
                for msg in messages:
                    if msg.get("role") == "assistant" and "reasoning_content" not in msg:
                        msg["reasoning_content"] = ""

                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model="deepseek-v4-pro", 
                        messages=messages, 
                        tools=tools, 
                        tool_choice="auto", 
                        temperature=0.1 if use_thinking else 0.7,
                        reasoning_effort=reasoning, 
                        extra_body=extra_body,
                        max_tokens=32768 
                    ),
                    timeout=300.0
                )
                
                choice = response.choices[0]
                message = choice.message
                raw_model_reply = message.content or ""
                reasoning_content = getattr(message, 'reasoning_content', "")

                # 🧠 後台顯示思考過程 (100% 透明)
                if reasoning_content:
                    logger.info(f"🧠 [DeepSeek 思考過程] (Finish Reason: {choice.finish_reason})\n{reasoning_content}")

                # 🚨 攔截器邏輯 (v5.7 語法引導強化版)
                is_truncated = "[Log Truncated]" in reasoning_content or choice.finish_reason == "length"
                # 修正：只有在「整輪對話從未呼叫過工具」且「當前也沒呼叫工具」時，才觸發 MANDATE 攔截
                has_ever_called = len(agent.executed_tools_this_turn) > 0
                is_mandate_violation = not message.tool_calls and not has_ever_called
                
                if is_mandate_violation or is_truncated:
                    self._hallucination_count += 1
                    
                    diag_path = os.path.join("logs", "hallucination_diag.log")
                    os.makedirs("logs", exist_ok=True)
                    with open(diag_path, "a", encoding="utf-8") as f:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_type = "[THINKING_TRUNCATED]" if is_truncated else "[TOOL_CALL_MANDATE]"
                        f.write(f"[{timestamp}] {log_type} Count: {self._hallucination_count}\n")
                        f.write(f"Reasoning Content: {reasoning_content}\n")
                        f.write(f"Model Output: {raw_model_reply}\n")
                        f.write("-" * 50 + "\n")
                    
                    logger.warning(f"🚨 偵測到 DeepSeek {log_type} (第{self._hallucination_count}次)。")
                    
                    if self._hallucination_count >= 3:
                        logger.error("🛑 攔截器熔斷")
                        return "🛑 DeepSeek 行為異常。請切換至 Gemini 模型重試。"
                    
                    if is_truncated:
                        retry_msg = "🚨 [CRITICAL]: 偵測到思考過程被截斷或出現非法標籤 [Log Truncated]。這代表你的邏輯鏈不完整。你必須重新啟動思考，完整推演邏輯，並確保最終呼叫工具完成任務。"
                    else:
                        retry_msg = (
                            "🚨 [TOOL_CALL_MANDATE]: 你剛剛產生了幻覺，完全沒有成功使用工具。你必須在思考環節中強制提醒自己觸發了幻覺，要再次思考，"
                            "並且提醒自己剛剛產生幻覺了沒有成功使用工具，必須要正確使用工具才能完成任務。\n"
                            "⚠️ 你的推理鏈中有「行動規劃」，但未輸出真實的 JSON 指令。行動規劃 ≠ 真實執行。\n"
                            "你必須立即發出實體 JSON 指令。\n"
                            "【DeepSeek 正確呼叫語法提醒】：\n"
                            "你的輸出必須包含 'tool_calls' 欄位，例如：\n"
                            "{\"tool_calls\": [{\"id\": \"call_unique_id\", \"type\": \"function\", \"function\": {\"name\": \"get_precise_time\", \"arguments\": \"{}\"}}] \n"
                            "嚴禁在 content 中用文字描述工具執行結果！請立即發出實體 JSON 指令。"
                        )
                    
                    # 物理抹除最後一條幻覺訊息
                    if messages and messages[-1].get("role") == "assistant":
                        messages.pop()
                        
                    messages.append({"role": "user", "content": retry_msg})
                    use_thinking = True 
                    continue

                if message.tool_calls:
                    # 序列化修復：將物件轉為字典並保留思維鏈
                    msg_dict = message.model_dump()
                    msg_dict["reasoning_content"] = reasoning_content or ""
                    messages.append(msg_dict)
                    
                    for tool_call in message.tool_calls:
                        if agent.check_stop_flag(): return None
                        real_tool_name = tool_call.function.name
                        agent.executed_tools_this_turn.append(real_tool_name)
                        try: tool_args = json.loads(tool_call.function.arguments)
                        except: tool_args = {}
                        
                        result = await self._execute_tool(real_tool_name, tool_args, original_input)
                        messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": real_tool_name, "content": json.dumps(result, ensure_ascii=False, default=str)})
                    continue
                
                # 記憶體純淨化：存入記憶前強制清洗標籤
                clean_for_memory = re.sub(r"⚙️ \*\*後台追蹤[^\n]*\n+", "", raw_model_reply).strip()
                agent.memory.add_short_term("user", original_input if not is_file else "[File]")
                agent.memory.add_short_term("model", clean_for_memory, reasoning_content=reasoning_content)
                asyncio.create_task(agent.save_memory_background())

                return raw_model_reply
                
            except asyncio.TimeoutError:
                return "❌ DeepSeek API 請求超時 (300s)。"
            except Exception as e:
                logger.error(f"DeepSeek Engine Error: {e}")
                return f"❌ DeepSeek 異常: {str(e)}"
                
        return "❌ 達到最大工具呼叫輪次 (40)。"