import os
import sys

import time
import subprocess
import logging
import platform
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.request import HTTPXRequest
from config import logger
from agent import PersonalAgent
from handlers import (
    start, help_command, manual_save, handle_message, handle_document, 
    handle_photo, handle_voice, voice_command, lock_command, 
    unlock_command, perform_scheduled_task, error_handler, cleanup_memory_command,
    restart_command, gis_check_command, gis_status_command,
    notify_on_command, notify_off_command, monitor_on_command, monitor_off_command, 
    chat_on_command, chat_off_command, handle_callback_query,
    backup_command, restore_list_command, restore_command, model_command,
    start_heartbeat_command, stop_heartbeat_command, heartbeat_status_command
)
from ui_server import run_server_in_background

RESTART_EXIT_CODE = 42
global_agent = None

def on_windows_close(sig):
    if sig == 2: 
        if global_agent and hasattr(global_agent, 'memory'):
            global_agent.memory.save_all_force()
        return True
    return False

def run_worker():
    global global_agent
    if platform.system() == "Windows":
        try:
            import win32api
            win32api.SetConsoleCtrlHandler(on_windows_close, True)
        except: pass

    try:
        agent = PersonalAgent()
        global_agent = agent
    except Exception as e:
        logger.critical(f"Agent Init Failed: {e}")
        return

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0, write_timeout=60.0, pool_timeout=60.0, connection_pool_size=10)
    builder = ApplicationBuilder().token(tg_token).request(request)
    if os.getenv("TG_PROXY"): builder = builder.proxy_url(os.getenv("TG_PROXY"))
    app = builder.build()
    
    if app.job_queue:
        agent.set_telegram_context(app.job_queue, perform_scheduled_task)

    app.bot_data["agent"] = agent
    app.add_error_handler(error_handler)

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("help", help_command)) 
    app.add_handler(CommandHandler("save", manual_save))
    app.add_handler(CommandHandler("cleanup", cleanup_memory_command))
    app.add_handler(CommandHandler("lock", lock_command))
    app.add_handler(CommandHandler("unlock", unlock_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("gis_check", gis_check_command))
    app.add_handler(CommandHandler("gis_status", gis_status_command))
    app.add_handler(CommandHandler("notify_on", notify_on_command))
    app.add_handler(CommandHandler("notify_off", notify_off_command))
    app.add_handler(CommandHandler("monitor_on", monitor_on_command))
    app.add_handler(CommandHandler("monitor_off", monitor_off_command))
    app.add_handler(CommandHandler("chat_on", chat_on_command))
    app.add_handler(CommandHandler("chat_off", chat_off_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("restore_list", restore_list_command))
    app.add_handler(CommandHandler("restore", restore_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("start_heartbeat", start_heartbeat_command))
    app.add_handler(CommandHandler("stop_heartbeat", stop_heartbeat_command))
    app.add_handler(CommandHandler("heartbeat", heartbeat_status_command))
    
    # Callback Query Handler (用於處理按鈕點擊)
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    run_server_in_background()
    app.run_polling()

def run_runner():
    script_file = sys.argv[0]
    while True:
        p = subprocess.Popen([sys.executable, script_file], env=os.environ.copy())
        p.wait()
        if p.returncode == RESTART_EXIT_CODE: continue
        if p.returncode != 0: time.sleep(3)
        else: sys.exit(0)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if os.environ.get("MAIBOT_WORKER") == "1": run_worker()
    else:
        os.environ["MAIBOT_WORKER"] = "1"
        run_runner()
