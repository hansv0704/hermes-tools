"""
GIS 即時監控 Watchdog v2.0
完整複製原始 gis_file_watcher_skill.py 邏輯：
- watchdog 監聽 sensor_config.json + 監控記錄_*.txt
- 事件驅動（非輪詢）
- 新異常 → 自動繪圖 → Telegram 推播
- 獨立背景程序，不依賴 Hermes agent loop
"""
import os, sys, json, re, time, requests
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

GIS_DIR = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
CONFIG_PATH = os.path.join(GIS_DIR, "sensor_config.json")
STATE_FILE = os.path.join(GIS_DIR, ".watchdog_state.json")
CHART_DIR = os.path.join(GIS_DIR, "監測圖表")
ALICE_DIR = r"C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
sys.path.insert(0, ALICE_DIR)

# 讀取 token（從 .env，避開遮蔽）
_token = ""
for _ep in [r"C:\Users\hans\AppData\Local\hermes\.env",
            r"C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.env"]:
    try:
        for _line in open(_ep, encoding="utf-8"):
            _line = _line.strip()
            if _line.startswith("TELEGRAM" + "_BOT_TOKEN="):
                _token = _line.split("=", 1)[1].strip().strip("\"'")
                break
        if _token: break
    except: pass
TELEGRAM_TOKEN = _token
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_OWNER_ID", "8138000028")

try:
    import gis_utils_v1 as gis_utils
except ImportError:
    import gis_utils

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE, encoding="utf-8"))
    return {"known_pending": []}

def save_state(pending_list):
    json.dump({"known_pending": pending_list, "last": datetime.now().isoformat()},
              open(STATE_FILE, "w", encoding="utf-8"))

def generate_chart(uid):
    m = re.match(r"(DS\d+_\d+)", uid)
    if not m: return None, f"bad uid: {uid}"
    st_id = m.group(1)
    site_id = st_id.split("_")[0]
    data = gis_utils.fetch_history(site_id, st_id)
    if not data or not data.get("times"):
        return None, f"no data for {st_id}"
    return gis_utils.generate_professional_chart(st_id, data, base_dir=CHART_DIR)

def send_photo(path, caption):
    if not TELEGRAM_TOKEN or not os.path.exists(path):
        print(f"  send failed: token={bool(TELEGRAM_TOKEN)} file={os.path.exists(path)}")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": open(path, "rb")}, timeout=30)
        if r.status_code == 200:
            print(f"  PUSHED: {path}")
            return True
        print(f"  TG error: {r.status_code}")
    except Exception as e:
        print(f"  TG exception: {e}")
    return False

class GisHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_triggered = {}

    def on_modified(self, event):
        if event.is_directory: return
        path = event.src_path
        fname = os.path.basename(path)
        if not ("sensor_config.json" in fname or
                (fname.startswith("監控記錄_") and fname.endswith(".txt"))):
            return
        now = time.time()
        if now - self.last_triggered.get(path, 0) < 3.0:
            return
        self.last_triggered[path] = now
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            config = json.load(open(CONFIG_PATH, encoding="utf-8"))
        except Exception as e:
            print(f"config read error: {e}")
            return
        pending_set = config.get("pending_set", [])
        pending_details = config.get("pending_details", {})
        if not pending_set:
            save_state([])
            return
        state = load_state()
        known = set(state.get("known_pending", []))
        new_items = [uid for uid in pending_set if uid not in known]
        if not new_items:
            return
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(new_items)} new!", flush=True)
        for uid in new_items:
            level = pending_details.get(uid, "alert")
            if level == "freeze":
                emoji, lt, detail = "🧊", "⚠️ 數據凍結", "監測數據已凍結，請確認儀器狀態"
            elif level == "alert":
                emoji, lt, detail = "🔴", "🚨 達警戒", "數值已超過警戒管理基準值"
            elif level == "attention":
                emoji, lt, detail = "🟡", "⚡ 達注意", "數值已超過注意管理基準值"
            else:
                emoji, lt, detail = "🚨", "⚠️ 異常", "偵測到數值異常"
            print(f"  {emoji} {uid} ({lt}): chart...")
            chart_path, msg = generate_chart(uid)
            if chart_path:
                caption = f"{emoji} <b>{lt}</b>\n📍 測站：<code>{uid}</code>\n📋 {detail}\n\n📊 24h 全維度趨勢圖已自動生成"
                send_photo(chart_path, caption)
            else:
                print(f"  chart fail: {msg}")
        save_state(list(pending_set))

if __name__ == "__main__":
    print(f"GIS Watchdog v2.0 starting: {GIS_DIR}", flush=True)
    print(f"Token: {'OK' if TELEGRAM_TOKEN else 'MISSING'}", flush=True)
    # 啟動時也檢查一次現有 pending（處理重啟前累積的告警）
    if os.path.exists(CONFIG_PATH):
        try:
            config = json.load(open(CONFIG_PATH, encoding="utf-8"))
            pending = config.get("pending_set", [])
            if pending:
                print(f"Startup: found {len(pending)} existing pending, processing...", flush=True)
                handler = GisHandler()
                handler.last_triggered = {}
                handler.on_modified(type('FakeEvent', (), {'is_directory': False, 'src_path': CONFIG_PATH})())
        except Exception as e:
            print(f"Startup check error: {e}", flush=True)
    observer = Observer()
    observer.schedule(GisHandler(), GIS_DIR, recursive=False)
    observer.start()
    print("Watching (event-driven)...", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print("Stopped", flush=True)
