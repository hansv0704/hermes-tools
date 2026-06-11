import asyncio
import os
import sys
import json
import time
import logging
import traceback
import subprocess
import re
import signal
import atexit
import io
from pathlib import Path
from datetime import datetime

# --- 第三方庫依賴 ---
def split_message(text, max_chars=4000):
    """將文字安全拆分為多個符合長度限制的區塊"""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        
        # 嘗試尋找最後一個換行符號，避免從字中間斷開
        split_at = text.rfind('\n', 0, max_chars)
        if split_at == -1:
            split_at = max_chars  # 如果沒換行，就硬切
            
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks

# --- 第三方库依赖 ---
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import google.generativeai as genai
from PIL import Image, ImageGrab

# --- 初始化設定 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
load_dotenv()

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Alice_System")

# ==========================================
# 模組 1: API Key 管理
# ==========================================
class APIKeyManager:
    def __init__(self):
        keys_str = os.getenv("GOOGLE_API_KEYS", "")
        self.keys = [k.strip() for k in keys_str.replace("\n", ",").split(",") if k.strip()]
        if not self.keys:
            logger.critical("❌ 未在 .env 找到 GOOGLE_API_KEYS")
            self.keys = []
        self.current_key_index = 0

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_key_index]

    def rotate_key(self):
        if not self.keys: return None
        prev_key = self.keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        new_key = self.keys[self.current_key_index]
        logger.warning(f"🔄 API Key 切換: {prev_key[:5]}... -> {new_key[:5]}...")
        return new_key

