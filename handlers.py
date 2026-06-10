import os
import sys
import random
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import ContextTypes
from config import logger
from skills.heartbeat_skill import HeartbeatMonitor, HeartbeatConfig, _heartbeat_monitor

# --- 輔助函式：獲取當前所有模式狀態 ---
def get_status_summary(agent):
    settings = agent.memory.long_term.get("settings", {})
    notify = "ON" if settings.get("notify_enabled") else "OFF"
    chat = "ON" if agent.is_chat_mode else "OFF"
    monitor = "ON" if settings.get("monitor_enabled") else "OFF"
    lock = "已鎖定" if agent.tools.safety_lock else "已解鎖"
    
    # 動態引擎顯示：反映雙核心路由邏輯
    engine = "DeepSeek (工作核心)" if not agent.is_chat_mode else "Gemini (感性核心)"
    model_name = agent.models_list[agent.current_model_index]
    
    return (
        f"\n\n📊 **當前系統狀態**\n"
        f"──────────────────────\n"
        f"🧠 路由引擎: `{engine}`\n"
        f"🤖 當前模型: `{model_name}`\n"

        f"🔔 通知權限: `{notify}`\n"
        f"💬 聊天模式: `{chat}`\n"
        f"📈 背景監控: `{monitor}`\n"
        f"🔒 安全鎖定: `{lock}`"
    )

# --- 輔助函式：安全的訊息發送器 ---
async def send_message_safe(bot, chat_id, text, retries=3, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except (NetworkError, TimedOut) as e:
            if attempt == retries - 1: raise e
            await asyncio.sleep(delay)
            delay *= 2
        except Exception as e: raise e

def split_message(text, max_chars=4000):
    """將文字安全拆分為多個符合長度限制的區塊"""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        
        split_at = text.rfind('\n', 0, max_chars)
        if split_at == -1:
            split_at = max_chars
            
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        agent.update_interaction_time()
        if hasattr(agent, "tools"): agent.tools.reload_skills()
        if hasattr(agent, "init_model_session"): agent.init_model_session()
    await update.message.reply_text(f"🚀 Alice 雙核心系統已就緒。{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 正在執行完全重啟 (Full Restart)... 請稍候。")
    agent = context.bot_data.get("agent")
    if agent:
        agent.snapshot_context()  # 📸 先捕獲重啟前上下文
        agent.memory.save_all_force()
    with open("restart.flag", "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f.flush()
        os.fsync(f.fileno())
    os._exit(42)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    help_text = (
        "📜 **Alice 系統指令清單**\n\n"
        "🛠️ **基本操作**\n"
        "• `/start` - 重新初始化 Session\n"
        "• `/restart` - 完全重啟系統 (載入底層代碼變更)\n"
        "• `/save` - 強制儲存記憶\n"
        "• `/cleanup` - 深度優化記憶庫\n"
        "• `/help` - 顯示此清單\n\n"
        "🧠 **雙核心路由引擎**\n"
        "• **工作模式** (預設): 優先使用 `DeepSeek-V4-Pro` 進行深度思考與編碼。\n"
        "• **聊天模式**: 優先使用 `Gemini Flash 系列` 確保情感細膩與節省成本。\n"
        "• `/model [編號]` - 強制鎖定特定模型\n"
        "• `/model auto` - 解除鎖定，恢復自動路由\n\n"
        "🗣️ **語音設定**\n"
        "• `/voice [on/off/1-6]` - 切換語音模式與聲線\n\n"
        "🔒 **安全控制**\n"
        "• `/lock` - 鎖定電腦操作權限\n"
        "• `/unlock` - 解鎖電腦操作權限\n\n"
        "⏹️ **中斷指令**\n"
        "• **[F10] 快捷鍵** - 立即中斷當前任務 (物理級中斷)\n\n"
        "📡 **模式切換**\n"
        "• `/notify_on` / `/notify_off` - 主動通知權限\n"
        "• `/chat_on` / `/chat_off` - 切換工作/聊天核心\n"
        "• `/monitor_on` / `/monitor_off` - 背景數據監控\n"

        "🌍 **GIS 專家監控**\n"
        "💓 **Heartbeat 背景監控**\n"
        "• `/start_heartbeat [interval=秒] [watch=代號] [stock] [nogis] [nosys]` - 啟動\n"
        "• `/stop_heartbeat` - 停止監控\n"
        "• `/heartbeat` - 查詢監控狀態\n\n"
        "• `/gis_check` - 執行專家級巡檢\n"
        "• `/gis_status` - 查看站點歷史趨勢\n\n"
        "📦 **系統備份與還原**\n"
        "• `/backup` - 雲端全量備份\n"
        "• `/restore_list` - 列出還原點\n"
        "• `/restore [時間戳記]` - 執行物理級回溯\n\n"
        "🎯 **投資代理人**\n"
        "• 請前往投資代理人儀表板 (Port 5002) 操作\n"
        "• TG 僅作為通知管道，完整功能請使用 Web UI"
    )
    if agent:
        help_text += get_status_summary(agent)
    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if not agent: return
    agent.update_chat_id(update.effective_chat.id)
    if not context.args:
        models = agent.models_list
        current_idx = agent.current_model_index
        text = "🤖 **可用模型清單**\n\n"
        for i, m in enumerate(models):
            status = " (當前使用中 ✨)" if i == current_idx else ""
            text += f"{i}. `{m}`{status}\n"
        text += "\n💡 **提示**: 系統已開啟自動路由。使用 `/model [編號]` 將強制鎖定模型，使用 `/model auto` 解除鎖定。"
        await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)
        return
    
    cmd_arg = context.args[0].lower()
    if cmd_arg == "auto":
        agent.forced_model_index = None
        await update.message.reply_text(f"✅ **已解除模型鎖定，恢復自動路由。**{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)
        return
        
    try:
        idx = int(cmd_arg)
        success, msg = agent.switch_model(idx)
        if success:
            agent.forced_model_index = idx
            msg += "\n🔒 **已強制鎖定使用此模型 (直到輸入 /model auto 解除)。**"
        await update.message.reply_text(f"{msg}{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)
    except (ValueError, IndexError):
        await update.message.reply_text("⚠️ 請輸入正確的模型編號 or 'auto'。")

async def gis_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        await update.message.reply_text("🔍 正在調用『GIS 專家大腦』執行深度巡檢，請稍候...")
        reply = await agent.generate_response("請執行 /gis_check 專家巡檢。")
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)

async def gis_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        await update.message.reply_text("📊 正在彙整 GIS 站點趨勢報告...")
        reply = await agent.generate_response("請執行 /gis_status 查看站點趨勢。")
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        await update.message.reply_text("📦 正在打包系統架構並上傳至雲端備份...")
        reply = await agent.generate_response("請執行 backup_architecture_to_cloud 工具。")
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)

async def restore_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        await update.message.reply_text("📜 正在獲取系統還原點清單...")
        reply = await agent.generate_response("請執行 list_restore_points 工具。")
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)

