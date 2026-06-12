"""
GIS Watchdog 模板 — 事件驅動檔案監控
獨立背景程序，不依賴 Hermes agent loop

使用方式：
  python gis_watchdog.py   # 啟動監控（背景執行）
"""
import os, sys, json, re, time, requests
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === 設定 ===
WATCH_DIR = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
CONFIG_FILE = os.path.join(WATCH_DIR, "sensor_config.json")
STATE_FILE = os.path.join(WATCH_DIR, ".watchdog_state.json")

# === Token（從 .env 讀取，避免硬編碼） ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_OWNER_ID", "8138000028")
if not TOKEN:
    for ep in [r"C:\Users\hans\AppData\Local\hermes\.env"]:
        try:
            for line in open(ep, encoding="utf-8"):
                if line.startswith("TELEGRAM_BOT_TOKEN=***                    TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            if TOKEN: break
        except: pass

# === Handler ===
class WatchHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_triggered = {}

    def on_modified(self, event):
        if event.is_directory: return
        now = time.time()
        if now - self.last_triggered.get(event.src_path, 0) < 3.0:  # 冷卻
            return
        self.last_triggered[event.src_path] = now
        # 在此加入你的處理邏輯
        print(f"[{datetime.now():%H:%M:%S}] 偵測到變更: {event.src_path}")

# === 啟動 ===
if __name__ == "__main__":
    observer = Observer()
    observer.schedule(WatchHandler(), WATCH_DIR, recursive=False)
    observer.start()
    print(f"Watchdog started: {WATCH_DIR}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