# ==========================================
# 模組 2: 記憶系統
# ==========================================
class MemorySystem:
    def __init__(self, base_dir="memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        self.short_term_file = self.base_dir / "short_term.json"
        self.medium_term_file = self.base_dir / "medium_term.json"
        self.long_term_file = self.base_dir / "long_term.json"
        self.archive_file = self.base_dir / "chat_archive.txt"
        
        self.short_term = []
        self.medium_term = []
        self.long_term = {
            "user_info": [], "arcmap_habits": [], "coding_style": [],
            "preferences": [], "other": []
        }
        
        self.load_all()
        self.unsaved_changes = False

    def load_all(self):
        if self.short_term_file.exists():
            try:
                with open(self.short_term_file, "r", encoding="utf-8") as f:
                    self.short_term = json.load(f)
            except: self.short_term = []
            
        if self.medium_term_file.exists():
            try:
                with open(self.medium_term_file, "r", encoding="utf-8") as f:
                    self.medium_term = json.load(f)
            except: self.medium_term = []
            
        if self.long_term_file.exists():
            try:
                with open(self.long_term_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k in self.long_term: self.long_term[k] = v
            except: pass
        else:
            self.save_long()

    def save_short_only(self):
        try:
            with open(self.short_term_file, "w", encoding="utf-8") as f:
                json.dump(self.short_term, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"短期記憶存檔失敗: {e}")

    def save_all_force(self):
        try:
            self.save_short_only()
            with open(self.medium_term_file, "w", encoding="utf-8") as f:
                json.dump(self.medium_term, f, ensure_ascii=False, indent=2)
            with open(self.long_term_file, "w", encoding="utf-8") as f:
                json.dump(self.long_term, f, ensure_ascii=False, indent=2)
            logger.info("💾 [系統] 所有記憶已完整寫入硬碟。")
        except Exception as e:
            logger.error(f"完整存檔失敗: {e}")

    def archive_old_messages(self, messages):
        if not messages: return
        try:
            with open(self.archive_file, "a", encoding="utf-8") as f:
                for m in messages:
                    f.write(f"[{m['timestamp']}] {m['role']}: {m['content']}\n")
        except Exception as e:
            logger.error(f"Archiving failed: {e}")

    def add_short_term(self, role, content):
        entry = {
            "role": role, 
            "content": content, 
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.short_term.append(entry)
        self.unsaved_changes = True
        
        if len(self.short_term) > 100: 
            to_archive = self.short_term[:20]
            self.short_term = self.short_term[20:]
            self.archive_old_messages(to_archive)

        self.save_short_only()
        return len(self.short_term)

    def get_recent_conversation_text(self, count=30):
        recent = self.short_term[-count:]
        if not recent: return ""
        return "\n".join([f"{m['role']}: {m['content']}" for m in recent])

    def update_from_analysis(self, analysis_data):
        updated = False
        if analysis_data.get("summary"):
            self.medium_term.append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "summary": analysis_data["summary"]
            })
            updated = True
        
        updates = analysis_data.get("long_term_updates", {})
        for cat, items in updates.items():
            if cat in self.long_term and items:
                for item in items:
                    if item not in self.long_term[cat]:
                        self.long_term[cat].append(item)
                        logger.info(f"🧠 [新知識習得] {cat}: {item}")
                        updated = True
        return updated

    def get_long_term_system_prompt(self):
        context = "【🔥 核心知識庫 (Long-term)】\n"
        has_data = False
        for category, items in self.long_term.items():
            if items:
                has_data = True
                context += f"[{category.upper()}]:\n" + "\n".join([f"- {i}" for i in items]) + "\n"
        
        recent = self.medium_term[-3:]
        if recent:
            has_data = True
            context += "\n【📜 近期背景 (Medium-term)】\n" + "\n".join([f"- {r['summary']}" for r in recent])
            
        return context if has_data else ""

# ==========================================
# 模組 3: 核心 Agent
# ==========================================
class PersonalAgent:
    def __init__(self):
        self.key_manager = APIKeyManager()
        self.memory = MemorySystem()
        
        self.default_model = os.getenv("DEFAULT_MODEL", "gemini-3-flash-preview")
        self.models_list = [self.default_model, "gemini-3.5-flash"]
        self.current_model_index = 0
        
        self.configure_genai()
        self.chat_session = None
        self.init_model_session()
        
        atexit.register(self.on_exit)

    def configure_genai(self):
        key = self.key_manager.get_current_key()
        if key: genai.configure(api_key=key)

    def init_model_session(self):
        model_name = self.models_list[self.current_model_index]
        logger.info(f"初始化模型 Session: {model_name}")
        
        system_prompt = (
            "你是由 Python 驅動的個人工作助理 (Alice)。"
            "請以繁體中文回答。"
            "回答請簡潔、直接、專業。\n\n" + 
            self.memory.get_long_term_system_prompt()
        )

        try:
            self.model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt
            )
            
            gemini_history = []
            for m in self.memory.short_term:
                gemini_history.append({"role": m["role"], "parts": [{"text": m["content"]}]})
                
            self.chat_session = self.model.start_chat(history=gemini_history)
        except Exception as e:
            logger.error(f"Session 初始化失敗: {e}")
            self.rotate_model()

    def rotate_model(self):
        self.current_model_index = (self.current_model_index + 1) % len(self.models_list)
        time.sleep(1)
        self.init_model_session()

    def perform_final_consolidation_sync(self):
        logger.info("🛑 [系統關閉程序] 正在執行最後一次記憶總結...")
        conversation_text = self.memory.get_recent_conversation_text(50)
        if not conversation_text: return

        prompt = (
            "【系統關閉前總結】\n"
            "請分析這段對話，提取使用者偏好或重要資訊，並回傳 JSON：\n"
            "{\n"
            '  "summary": "...",\n'
            '  "long_term_updates": { "user_info": [], "arcmap_habits": [], "coding_style": [], "preferences": [], "other": [] }\n'
            "}\n"
            f"內容：\n{conversation_text}"
        )

        try:
            response = self.model.generate_content(prompt)
            text_res = response.text.strip()
            if "```" in text_res:
                text_res = re.sub(r"```json\s*", "", text_res)
                text_res = re.sub(r"```\s*", "", text_res)
            
            data = json.loads(text_res)
            updated = self.memory.update_from_analysis(data)
            if updated: logger.info("✅ 關閉前記憶更新完成。")
        except Exception as e:
            logger.error(f"⚠️ 最終總結失敗: {e}")

    def on_exit(self):
        if self.memory.unsaved_changes:
            self.perform_final_consolidation_sync()
        self.memory.save_all_force()

    def capture_screen(self):
        try:
            screenshot = ImageGrab.grab()
            screenshot.thumbnail((1920, 1920))
            return screenshot
        except: return None

    async def consolidate_background(self):
        logger.info("🧹 [背景任務] 分析對話中...")
        conversation_text = self.memory.get_recent_conversation_text(30)
        if not conversation_text: return

        prompt = (
            "分析最近30句對話，提取記憶，回傳 JSON: { \"summary\": \"...\", \"long_term_updates\": { ... } }\n"
            f"內容：\n{conversation_text}"
        )
        try:
            temp_model = genai.GenerativeModel(self.models_list[self.current_model_index])
            response = await temp_model.generate_content_async(prompt)
            text_res = response.text.strip()
            if "```" in text_res:
                text_res = re.sub(r"```json\s*", "", text_res)
                text_res = re.sub(r"```\s*", "", text_res)
            
            data = json.loads(text_res)
            updated = self.memory.update_from_analysis(data)
            if updated: self.memory.save_all_force()
        except Exception: pass

    async def generate_response(self, user_input, is_file=False):
        """
        支援純文字或檔案內容輸入
        user_input: 可以是使用者的話，或者是 "檔案內容 + 使用者註解"
        """
        content_parts = [user_input]
        
        # 只有在純文字模式下且有關鍵字時才截圖 (如果是傳檔案就不用截圖了)
        if not is_file and any(k in str(user_input).lower() for k in ["看", "螢幕", "screen", "截圖"]):
            scr = self.capture_screen()
            if scr: content_parts.append(scr)

        for attempt in range(2):
            try:
                if not self.chat_session: self.init_model_session()
                
                response = await self.chat_session.send_message_async(content_parts)
                reply_text = response.text
                
                # 紀錄對話 (如果是檔案，只記錄前100字避免記憶爆炸)
                log_text = user_input if not is_file else f"[使用者上傳了檔案] {user_input[:100]}..."
                
                self.memory.add_short_term("user", log_text)
                current_count = self.memory.add_short_term("model", reply_text)

                if current_count > 0 and current_count % 30 == 0:
                    asyncio.create_task(self.consolidate_background())

                return reply_text

            except Exception as e:
                logger.error(f"生成錯誤: {e}")
                self.key_manager.rotate_key()
                self.configure_genai()
                self.init_model_session()
                await asyncio.sleep(1)
        
        return "❌ 系統連線問題，請稍後再試。"