async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        if not context.args:
            await update.message.reply_text("⚠️ 請提供還原點時間戳記，例如：`/restore 20260511_120000`。可先透過 `/restore_list` 查詢。")
            return
        timestamp = context.args[0]
        await update.message.reply_text(f"⚠️ 正在執行物理級回溯至 {timestamp}... 系統將在完成後自動重啟。")
        reply = await agent.generate_response(f"請執行 perform_restoration 工具，時間戳記為 {timestamp}。")
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("gis_ack|"):
        _, st_id, s_type = data.split("|")
        uid = f"{st_id}_{s_type}"
        gis_dir = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
        default_path = os.path.join(gis_dir, "sensor_config.json")
        config_path_str = os.getenv("GIS_SENSOR_CONFIG_PATH", default_path)
        config_path = Path(config_path_str)
        if not config_path.exists():
            await query.edit_message_text(text=f"❌ 找不到設定檔。")
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config.setdefault("acknowledged_set", []).append(uid)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            await query.edit_message_text(text=f"✅ 已將 {uid} 標記為『確認異常』。")
        except Exception as e:
            await query.edit_message_text(text=f"❌ 調整配置失敗: {e}")

async def notify_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        settings = agent.memory.long_term.get("settings", {})
        settings["notify_enabled"] = True
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"✅ [主動通知模式] 已切換：開啟{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def notify_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        settings = agent.memory.long_term.get("settings", {})
        settings["notify_enabled"] = False
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"❌ [主動通知模式] 已切換：關閉{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def chat_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(chat_id)
        agent.is_chat_mode = True
        agent.update_interaction_time()
        settings = agent.memory.long_term.get("settings", {})
        settings["chat_mode_enabled"] = True
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        if context.job_queue:
            for job in context.job_queue.get_jobs_by_name(f"chat_mode_{chat_id}"): job.schedule_removal()
            context.job_queue.run_repeating(proactive_chat_job, interval=60, chat_id=chat_id, name=f"chat_mode_{chat_id}")
        await update.message.reply_text(f"💕 [聊天模式] 已切換：開啟{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def chat_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(chat_id)
        agent.is_chat_mode = False
        settings = agent.memory.long_term.get("settings", {})
        settings["chat_mode_enabled"] = False
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        if context.job_queue:
            for job in context.job_queue.get_jobs_by_name(f"chat_mode_{chat_id}"): job.schedule_removal()
        await update.message.reply_text(f"💼 [聊天模式] 已切換：關閉{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def monitor_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        settings = agent.memory.long_term.get("settings", {})
        settings["monitor_enabled"] = True
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"📈 [背景監控模式] 已切換：開啟{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def monitor_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        settings = agent.memory.long_term.get("settings", {})
        settings["monitor_enabled"] = False
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"📉 [背景監控模式] 已切換：關閉{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def cleanup_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)
        success, msg = await agent.run_deep_optimization()
        await update.message.reply_text(f"{'✅' if success else '❌'} {msg}")

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if not agent: return
    agent.update_chat_id(update.effective_chat.id)
    if not context.args:
        status = "開啟" if agent.tools.tts.enabled else "關閉"
        await update.message.reply_text(f"🗣️ 語音設定 (目前: {status})")
        return
    cmd = context.args[0].lower()
    settings = agent.memory.long_term.get("settings", {})
    if cmd == "off": agent.tools.tts.enabled = False
    elif cmd == "on": agent.tools.tts.enabled = True
    elif cmd in ["1", "2", "3", "4", "5", "6"]:
        mapping = {"1":"tw_female", "2":"tw_male", "3":"cn_female", "4":"gemini_puck", "5":"gemini_zephyr", "6":"gemini_fenrir"}
        agent.tools.tts.current_voice = mapping[cmd]
        agent.tools.tts.enabled = True
    settings["voice_enabled"] = agent.tools.tts.enabled
    settings["voice_id"] = agent.tools.tts.current_voice
    agent.memory.long_term["settings"] = settings
    agent.memory.save_all_force()
    await update.message.reply_text(f"✅ 語音設定已更新。{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent: 
        agent.update_chat_id(update.effective_chat.id)
        msg = agent.tools.set_safety_lock(True)
        settings = agent.memory.long_term.get("settings", {})
        settings["safety_lock"] = True
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"{msg}{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent: 
        agent.update_chat_id(update.effective_chat.id)
        msg = agent.tools.set_safety_lock(False)
        settings = agent.memory.long_term.get("settings", {})
        settings["safety_lock"] = False
        agent.memory.long_term["settings"] = settings
        agent.memory.save_all_force()
        await update.message.reply_text(f"{msg}{get_status_summary(agent)}", parse_mode=constants.ParseMode.MARKDOWN)

async def proactive_chat_job(context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    chat_id = context.job.chat_id
    if not agent or not agent.is_chat_mode: return
    text = await agent.trigger_proactive_chat()
    if text: await send_message_safe(context.bot, chat_id, text)

async def perform_scheduled_task(context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        task_data = context.job.data
        task_id = task_data.get("task_id") if isinstance(task_data, dict) else None
        task_content = task_data.get("content") if isinstance(task_data, dict) else task_data
        recurrence = task_data.get("recurrence") if isinstance(task_data, dict) else None
        
        reply = await agent.generate_response(f"執行排程任務：『{task_content}』", is_file=False)
        if reply:
            for chunk in split_message(reply):
                await send_message_safe(context.bot, context.job.chat_id, chunk)
            
        # 🔄 循環任務處理：若為每日任務，先排定下次再刪除本次
        if recurrence == "daily":
            next_time_dt = datetime.now() + timedelta(days=1)
            next_task_id = agent.memory.add_scheduled_task(
                context.job.chat_id, task_content, next_time_dt, recurrence="daily"
            )
            context.job_queue.run_once(
                perform_scheduled_task, 24 * 3600, 
                chat_id=context.job.chat_id, 
                data={
                    "task_id": next_task_id, 
                    "content": task_content, 
                    "recurrence": "daily"
                }
            )
            logger.info(f"🔁 已自動排定下次循環任務：{next_time_dt.strftime('%Y-%m-%d %H:%M:%S')} (ID: {next_task_id})")
        
        # 🗑️ 執行後物理刪除（一次性與循環都要刪除本次任務，不留記錄）
        if task_id:
            try:
                agent.memory.delete_task(task_id)
                logger.info(f"🗑️ 排程任務 {task_id} 已物理刪除。")
            except Exception as e:
                logger.error(f"⚠️ 刪除任務 {task_id} 失敗: {e}")

async def start_heartbeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """啟動 Heartbeat 背景監控"""
    global _heartbeat_monitor
    agent = context.bot_data.get("agent")
    chat_id = update.effective_chat.id
    if agent:
        agent.update_chat_id(chat_id)

    if _heartbeat_monitor and _heartbeat_monitor._running:
        status = _heartbeat_monitor.get_status()
        await update.message.reply_text(
            f"⚠️ Heartbeat 已在運行中\n"
            f"• 巡檢次數: {status['cycle_count']}\n"
            f"• 警報數: {status['alerts_sent']}\n"
            f"• 間隔: {status['interval_seconds']}s",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    # 解析參數
    interval = 300
    gis_on = True
    stock_on = False
    system_on = True
    watchlist = {}

    if context.args:
        for arg in context.args:
            if arg.startswith("interval="):
                try:
                    interval = int(arg.split("=")[1])
                except ValueError:
                    pass
            elif arg.startswith("watch="):
                symbols = arg.split("=")[1].split(",")
                for s in symbols:
                    watchlist[s.strip().upper()] = 5.0
            elif arg == "stock":
                stock_on = True
            elif arg == "nogis":
                gis_on = False
            elif arg == "nosys":
                system_on = False

    config = HeartbeatConfig(
        interval_seconds=interval,
        gis_enabled=gis_on,
        stock_enabled=stock_on,
        system_enabled=system_on,
        stock_watchlist=watchlist,
        telegram_chat_id=str(chat_id)
    )

    _heartbeat_monitor = HeartbeatMonitor(config)

    # 設定 Telegram 通知回調
    async def notify_cb(msg: str):
        from config import BOT_TOKEN
        import httpx
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"chat_id": chat_id, "text": msg})

    _heartbeat_monitor.set_notify_callback(notify_cb)

    result = await _heartbeat_monitor.start()
    await update.message.reply_text(
        f"✅ Heartbeat 監控已啟動\n"
        f"• 間隔: {interval}s\n"
        f"• GIS: {'✅' if gis_on else '❌'}\n"
        f"• 股票: {'✅' if stock_on else '❌'} ({len(watchlist)} 檔)\n"
        f"• 系統: {'✅' if system_on else '❌'}",
        parse_mode=constants.ParseMode.MARKDOWN
    )


async def stop_heartbeat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止 Heartbeat 背景監控"""
    global _heartbeat_monitor
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)

    if not _heartbeat_monitor or not _heartbeat_monitor._running:
        await update.message.reply_text("⚠️ Heartbeat 未在運行中。")
        return

    result = await _heartbeat_monitor.stop()
    await update.message.reply_text(
        f"⏹️ Heartbeat 已停止\n"
        f"• 總巡檢: {result['total_cycles']} 次\n"
        f"• 總警報: {result['total_alerts']} 則",
        parse_mode=constants.ParseMode.MARKDOWN
    )


async def heartbeat_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查詢 Heartbeat 狀態"""
    global _heartbeat_monitor
    agent = context.bot_data.get("agent")
    if agent:
        agent.update_chat_id(update.effective_chat.id)

    if not _heartbeat_monitor:
        await update.message.reply_text("📊 Heartbeat 尚未初始化。使用 `/start_heartbeat` 啟動。")
        return

    status = _heartbeat_monitor.get_status()
    state = "🟢 運行中" if status['running'] else "🔴 已停止"
    await update.message.reply_text(
        f"📊 Heartbeat 狀態: {state}\n"
        f"• 巡檢間隔: {status['interval_seconds']}s\n"
        f"• 已完成巡檢: {status['cycle_count']} 次\n"
        f"• 已發警報: {status['alerts_sent']} 則\n"
        f"• 上次巡檢: {status['last_cycle'] or 'N/A'}\n"
        f"• GIS 監控: {'✅' if status['gis_enabled'] else '❌'}\n"
        f"• 股票監控: {'✅' if status['stock_enabled'] else '❌'} ({', '.join(status['watchlist_symbols']) or '無'})\n"
        f"• 系統監控: {'✅' if status['system_enabled'] else '❌'}",
        parse_mode=constants.ParseMode.MARKDOWN
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if not agent: return
    chat_id = update.effective_chat.id
    agent.update_chat_id(chat_id)
    user_text = update.message.text.strip()
    fallback_commands = {
        "/notify_on": notify_on_command, "/notify_off": notify_off_command,
        "/chat_on": chat_on_command, "/chat_off": chat_off_command,
        "/monitor_on": monitor_on_command, "/monitor_off": monitor_off_command,
        "/restart": restart_command, "/help": help_command,
        "/start": start, "/lock": lock_command, "/unlock": unlock_command,
        "/save": manual_save, "/cleanup": cleanup_memory_command,
        "/voice": voice_command, "/gis_check": gis_check_command,
        "/gis_status": gis_status_command,
        "/backup": backup_command,
        "/restore_list": restore_list_command,
        "/restore": restore_command,
        "/model": model_command,
        "/start_heartbeat": start_heartbeat_command,
        "/stop_heartbeat": stop_heartbeat_command,
        "/heartbeat": heartbeat_status_command,
    }
    first_word = user_text.split()[0].lower()
    cmd_base = first_word.split("@")[0]
    if cmd_base in fallback_commands:
        await fallback_commands[cmd_base](update, context)
        return
    
    # --- 併發控制：防止任務覆蓋導致孤兒任務 ---
    existing_task = agent.active_tasks.get(chat_id)
    if existing_task and not existing_task.done():
        await update.message.reply_text("⏳ **已有任務正在執行中**\n請等待完成，或使用 **[F10] 快捷鍵** 中斷當前任務後再試。", parse_mode=constants.ParseMode.MARKDOWN)
        return

    # 建立並追蹤任務
    task = asyncio.create_task(agent.generate_response(user_text, is_file=False))
    agent.active_tasks[chat_id] = task
    
    try:
        reply = await task
        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(chunk)
    except asyncio.CancelledError:
        logger.warning(f"⚠️ 任務被取消 (chat_id: {chat_id})")
    finally:
        if chat_id in agent.active_tasks: del agent.active_tasks[chat_id]

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        chat_id = update.effective_chat.id
        agent.update_chat_id(chat_id)
        file = await update.message.photo[-1].get_file()
        data = await file.download_as_bytearray()
        
        # 併發控制
        existing_task = agent.active_tasks.get(chat_id)
        if existing_task and not existing_task.done():
            await update.message.reply_text("⏳ **已有任務正在執行中**\n請先中斷當前任務。", parse_mode=constants.ParseMode.MARKDOWN)
            return

        task = asyncio.create_task(agent.generate_response(update.message.caption or "描述圖片", is_file=False, media_files=[{'mime_type': 'image/jpeg', 'data': bytes(data)}]))
        agent.active_tasks[chat_id] = task
        try:
            reply = await task
            if reply:
                for chunk in split_message(reply):
                    await update.message.reply_text(chunk)
        except asyncio.CancelledError: pass
        finally:
            if chat_id in agent.active_tasks: del agent.active_tasks[chat_id]

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        chat_id = update.effective_chat.id
        agent.update_chat_id(chat_id)
        file = await update.message.voice.get_file()
        data = await file.download_as_bytearray()
        
        # 併發控制
        existing_task = agent.active_tasks.get(chat_id)
        if existing_task and not existing_task.done():
            await update.message.reply_text("⏳ **已有任務正在執行中**\n請先中斷當前任務。", parse_mode=constants.ParseMode.MARKDOWN)
            return

        task = asyncio.create_task(agent.generate_response("處理語音", is_file=False, media_files=[{'mime_type': 'audio/ogg', 'data': bytes(data)}]))
        agent.active_tasks[chat_id] = task
        try:
            reply = await task
            if reply:
                for chunk in split_message(reply):
                    await update.message.reply_text(chunk)
        except asyncio.CancelledError: pass
        finally:
            if chat_id in agent.active_tasks: del agent.active_tasks[chat_id]

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent:
        chat_id = update.effective_chat.id
        agent.update_chat_id(chat_id)
        file = await context.bot.get_file(update.message.document.file_id)
        data = await file.download_as_bytearray()
        
        # 併發控制
        existing_task = agent.active_tasks.get(chat_id)
        if existing_task and not existing_task.done():
            await update.message.reply_text("⏳ **已有任務正在執行中**\n請先中斷當前任務。", parse_mode=constants.ParseMode.MARKDOWN)
            return

        task = asyncio.create_task(agent.generate_response(f"分析檔案:\n{data.decode('utf-8', errors='ignore')}", is_file=True))
        agent.active_tasks[chat_id] = task
        try:
            reply = await task
            if reply:
                for chunk in split_message(reply):
                    await update.message.reply_text(chunk)
        except asyncio.CancelledError: pass
        finally:
            if chat_id in agent.active_tasks: del agent.active_tasks[chat_id]

async def manual_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data.get("agent")
    if agent: 
        agent.update_chat_id(update.effective_chat.id)
        agent.memory.save_all_force(); await update.message.reply_text("💾 記憶已儲存。")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("🚨 異常:", exc_info=context.error)
