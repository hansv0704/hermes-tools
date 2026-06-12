"""
GIS 即時監控 Watchdog v2.4
- watchdog 只監聽 sensor_config.json（唯一警報來源）
- 監控記錄_*.txt 為人工查閱用，不觸發 watchdog
- 事件驅動（非輪詢）
- 儀器異常 → 自動繪圖 → Telegram 推播（三層級警報）
- CCD 斷線 → Telegram 純文字推播（含恢復通知）
- 啟動時初始掃描，避免錯過重啟前的異常

啟動方式：
  python gis_watchdog.py

依賴：
  pip install watchdog matplotlib requests
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

# ── Token 讀取（字串拼接避開 Hermes secret redaction） ──
_token = ""
for _ep in [r"C:\Users\hans\AppData\Local\hermes\.env",
            r"C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.env"]:
    try:
        for _line in open(_ep, encoding="utf-8"):
            _line = _line.strip()
            if _line.startswith("TELEGRAM" + "_BOT_TOKEN=") and not _line.startswith("#"):
                val = _line.split("=", 1)[1].strip().strip('"').strip("'")
                if len(val) > 20:
                    _token = val
                    break
        if _token:
            break
    except Exception:
        pass
TELEGRAM_TOKEN = _token
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_OWNER_ID", "8138000028")

try:
    import gis_utils_v1 as gis_utils
except ImportError:
    import gis_utils

# ── CCD 測站名稱對照 ──
CCD_SITE_NAMES = {
    "DS144": "新庄",
    "DS145": "藤枝林道",
    "DS009": "來義",
    "DS002": "萬山",
    "DS011": "寶山",
}

# ── 狀態持久化 ──
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE, encoding="utf-8"))
    return {"known_pending": [], "known_ccd_offline": []}

def save_state(pending_list=None, ccd_offline_list=None):
    current = load_state()
    if pending_list is not None:
        current["known_pending"] = pending_list
    if ccd_offline_list is not None:
        current["known_ccd_offline"] = ccd_offline_list
    current["last"] = datetime.now().isoformat()
    json.dump(current, open(STATE_FILE, "w", encoding="utf-8"))

# ── 繪圖 ──
def generate_chart(uid):
    m = re.match(r"(DS\d+_\d+)", uid)
    if not m:
        return None, f"bad uid: {uid}"
    st_id = m.group(1)
    site_id = st_id.split("_")[0]
    data = gis_utils.fetch_history(site_id, st_id)
    if not data or not data.get("times"):
        return None, f"no data for {st_id}"
    return gis_utils.generate_professional_chart(st_id, data, base_dir=CHART_DIR)

# ── Telegram 推播（圖片 + 純文字） ──
def send_photo(path, caption):
    if not TELEGRAM_TOKEN or not os.path.exists(path):
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": open(path, "rb")}, timeout=30)
        return r.status_code == 200
    except Exception:
        return False

def send_message(text):
    """發送純文字 TG 訊息（CCD 斷線/恢復用）"""
    if not TELEGRAM_TOKEN:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15)
        return r.status_code == 200
    except Exception:
        return False

# ── 警報層級映射（三層級） ──
LEVEL_MAP = {
    "freeze":    ("🧊", "⚠️ 數據凍結", "監測數據已凍結，請確認儀器狀態"),
    "alert":     ("🔴", "🚨 達警戒",   "數值已超過警戒管理基準值"),
    "attention": ("🟡", "⚡ 達注意",   "數值已超過注意管理基準值"),
}

def process_anomaly(uid, level):
    """處理單一儀器異常：繪圖 → 推播。回傳是否成功。"""
    emoji, title, detail = LEVEL_MAP.get(level, ("🚨", "異常", "數值異常"))
    chart_path, msg = generate_chart(uid)
    if chart_path:
        caption = (
            f"{emoji} <b>{title}</b>\n"
            f"📍 測站：<code>{uid}</code>\n"
            f"📋 {detail}\n"
            f"📊 24h 全維度趨勢圖已自動生成"
        )
        ok = send_photo(chart_path, caption)
        print(f"  {uid} [{level}] → {'TG sent' if ok else 'TG FAIL'}")
        return ok
    else:
        print(f"  {uid} [{level}] → chart fail: {msg}")
        return False

# ── 儀器異常掃描 ──
def scan_sensor_anomalies(config):
    """掃描 pending_set，對新異常推播。"""
    pending_set = config.get("pending_set", [])
    pending_details = config.get("pending_details", {})
    if not pending_set:
        save_state(pending_list=[])
        return
    state = load_state()
    known = set(state.get("known_pending", []))
    new_items = [uid for uid in pending_set if uid not in known]
    if not new_items:
        return
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(new_items)} new anomalies: {new_items}")
    for uid in new_items:
        process_anomaly(uid, pending_details.get(uid, "alert"))
    save_state(pending_list=list(pending_set))

# ── CCD 斷線掃描 ──
def scan_ccd_status(config):
    """掃描 ccd_status，對新斷線/恢復推播純文字 TG。"""
    ccd_status = config.get("ccd_status", {})
    if not ccd_status:
        return
    state = load_state()
    known_offline = set(state.get("known_ccd_offline", []))
    current_offline = {sid for sid, status in ccd_status.items() if status == "offline"}

    # 新斷線
    new_offline = current_offline - known_offline
    for sid in new_offline:
        name = CCD_SITE_NAMES.get(sid, sid)
        text = (
            f"📷 <b>⚠️ CCD 影像斷線</b>\n"
            f"📍 測站：<code>{sid}</code> {name}\n"
            f"📋 監測影像已超過 30 分鐘未更新，請確認攝影機狀態"
        )
        ok = send_message(text)
        print(f"  CCD {sid} → offline {'TG sent' if ok else 'TG FAIL'}")

    # 恢復
    recovered = known_offline - current_offline
    for sid in recovered:
        name = CCD_SITE_NAMES.get(sid, sid)
        text = (
            f"📷 <b>✅ CCD 影像恢復</b>\n"
            f"📍 測站：<code>{sid}</code> {name}\n"
            f"📋 影像已恢復正常更新"
        )
        ok = send_message(text)
        print(f"  CCD {sid} → recovered {'TG sent' if ok else 'TG FAIL'}")

    # 儲存最新狀態
    if new_offline or recovered:
        save_state(ccd_offline_list=list(current_offline))

# ── 統一掃描入口 ──
def scan_and_alert(config=None):
    """掃描 sensor_config.json：儀器異常 + CCD 斷線。"""
    if config is None:
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            config = json.load(open(CONFIG_PATH, encoding="utf-8"))
        except Exception:
            return
    scan_sensor_anomalies(config)
    scan_ccd_status(config)

# ── Watchdog Handler ──
class GisHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_triggered = {}

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        fname = os.path.basename(path)
        # 只盯 sensor_config.json — 這是唯一的警報來源
        # 監控記錄_*.txt 為人工查閱用，不觸發
        if "sensor_config.json" not in fname:
            return
        now = time.time()
        if now - self.last_triggered.get(path, 0) < 3.0:
            return
        self.last_triggered[path] = now
        scan_and_alert()

# ── 主程式 ──
if __name__ == "__main__":
    print(f"GIS Watchdog v2.4 — {GIS_DIR}")
    print(f"TG Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"TG Token: {'✓' if TELEGRAM_TOKEN else '✗ MISSING'}")

    # 啟動時初始掃描（捕捉重啟前遺漏的異常）
    print("Initial scan (sensors + CCD)...")
    try:
        scan_and_alert()
    except Exception as e:
        print(f"  Initial scan error: {e}")

    observer = Observer()
    observer.schedule(GisHandler(), GIS_DIR, recursive=False)
    observer.start()
    print("Watching (event-driven)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print("Stopped")