# ==========================================
# 模組 4: Telegram Bot
# ==========================================
agent = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Alice 已啟動\n"
        "1. 📷 輸入「看螢幕」可觸發截圖。\n"
        "2. 📄 直接拖曳檔案進來，我可以讀取並分析程式碼。"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    owner_id = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id and str(chat_id) != owner_id: return

    user_text = update.message.text
    reply = await agent.generate_response(user_text, is_file=False)
    
    for chunk in split_message(reply):
        try:
            await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)
        except:
            await update.message.reply_text(chunk)

# 新增：檔案處理器
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    owner_id = os.getenv("TELEGRAM_OWNER_ID")
    if owner_id and str(chat_id) != owner_id: return

    document = update.message.document
    file_name = document.file_name
    
    # 過濾檔案類型，避免讀取二進制檔 (exe, zip 等)
    allowed_extensions = ['.py', '.txt', '.json', '.md', '.csv', '.html', '.css', '.js', '.bat', '.sh']
    file_ext = os.path.splitext(file_name)[1].lower()
    
    if file_ext not in allowed_extensions:
        await update.message.reply_text(f"⚠️ 我目前只支援讀取文字與程式碼檔案 ({', '.join(allowed_extensions)})")
        return

    await update.message.reply_text(f"📄 正在讀取檔案 `{file_name}` ...", parse_mode=constants.ParseMode.MARKDOWN)

    try:
        # 下載檔案到記憶體
        new_file = await context.bot.get_file(document.file_id)
        byte_array = await new_file.download_as_bytearray()
        
        # 解碼內容
        try:
            file_content = byte_array.decode('utf-8')
        except UnicodeDecodeError:
            # 嘗試用 big5 解碼 (針對舊 Windows 檔案)
            file_content = byte_array.decode('big5', errors='ignore')

        # 組合 Prompt
        caption = update.message.caption if update.message.caption else "請分析這份程式碼，並告訴我如何改進或是修復 Bug。"
        full_prompt = (
            f"【使用者上傳檔案內容】\n"
            f"檔名: {file_name}\n"
            f"內容:\n```\n{file_content}\n```\n\n"
            f"【使用者問題】: {caption}"
        )
        
        # 傳送給 Agent 處理
        reply = await agent.generate_response(full_prompt, is_file=True)
        
        for chunk in split_message(reply):
            try:
                await update.message.reply_text(chunk, parse_mode=constants.ParseMode.MARKDOWN)
            except:
                await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"檔案處理失敗: {e}")
        await update.message.reply_text("❌ 檔案讀取失敗，請確認檔案格式是否正確。")

async def manual_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if agent:
        agent.memory.save_all_force()
        await update.message.reply_text("💾 所有記憶已強制同步到硬碟。")

# ==========================================
# 模組 5: 啟動入口
# ==========================================
RESTART_EXIT_CODE = 42

def run_worker():
    global agent
    if not os.getenv("TG_PROXY"):
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(k, None)

    try:
        agent = PersonalAgent()
    except Exception as e:
        logger.critical(f"Agent Init Failed: {e}")
        return

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    builder = ApplicationBuilder().token(tg_token)
    if os.getenv("TG_PROXY"): 
        builder = builder.proxy_url(os.getenv("TG_PROXY"))

    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("save", manual_save))
    
    # 註冊文字與檔案處理器
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print(f"🚀 Alice Worker 啟動 (支援檔案讀取)")
    
    app.run_polling()

def run_runner():
    script_file = sys.argv[0]
    while True:
        logger.info("--- 啟動 Worker ---")
        p = subprocess.Popen([sys.executable, script_file], env=os.environ.copy())
        try:
            p.wait()
        except KeyboardInterrupt:
            logger.info("正在請求子進程安全關閉 (請稍候)...")
            p.send_signal(signal.SIGINT)
            p.wait()
            sys.exit(0)
            
        if p.returncode == RESTART_EXIT_CODE:
            continue
        if p.returncode != 0:
            time.sleep(3)
        else:
            sys.exit(0)

if __name__ == "__main__":
    if os.environ.get("MAIBOT_WORKER") == "1":
        run_worker()
    else:
        os.environ["MAIBOT_WORKER"] = "1"
        run_runner()