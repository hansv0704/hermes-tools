import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import matplotlib

# 強制使用 Agg 後端
matplotlib.use('Agg')

def fetch_history(site_id, st_id):
    """
    從遠端伺服器抓取測站 24 小時內的歷史數據。
    """
    history = {"times": [], "gps_e": [], "gps_n": [], "tm_v1": [], "tm_v2": [], "gw": []}
    now = datetime.now()
    for day_offset in [1, 0]:
        target_day = now - timedelta(days=day_offset)
        dir_url = f"http://140.116.249.143/dsmon/amhist/{target_day.strftime('%Y')}/{target_day.strftime('%m%d')}/"
        try:
            res = requests.get(dir_url, timeout=5)
            if res.status_code != 200: continue
            files = sorted(list(set(re.findall(r'(\d{4}_10min_a_ds_data\.xml)', res.text))))
            for f_name in files:
                try:
                    f_dt = target_day.replace(hour=int(f_name[:2]), minute=int(f_name[2:4]), second=0, microsecond=0)
                    if now - timedelta(hours=24) <= f_dt <= now:
                        xml_res = requests.get(f"{dir_url}{f_name}", timeout=3)
                        if xml_res.status_code == 200:
                            root = ET.fromstring(xml_res.content.decode('utf-8', errors='ignore'))
                            station = root.find(f".//site_data[@siteid='{site_id}']/station[@stationId='{st_id}']")
                            if station is not None:
                                def get_val(tag):
                                    node = station.find(f".//sensor[@sensor_type='{tag}']")
                                    if node is not None and node.text:
                                        vals = node.text.strip().split()
                                        if vals and vals[0] != "-":
                                            return [float(v) for v in vals]
                                    return [None, None]
                                gps = get_val("GPSForecast3db")
                                tm = get_val("BiTiltMeter")
                                gw = get_val("ObservationWell")
                                history["times"].append(f_dt.strftime("%m/%d %H:%M"))
                                history["gps_e"].append(gps[0]); history["gps_n"].append(gps[1])
                                history["tm_v1"].append(tm[0]); history["tm_v2"].append(tm[1])
                                history["gw"].append(gw[0])
                except: continue
        except: continue
    return history

def generate_professional_chart(st_id, data, base_dir=None):
    if base_dir is None:
        gis_root = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
        base_dir = os.path.join(gis_root, "監測圖表")
    """
    生成趨勢圖並存入外部專案資料夾。
    """
    if not data or not data.get("times"):
        return None, "無數據可供繪圖"

    # 1. 建立目錄結構
    today_str = datetime.now().strftime("%Y%m%d")
    save_dir = Path(base_dir) / today_str
    
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # 若外部路徑失敗，退回到本地備份路徑
        save_dir = Path("photo") / today_str
        save_dir.mkdir(parents=True, exist_ok=True)

    # 2. 檔案命名: YYYYMMDD_HHMMSS_STATION.png
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{timestamp}_{st_id}.png"
    output_path = save_dir / file_name

    # 3. 繪圖邏輯
    times = data["times"]
    fig, (ax_gps, ax_tm, ax_gw) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    tick_s = max(1, len(times) // 12)
    
    def setup_ax(ax, title):
        ax.set_title(title, fontweight='bold', fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=True, useMathText=True))

    setup_ax(ax_gps, "GPS 變位")
    ax_gps.plot(times, data["gps_e"], color='#2e7d32', marker='o', markersize=3, label='E', linewidth=1)
    ax_gps_n = ax_gps.twinx()
    ax_gps_n.plot(times, data["gps_n"], color='#81c784', marker='^', markersize=3, label='N', linewidth=1)
    ax_gps.set_ylabel("E", color='#2e7d32'); ax_gps_n.set_ylabel("N", color='#81c784')

    setup_ax(ax_tm, "TM 傾斜儀")
    ax_tm.plot(times, data["tm_v1"], color='#1565c0', marker='o', markersize=3, label='Val 1', linewidth=1)
    ax_tm_v2 = ax_tm.twinx()
    ax_tm_v2.plot(times, data["tm_v2"], color='#64b5f6', marker='^', markersize=3, label='Val 2', linewidth=1)
    ax_tm.set_ylabel("Val 1", color='#1565c0'); ax_tm_v2.set_ylabel("Val 2", color='#64b5f6')

    setup_ax(ax_gw, "GW 水位計")
    ax_gw.plot(times, data["gw"], color='#d84315', marker='s', markersize=3, label='GW', linewidth=1)
    ax_gw.set_ylabel("水位", color='#d84315')

    plt.xticks(range(0, len(times), tick_s), rotation=45, fontsize=8)
    plt.suptitle(f"📊 專業監測報告: {st_id} (全維度 24h 趨勢)", fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    plt.savefig(str(output_path), dpi=120)
    plt.close()
    return str(output_path), "成功"

if __name__ == "__main__":
    # 測試程式碼
    print("GIS Utils 測試中...")
    test_st = "DS145_03"
    test_site = "DS145"
    data = fetch_history(test_site, test_st)
    path, msg = generate_professional_chart(test_st, data)
    print(f"結果: {msg}, 路徑: {path}")
