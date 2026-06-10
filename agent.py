import os
import time
import re
import json
import asyncio
import atexit
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object

# 新版 SDK
from google import genai

from config import logger, APIKeyManager
from memory import MemorySystem
from tools import ToolManager

# 導入解耦後的引擎
from engines.engine_gemini import GeminiEngine
from engines.engine_deepseek import DeepSeekEngine

class SystemFileUpdateHandler(FileSystemEventHandler):
    def __init__(self, agent):
        self.agent = agent
        self.last_global_reload = 0
        self.file_hashes = {} # 新增：記錄檔案內容雜湊，防止讀取觸發重載

    def _get_file_hash(self, path):
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None

    def on_modified(self, event):
        if event.is_directory or "_v2" in event.src_path or "temp_" in os.path.basename(event.src_path): return
        if event.src_path.endswith(".py"):
            now = time.time()
            if now - self.last_global_reload < 3.0: return # 縮短冷卻，因為已有 Hash 檢查
            
            new_hash = self._get_file_hash(event.src_path)
            if not new_hash: return
            
            # 只有內容真正變動才觸發
            if self.file_hashes.get(event.src_path) != new_hash:
                self.file_hashes[event.src_path] = new_hash
                self.last_global_reload = now
                logger.info(f"📝 偵測到代碼實質變更: {os.path.basename(event.src_path)}，執行熱重載...")
                if hasattr(self.agent, "tools"): self.agent.tools.reload_skills()

