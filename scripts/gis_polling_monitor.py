"""
GIS 即時監控輪詢腳本 v1.0
取代舊 Alice 的 gis_file_watcher_skill.py (watchdog 模式)
改為輪詢 sensor_config.json，每 1-2 分鐘執行一次

完整流程：
1. 讀取 sensor_config.json
2. 比對上次已知異常，找出「新出現的異常站點」
3. 對新異常站點：fetch_history → generate_professional_chart → Telegram sendPhoto
4. 輸出摘要（Hermes cron 會讀取此輸出）
"""
import os
import sys
import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime

# === 路徑設定 ===
GIS_DIR = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
CONFIG_PATH = os.path.join(GIS_DIR, "sensor_config.json")
STATE_FILE = os.path.join(GIS_DIR, ".hermes_gis_state.json")
CHART_DIR = os.path.join(GIS_DIR, "監測圖表")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALICE_DIR = os.path.join(SCRIPT_DIR, "..", "..")
sys.path.insert(0, ALICE_DIR)

# === Telegram 設定 ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_OWNER_ID", "8138000028")

# === 載入 gis_utils ===
try:
    import gis_utils_v1 as gis_utils
except ImportError:
    try:
        import gis_utils
    except ImportError:
        print("❌ 找不到 gis_utils 模組")
        sys.exit(1)


def load_state():
    """載入上次已知的異常狀態"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_pending": [], "last_check": None}


def save_state(state):
    """儲存當前狀態"""
    state["last_check"] = datetime.now().isoformat()
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def send_telegram_photo(photo_path, caption):
    """透過 Telegram Bot API 直接發送圖片"""
    if not TELEGRAM_TOKEN:
        print("❌ 未設定 TELEGRAM_BOT_TOKEN")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            resp = requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML"
            }, files={"photo": f}, timeout=30)
        if resp.status_code == 200:
            print(f"✅ 已發送圖片到 Telegram: {photo_path}")
            return True
        else:
            print(f"❌ Telegram 發送失敗: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Telegram 發送異常: {e}")
        return False


def generate_chart(uid):
    """為指定測站生成折線圖"""
    match = re.match(r"(DS\d+_\d+)", uid)
    if not match:
        return None, f"無法辨識測站 ID: {uid}"
    st_id = match.group(1)
    site_id = st_id.split("_")[0]

    data = gis_utils.fetch_history(site_id, st_id)
    if not data or not data.get("times"):
        return None, f"無法獲取 {st_id} 歷史數據"

    output_path, msg = gis_utils.generate_professional_chart(st_id, data, base_dir=CHART_DIR)
    return output_path, msg


def main():
    if not os.path.exists(CONFIG_PATH):
        print("⚠️ sensor_config.json 不存在，GIS 監控可能未啟動")
        return

    # 讀取設定
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    pending_set = config.get("pending_set", [])
    pending_details = config.get("pending_details", {})
    ccd_status = config.get("ccd_status", {})

    # 載入上次狀態
    state = load_state()
    known = set(state.get("known_pending", []))

    # 找出新異常
    new_pending = [uid for uid in pending_set if uid not in known]

    results = []

    # CCD 斷線檢查（總是報告）
    ccd_offline = [k for k, v in ccd_status.items() if v == "offline"]
    if ccd_offline:
        results.append(f"⚠️ CCD 斷線: {', '.join(ccd_offline)}")

    if not new_pending:
        # 無新異常
        if pending_set:
            print(f"✅ GIS 監控正常 | 現有 {len(pending_set)} 個已知異常 | 無新增")
        else:
            print("✅ GIS 監控正常 | 無異常")
        save_state({"known_pending": list(pending_set), "last_check": datetime.now().isoformat()})
        return

    # 處理新異常
    print(f"🚨 偵測到 {len(new_pending)} 個新異常站點！")
    for uid in new_pending:
        level = pending_details.get(uid, "alert")
        if level in ("alert", "freeze"):
            emoji, level_text, detail = "🔴", "警戒", "數值已超過警戒管理基準值！"
        elif level == "attention":
            emoji, level_text, detail = "🟡", "注意", "數值已超過注意管理基準值"
        else:
            emoji, level_text, detail = "🚨", "異常", "偵測到數值異常"

        print(f"  {emoji} {uid} ({level_text}): 生成圖表...")
        chart_path, chart_msg = generate_chart(uid)

        if chart_path:
            caption = f"{emoji} <b>GIS {level_text}警報</b>\n測站: <code>{uid}</code>\n{detail}\n\n📊 24h 全維度趨勢圖已自動生成"
            if send_telegram_photo(chart_path, caption):
                results.append(f"{emoji} {uid}: 圖表已推送")
            else:
                results.append(f"{emoji} {uid}: 圖表生成成功但推送失敗")
        else:
            results.append(f"{emoji} {uid}: 圖表生成失敗 - {chart_msg}")

    # 更新狀態
    state["known_pending"] = list(pending_set)
    save_state(state)

    # 輸出摘要
    print("\n".join(results))


if __name__ == "__main__":
    main()