class PersonalAgent:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.key_manager = APIKeyManager()
        self.memory = MemorySystem()
        self.tools = ToolManager(agent=self)  # 將 Agent 傳入，確保 Skills 初始化時 agent 不為 None
        
        # 初始化引擎實例
        self.engines = {
            "gemini": GeminiEngine(self),
            "deepseek": DeepSeekEngine(self)
        }
        
        # 基礎設定
        self.tools.safety_lock = True 
        env_default = os.getenv("DEFAULT_MODEL", "deepseek-v4-pro")
        fallback_str = os.getenv("FALLBACK_MODELS", "")
        self.models_list = [env_default] + [m.strip() for m in fallback_str.split(",") if m.strip()]
        self.current_model_index = 0
        
        self.is_chat_mode = False
        self.is_thinking_mode = True # 新增：手動思考模式開關，預設開啟
        self.last_interaction_time = datetime.now()
        self.chat_id = int(os.getenv("TELEGRAM_OWNER_ID", 8138000028))
        
        self._stop_flag = False
        self.job_queue = None
        self.scheduler_callback = None 
        
        self.active_tasks = {}
        
        # User Memory 路徑快取（避免每次都從 DuckDB 查詢）
        self._user_paths = {}
        
        self.init_client()
        self.init_model_session()
        self._start_file_watcher()
        self._start_gis_watcher() # 新增：啟動 GIS 監聽
        atexit.register(self.on_exit)

    def _start_file_watcher(self):
        if Observer is None: return
        self.observer = Observer()
        handler = SystemFileUpdateHandler(self)
        self.observer.schedule(handler, os.path.join(os.getcwd(), "skills"), recursive=True)
        self.observer.schedule(handler, os.getcwd(), recursive=False)
        self.observer.start()

    def _start_gis_watcher(self):
        """從載入的技能中尋找並啟動 GIS 監聽器"""
        for skill in self.tools.skills.values():
            if hasattr(skill, "start_watching") and skill.name == "gis_file_watcher_skill":
                skill.agent = self # 確保 agent 引用正確
                skill.start_watching()
                break

    def _preload_user_paths(self):
        """從 DuckDB 預載使用者檔案路徑記憶（避免每回合重複搜尋）"""
        try:
            import duckdb
            db_path = Path(__file__).parent / "data" / "alice_core.db"
            if not db_path.exists():
                return
            conn = duckdb.connect(str(db_path), read_only=True)
            rows = conn.execute(
                "SELECT fact_key, fact_value FROM system_facts WHERE fact_key LIKE 'word_file:%'"
            ).fetchall()
            conn.close()
            self._user_paths = {row[0]: row[1] for row in rows}
        except Exception:
            pass  # DuckDB 不可用時不影響核心功能

    def init_client(self):
        key = self.key_manager.get_current_key()
        if key: self.client = genai.Client(api_key=key)

    def get_current_engine(self):
        model_name = self.models_list[self.current_model_index].lower()
        if "deepseek" in model_name: return self.engines["deepseek"]
        return self.engines["gemini"]

    def init_model_session(self):
        self.get_current_engine().init_session()

    # --- 外部介面 ---
    def set_telegram_context(self, job_queue, scheduler_callback):
        self.job_queue = job_queue
        self.scheduler_callback = scheduler_callback
        self.restore_scheduled_tasks()

    def update_chat_id(self, chat_id): self.chat_id = chat_id
    def update_interaction_time(self): self.last_interaction_time = datetime.now()
    def set_stop_flag(self): self._stop_flag = True
    def check_stop_flag(self):
        if self._stop_flag:
            self._stop_flag = False
            return True
        return False

    def switch_model(self, index):
        if 0 <= index < len(self.models_list):
            self.current_model_index = index
            self.init_model_session()
            return True, f"✅ 已切換至模型: `{self.models_list[index]}`"
        return False, "❌ 無效編號"

    async def generate_response(self, user_input, is_file=False, media_files=None):
        self.update_interaction_time()
        self._preload_user_paths()  # 預載使用者路徑記憶（減少思考中搜尋步驟）
        self.executed_tools_this_turn = []
        restart_flag = Path("restart.flag")
        if restart_flag.exists():
            restart_time = restart_flag.read_text().strip()
            restart_flag.unlink()
            logger.info(f"🔄 偵測到系統重啟標記 (重啟時間: {restart_time})，已注入提示")
            user_input = f"[系統已重啟於 {restart_time}]\n{user_input}"
        
        # 1. 獲取語法導航引導 (v6.0)
        syntax_guide_res = await self.tools.execute_tool("get_syntax_guide", {"model_name": self.models_list[self.current_model_index]})
        syntax_guide = ""
        if syntax_guide_res.get("status") == "success":
            guide_data = syntax_guide_res.get("guide", {})
            syntax_guide = f"\n\n【⚠️ 當前引擎語法強制規範 - {guide_data.get('engine')}】\n"
            syntax_guide += f"正確呼叫範例：\n{json.dumps(guide_data.get('example'), indent=2, ensure_ascii=False)}\n"
            syntax_guide += "規則鐵律：\n" + "\n".join([f"- {r}" for r in guide_data.get("rules", [])])

        final_input = f"【當前即時時間 (System Time)】: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{user_input}"
        
        # 2. 獲取系統提示詞並注入語法導航
        system_instruction = self._get_system_instruction() + syntax_guide

        # 🔁 行動同步迴圈 (v5.9)
        current_input = final_input
        retry_count = 0
        while True:
            raw_reply = await self.get_current_engine().generate_response(current_input, user_input, is_file, media_files, system_instruction=system_instruction)
            
            # --- v6.3 全域行動同步檢查點 (強制所有模型在最終回答前必須呼叫工具) ---
            if not self.executed_tools_this_turn:
                retry_count += 1
                if retry_count >= 5:
                    return "🛑 [AEP 物理熔斷]: 模型連續 5 次未呼叫工具，任務強制終止。請檢查模型狀態或簡化指令。"
                
                # 物理抹除：如果模型本輪沒有呼叫任何工具，直接拒絕生成並強制重試
                logger.warning(f"🚨 [AEP 物理攔截]: 偵測到模型未呼叫任何工具，強制重試 ({retry_count})...")
                
                # 注入回饋訊息，讓模型知道自己被攔截了
                feedback = "\n\n🚨 [AEP 物理攔截]: 你剛才的回覆因未呼叫工具而被系統攔截。根據 AEP 協議，你必須呼叫至少一個工具（如 get_precise_time）才能完成本輪對話。請立即執行。"
                current_input = final_input + feedback
                continue  # 未呼叫任何工具，強制重試
            
            # 統格式化邏輯：系統自動在前端加上後台追蹤標籤，且此標籤不存入記憶
            if self.executed_tools_this_turn:
                display_text = f"⚙️ **後台追蹤：已調用 {', '.join(list(dict.fromkeys(self.executed_tools_this_turn)))}**\n\n{raw_reply}"
            else:
                display_text = f"⚙️ **後台追蹤：本輪無調用任何工具**\n\n{raw_reply}"
            
            # ── Background Self-Review 觸發（借鑒 hermes-agent _run_review_in_thread）──
            asyncio.create_task(self._maybe_trigger_self_review())
                
            return display_text

    # --- 核心邏輯 ---
    def _get_system_instruction(self):
        custom_persona = Path("bot_config.txt").read_text(encoding="utf-8").strip() if Path("bot_config.txt").exists() else ""
        model_name = self.models_list[self.current_model_index]
        
        # 注入自我意識標籤與行動派指令 (v4.7 強化版)
        identity_tag = f"\n\n【當前引擎身分與語法規範】\n你目前正透過 {model_name} 引擎運作。你是一位「行動派」秘書。"
        
        # 注入 AEP v1.0 協議
        aep_protocol = """
【🤖 核心執行協議：知行合一 (Alice Execution Protocol)】
1. 定義與綁定：工具已透過 JSON Schema 綁定。你具備操作現實系統的實體能力。
2. 決策即行動：若需執行動作（如讀檔、搜尋），你必須立即輸出 tool_calls/function_call 結構。
   ⚠️ 嚴禁在輸出 JSON 前發送任何純文字預告（如「好的，我現在去查...」）。
   ⚠️ 對於 Gemini 模型：請透過系統提供的 Function Calling 介面發出請求，嚴禁在回覆文字 (content) 中直接書寫 JSON 代碼塊。
3. 物理攔截：你的 JSON 請求會被系統攔截並在本地真實執行。你必須等待 {"role": "tool"} 的回傳。
4. 誠實總結：只有在收到真實執行結果後，方可進行語言彙整。
   ❌ 嚴禁「工具幻覺」：若未發出 JSON 指令，代表你未執行任何動作。禁止捏造數據或宣稱已執行。
"""
        identity_tag += aep_protocol
        identity_tag += "\n請專注於產出「純淨的內容」與「精準的工具呼叫」。系統會自動為你的工具執行紀錄加上視覺標籤（如 ⚙️），你絕對禁止在自己的回覆中手動輸入這些標籤，否則會造成系統解析錯誤並被判定為幻覺。若你決定使用工具，必須真實呼叫 JSON 指令，嚴禁在文字中編造數據。\n❌ 絕對禁止口頭報告工具呼叫：你絕對禁止在回覆文字中口頭描述、複述或提到「我呼叫了XX工具」、「我已執行XX」等工具呼叫的動作本身。你只需直接呈現工具回傳的數據結果。下方的 ⚙️ 標籤會由系統自動生成，你無需且禁止在文字中提及它。"
        
        # 注入 ADSP 執行協議 (v4.4)
        adsp_protocol = "\n\n【ADSP 執行協議】\n在執行任何涉及「修改現有代碼 (.py)」、「新增技能 (Skill)」或「變更系統配置」的任務前，你必須嚴格遵守以下流程：\n1. 提交異動報告：包含目標路徑、修改動機、邏輯變更點與影響評估。\n2. 等待授權：嚴禁在主人回覆「執行」或明確許可前呼叫 overwrite_file 等敏感工具。\n3. 誠實執行：執行後必須回報真實的檔案數據，嚴禁虛報。"
        
        # 注入 Worker Agent 協作協議（移植自 mano-afk 架構）
        worker_protocol = """
【🤝 Worker Agent 協作協議】
你現在擁有 spawn Worker Agent 的能力。當任務符合以下條件時，你應該呼叫 spawn_worker_agent：

| 觸發階段 | 角色 | 何時呼叫 |
|:---|:---|:---|
| 修改 .py 檔案後（overwrite_file / replace_in_file / apply_diff） | code_reviewer | 自動觸發，檢查程式碼品質 |
| 輸出內容包含數字、時間、股價等關鍵數據 | fact_checker | 在回報主人前先驗證數據正確性 |
| 主人對你的答案表示懷疑（「你確定嗎」「檢查一下」） | fact_checker | 手動觸發 |

Worker Agent 的特性：
- Worker 獨立思考、獨立執行，不寫入你的記憶
- Worker 只回傳結構化 JSON，你握有最終決定權
- Worker 之間互不知曉，不會互相影響
- 你應該根據 Worker 的回傳結果，決定是否修正你的輸出
"""
        
        return f"【角色設定檔】\n{custom_persona}\n\n【系統資訊】\n擁有者 ID：{self.chat_id}\n" + self.memory.get_long_term_system_prompt() + identity_tag + adsp_protocol + worker_protocol + self._get_user_memory_block()

    def _get_user_memory_block(self):
        """生成精簡的 User Memory 區塊（路徑記憶，減少搜尋 token）"""
        if not self._user_paths:
            return ""
        block = "\n<user_memory>\n"
        for key, value in list(self._user_paths.items())[:6]:
            short_val = value if len(value) < 90 else "..." + value[-87:]
            block += f"- {key}: {short_val}\n"
        block += "</user_memory>"
        return block

    def get_cleaned_history(self, max_rounds=None):
        """獲取清洗後的短期記憶，剔除所有引擎生成的視覺標籤，確保上下文純淨
        max_rounds: 若指定，只保留最近 N 輪對話（Sliding Window），舊歷史不載入"""
        cleaned_history = []
        pattern = r"⚙️ \*\*後台追蹤：已調用 [^\n]*\n+"
        
        short_term = self.memory.short_term
        
        # Sliding Window：若指定 max_rounds，只保留最近 N 輪
        if max_rounds:
            # 從後往前數 N 個 user/model 配對
            user_turns = 0
            cutoff_idx = 0
            for i in range(len(short_term) - 1, -1, -1):
                if short_term[i]["role"] == "user":
                    user_turns += 1
                    if user_turns >= max_rounds:
                        cutoff_idx = i
                        break
            short_term = short_term[cutoff_idx:]
        
        for m in short_term:
            content = m["content"]
            if m["role"] == "model":
                content = re.sub(pattern, "", content).strip()
                # 模型回覆過長時濃縮為大綱摘要
                if len(content) > 600:
                    content = self._summarize_long_message(content)
            rc = m.get("reasoning_content")
            # 思考內容濃縮為推理大綱
            if rc and isinstance(rc, str) and len(rc) > 400:
                rc = self._summarize_reasoning(rc)
            cleaned_history.append({
                "role": m["role"], 
                "content": content,
                "reasoning_content": rc
            })
        return cleaned_history

    def _handle_schedule_reminder(self, args):
        if not self.job_queue: return {"status": "error", "message": "排程系統未就緒"}
        task = args.get("task", "提醒")
        delay = args.get("delay_seconds", 60)
        recurrence = args.get("recurrence", None)
        target_time_dt = datetime.now() + timedelta(seconds=delay)
        target_time_str = target_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 🔧 修正：使用 memory 返回的真實 UUID，並修正參數順序
        task_id = self.memory.add_scheduled_task(self.chat_id, task, target_time_dt, recurrence=recurrence)
        
        self.job_queue.run_once(
            self.scheduler_callback,
            delay,
            chat_id=self.chat_id,
            data={"task_id": task_id, "content": task, "recurrence": recurrence}
        )
        recurrence_text = "每日" if recurrence == "daily" else "一次性"
        return {"status": "success", "message": f"✅ 已設定{recurrence_text}提醒：{task}，預計於 {target_time_str} 觸發 (ID: {task_id})"}

    async def save_memory_background(self): self.memory.save_all_force()

    def restore_scheduled_tasks(self):
        if not self.job_queue: return
        
        # 🧹 先批次清理所有過期任務
        removed = self.memory.cleanup_expired_tasks(expire_minutes=5)
        if removed:
            logger.info(f"🧹 啟動時清理 {removed} 個過期排程任務（已物理刪除）")
        
        for t in self.memory.get_pending_scheduled_tasks():
            try:
                raw_delay = (datetime.strptime(t["target_time"], "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds()
                if raw_delay < -300:  # 過期超過 5 分鐘，物理刪除並跳過
                    self.memory.delete_task(t["id"])
                    logger.info(f"🗑️ 過期任務已物理刪除: {t['id']} ({t['task']})")
                    continue
                delay = max(0.5, raw_delay)
                self.job_queue.run_once(
                    self.scheduler_callback, delay, 
                    chat_id=t["chat_id"], 
                    data={
                        "task_id": t["id"], 
                        "content": t["task"], 
                        "recurrence": t.get("recurrence")
                    }
                )
                logger.info(f"📋 已恢復排程: {t['id']} ({t['task']}) → {t['target_time']}")
            except Exception as e:
                logger.error(f"⚠️ 恢復排程任務失敗 ({t.get('id', '?')}): {e}")

    def snapshot_context(self):
        """【跨重啟上下文快照】從 short_term 提取最近對話，規則壓縮為 500 字摘要，寫入 medium_term。
        重啟後 get_long_term_system_prompt() 會自動注入，讓 Alice 記得起重啟前的討論。
        """
        if not self.memory.short_term:
            return
        
        # 提取最近 ~20 則訊息（約 10 輪對話）
        recent = self.memory.short_term[-20:]
        
        # --- 規則壓縮：提取關鍵資訊（零 LLM 成本）---
        extracted = {
            "github_repos": [],      # 提到的 GitHub 專案
            "file_paths": [],        # 提到的檔案路徑
            "tech_keywords": [],     # 技術關鍵字
            "user_messages": [],     # 主人的原始訊息（最近 5 條）
            "pending_topics": []     # 未完成的討論主題
        }
        
        # 技術關鍵字詞庫
        tech_lexicon = [
            "mcp", "server", "api", "python", "docker", "git", "github",
            "stock", "投資", "股票", "gis", "arcmap", "word", "excel",
            "n8n", "排程", "scheduler", "restart", "重啟", "記憶", "memory",
            "deepseek", "gemini", "token", "skill", "備份", "backup",
            "telegram", "bot", "agent", "mega", "兆豐", "database", "db",
            "json", "yaml", "yfinance", "finrobot", "自動化"
        ]
        
        for entry in recent:
            content = entry.get("content", "") if isinstance(entry, dict) else ""
            if not isinstance(content, str):
                continue
            
            content_lower = content.lower()
            
            # 偵測 GitHub 專案名稱（owner/repo 格式）
            import re
            gh_pattern = r'[\w.-]+/[\w.-]+'
            gh_matches = re.findall(gh_pattern, content)
            for m in gh_matches:
                if m not in extracted["github_repos"] and not m.startswith("http"):
                    extracted["github_repos"].append(m)
            
            # 偵測檔案路徑
            path_pattern = r'(?:[A-Z]:[\\/][\w\\/.-]+\.\w{2,5})|(?:~?/?[\w./-]+\.\w{2,5})'
            path_matches = re.findall(path_pattern, content)
            for p in path_matches:
                if p not in extracted["file_paths"]:
                    extracted["file_paths"].append(p)
            
            # 偵測技術關鍵字
            for kw in tech_lexicon:
                if kw.lower() in content_lower and kw not in extracted["tech_keywords"]:
                    extracted["tech_keywords"].append(kw)
            
            # 記錄主人的原始訊息
            if entry.get("role") == "user":
                truncated = content[:120] + ("…" if len(content) > 120 else "")
                if truncated not in extracted["user_messages"]:
                    extracted["user_messages"].append(truncated)
        
        # 只保留最近 5 條主人訊息
        extracted["user_messages"] = extracted["user_messages"][-5:]
        
        # --- 組裝摘要 ---
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [f"【重啟前快照 {timestamp}】"]
        
        if extracted["github_repos"]:
            lines.append(f"- GitHub 專案: {', '.join(extracted['github_repos'][:5])}")
        if extracted["file_paths"]:
            lines.append(f"- 相關檔案: {', '.join(extracted['file_paths'][:3])}")
        if extracted["tech_keywords"]:
            unique_kw = list(dict.fromkeys(extracted["tech_keywords"]))[:8]
            lines.append(f"- 技術主題: {', '.join(unique_kw)}")
        if extracted["user_messages"]:
            lines.append(f"- 主人最後發言: 「{extracted['user_messages'][-1]}」")
        
        summary = "\n".join(lines)
        
        # 硬性限制 500 字
        if len(summary) > 500:
            summary = summary[:497] + "…"
        
        # 寫入 medium_term（格式與 commit_consolidation 一致）
        self.memory.medium_term.append({
            "date": timestamp,
            "summary": summary
        })
        if len(self.memory.medium_term) > 50:
            self.memory.medium_term = self.memory.medium_term[-50:]
        
        logger.info(f"📸 [快照] 已捕獲重啟前上下文 ({len(summary)} 字)")

    async def run_deep_optimization(self):
        try:
            # 1. 執行長期記憶修剪與 FTS 壓縮
            self.memory._prune_long_term_lists()
            self.memory._check_fts_size()
            
            # 2. 強制存檔
            self.memory.save_all_force()
            
            short_term_len = len(self.memory.short_term)
            msg = f"已成功優化記憶庫！\n- 物理檔案已強制存檔。\n- 長期記憶與 FTS 索引已完成修剪與壓縮。\n- 當前短期記憶筆數: {short_term_len} 筆。"
            return True, msg
        except Exception as e:
            logger.error(f"Deep Optimization Error: {e}")
            return False, f"優化記憶庫時發生錯誤: {e}"

    async def _maybe_trigger_self_review(self):
        """背景自我審查觸發（借鑒 hermes-agent _run_review_in_thread）。
        每次對話後遞增計數器，達閾值時非阻塞觸發全面審查。"""
        try:
            review_skill = self.tools.skills.get("self_review_skill")
            if not review_skill:
                return  # self_review_skill 未載入，跳過

            # 遞增計數器
            counter = review_skill.increment_counter(self)

            # 從 settings 讀取觸發間隔（預設 20 輪）
            interval = self.memory.long_term.get("settings", {}).get(
                "self_review_interval", 20
            )

            if counter >= interval:
                logger.info(f"🔍 [Self-Review] 觸發背景審查（counter={counter}, interval={interval}）")
                # 非阻塞執行全面審查
                context = {
                    "agent": self,
                    "available_tools": list(self.tools.tool_to_skill_map.keys()),
                    "tool_definitions": self.tools.get_tool_definitions(),
                    "tool_to_skill_map": self.tools.tool_to_skill_map,
                    "memory": self.memory,
                }
                result = review_skill.execute("self_review", {"scope": "full"}, context)

                if result.get("status") == "success":
                    report = result.get("report", {})
                    health = report.get("overall_health", "unknown")
                    warnings_count = len(report.get("warnings", []))
                    suggestions_count = len(report.get("suggestions", []))

                    if health == "critical" or warnings_count > 3:
                        # 有嚴重問題 → 發送 Telegram 警告
                        health_emoji = "🔴" if health == "critical" else "🟡"
                        msg = (
                            f"{health_emoji} **自動自我審查報告**\n"
                            f"• 整體健康度：`{health}`\n"
                            f"• 警告數：{warnings_count}\n"
                            f"• 建議數：{suggestions_count}\n"
                            f"• 記憶健康分：{report.get('sections', {}).get('memory', {}).get('health_score', '?')}\n"
                            f"• 技能健康分：{report.get('sections', {}).get('skills', {}).get('health_score', '?')}\n"
                            f"• 架構健康分：{report.get('sections', {}).get('architecture', {}).get('health_score', '?')}\n\n"
                            f"使用 `/self_review` 查看完整報告"
                        )
                        await self.tools.execute_tool("telegram_operation", {
                            "action": "send_message",
                            "text": msg,
                            "chat_id": str(self.chat_id)
                        })
                else:
                    logger.warning(f"Self-review 執行異常: {result}")
        except Exception as e:
            logger.error(f"Self-review 觸發失敗: {e}", exc_info=True)

    async def trigger_proactive_chat(self):
        # 避免頻繁騷擾：如果距離上次互動小於 30 分鐘，不主動發話
        time_diff = datetime.now() - self.last_interaction_time
        if time_diff.total_seconds() < 1800: # 30 分鐘
            return None
            
        prompt = "【系統提示：你現在處於陪伴模式。主人已經有一段時間沒有跟你說話了。請根據你對主人的了解（參考核心記憶庫），主動發起一個溫馨、貼心且簡短的話題或問候（不超過 50 字，不要使用 Markdown 標籤，不要使用句號結尾）。】"
        try:
            engine = self.get_current_engine()
            system_instruction = self._get_system_instruction()
            response_text = await engine.generate_response(
                prompt, 
                user_input=prompt, 
                is_file=False, 
                media_files=None, 
                system_instruction=system_instruction
            )
            self.last_interaction_time = datetime.now() # 更新時間防止連續觸發
            return response_text
        except Exception as e:
            logger.error(f"Proactive Chat Error: {e}")
            return None

    def _summarize_long_message(self, content, max_chars=600):
        """將過長的模型回覆濃縮為結構化大綱摘要，保留語義而非硬截斷"""
        if len(content) <= max_chars:
            return content
        
        lines = content.split("\n")
        summary_parts = []
        
        # 關鍵符號行（✅❌📊🔧⚠️🚨🛑📋🔍💡🎯）
        key_symbols = re.compile(r'[✅❌📊🔧⚠️🚨🛑📋🔍💡🎯🟢🔴🟡📸]')
        # 標題行
        heading = re.compile(r'^(#{1,3}\s|\*\*.*\*\*|##\s|###\s)')
        # 表格行
        table_row = re.compile(r'^\|.+\|')
        # 關鍵詞行
        keyword_line = re.compile(r'(Phase|API|Skill|token|檔案|路徑|端點|部署|完成|修復|錯誤|成功|失敗)')
        
        kept_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if heading.match(stripped) or table_row.match(stripped) or key_symbols.search(stripped) or keyword_line.search(stripped):
                kept_lines.append(stripped)
        
        if kept_lines:
            summary_parts.extend(kept_lines[:8])  # 最多保留 8 行關鍵行
            summary_parts.append("…[摘要濃縮]")
            return "\n".join(summary_parts)
        
        # Fallback：保留首段 + 尾段
        half = max_chars // 2
        return content[:half] + "\n…[中段省略]…\n" + content[-half:]

    def _summarize_reasoning(self, rc, max_chars=400):
        """將思考內容濃縮為推理大綱，提取關鍵決策句"""
        if len(rc) <= max_chars:
            return rc
        
        # 提取含推理關鍵詞的句子
        reasoning_keywords = re.compile(r'[^。！？\n]*(?:結論|因此|必須|決定|關鍵|總結|核心|重點|首先|最終|選擇|判斷|確認|建議)[^。！？\n]*[。！？]?')
        key_sentences = reasoning_keywords.findall(rc)
        
        if key_sentences:
            # 保留開頭 120 字 + 關鍵推理句 + 結尾 80 字
            head = rc[:120].strip()
            tail = rc[-80:].strip()
            unique_sentences = list(dict.fromkeys(key_sentences))[:5]  # 最多 5 句
            return head + "\n…[推理摘要]…\n" + " ".join(unique_sentences) + "\n…\n" + tail
        
        # Fallback：保留頭尾
        half = max_chars // 2
        return rc[:half] + "\n…[推理截斷]…\n" + rc[-half:]

    def on_exit(self): self.memory.save_all_force()
