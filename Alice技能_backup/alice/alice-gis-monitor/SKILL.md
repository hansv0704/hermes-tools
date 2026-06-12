---
name: alice-gis-monitor
description: "GIS 監控系統 — watchdog 事件驅動即時監控、儀器三層級警報自動繪圖推播（🧊數據凍結/🔴達警戒/🟡達注意）、CCD 影像斷線純文字推播、手動測站圖表查詢。"
version: 2.4.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, gis, monitoring, sensor, alert, chart, watchdog]
    source: "移植自 Alice Bot GIS 監控子系統"
---

# GIS 監控系統

## ⚠️ 強制規則

- 主人要求查看折線圖時，**必須實際執行 terminal 命令繪圖**，禁止只回文字
- 儀器警報推播使用三層級格式（見下方）
- CCD 斷線使用純文字 TG 推播（無圖，因無儀器數據可繪）
- 監控記錄_*.txt 為人工查閱用，**不觸發 watchdog**
- watchdog 重啟後必須執行初始掃描捕捉遺漏異常

## Watchdog 背景程序

`scripts/gis_watchdog.py` v2.4+ 為獨立背景程序，事件驅動：

1. watchdog **只監聽 `sensor_config.json`**（唯一警報來源）
2. `sensor_config.json` 變動 → 雙軌掃描：
   - **儀器異常**：讀 `pending_set` + `pending_details` → 比對 `known_pending` → 繪圖 + TG 推播
   - **CCD 斷線**：讀 `ccd_status` → 比對 `known_ccd_offline` → TG 純文字推播（含恢復通知）
3. `監控記錄_*.txt` 為人工查閱用，不觸發 watchdog

核心函式（可獨立呼叫）：
- `process_anomaly(uid, level)` — 繪圖 + TG 推播單一儀器異常
- `scan_sensor_anomalies(config)` — 掃描 pending_set，只推新異常
- `scan_ccd_status(config)` — 掃描 ccd_status，偵測斷線/恢復
- `scan_and_alert(config=None)` — 統一入口，儀器 + CCD 雙軌掃描
- `send_message(text)` — 純文字 TG 推播（CCD 用）
- `send_photo(path, caption)` — 圖片 TG 推播（儀器用）

### Token 讀取注意

watchdog 從 `.env` 讀取 TELEGRAM_BOT_TOKEN 時，**必須跳過值太短的行**（如之前留下的 `***` 佔位符）。正確實作：

```python
for line in open(env_path):
    if 'BOT_TOKEN' in line and not line.strip().startswith('#'):
        val = line.split('=', 1)[1].strip().strip('"').strip("'")
        if len(val) > 20:  # 真正的 token 至少 46 字元
            token = val
            break
```

## 警報層級格式

| 層級 | TG 標題 | 說明 |
|:--|:--|:--|
| freeze | 🧊 ⚠️ 數據凍結 | 監測數據已凍結，請確認儀器狀態 |
| alert | 🔴 🚨 達警戒 | 數值已超過警戒管理基準值 |
| attention | 🟡 ⚡ 達注意 | 數值已超過注意管理基準值 |

TG caption 格式：
```
{emoji} <b>{層級標題}</b>
📍 測站：<code>{uid}</code>
📋 {詳細說明}
📊 24h 全維度趨勢圖已自動生成
```

## CCD 影像監測

CCD 斷線不經 pending_set，而是 monitor.py 寫入 `ccd_status` 欄位。Watchdog 同步監聽此欄位變化。

### CCD TG 訊息格式

**斷線時：**
```
📷 <b>⚠️ CCD 影像斷線</b>
📍 測站：<code>{site_id}</code> {站名}
📋 監測影像已超過 30 分鐘未更新，請確認攝影機狀態
```

**恢復時：**
```
📷 <b>✅ CCD 影像恢復</b>
📍 測站：<code>{site_id}</code> {站名}
📋 影像已恢復正常更新
```

CCD 使用純文字 `sendMessage`（非 sendPhoto），因為沒有儀器數據可繪圖。防重複機制與儀器異常相同，透過 `known_ccd_offline` 狀態追蹤。

### CCD 測站對照

| 站點代碼 | 站名 |
|:--|:--|
| DS144 | 新庄 |
| DS145 | 藤枝林道 |
| DS009 | 來義 |
| DS002 | 萬山 |
| DS011 | 寶山 |

## 手動繪圖命令

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python -c "
import sys, json
sys.path.insert(0, 'skills/work')
from gis_expert_monitor_skill import GisExpertMonitorSkill
skill = GisExpertMonitorSkill()
result = skill.execute('get_gis_chart', {'uid': 'DS144_02'}, {})
print(json.dumps(result, ensure_ascii=False))
"
```

## 啟動 Watchdog

Watchdog 是**獨立背景程序**，不隨 Hermes 自動啟動。**如果 watchdog 沒在跑，TG 完全不會收到任何警報。** 啟動命令：

```bash
cd "C:\Users\hans\AppData\Local\hermes\profiles\alice\skills\alice\alice-gis-monitor\scripts" && python gis_watchdog.py
```

使用 `terminal(background=true)` 啟動為守護程序。啟動後會自動掃描遺漏異常並推播。

### 健康檢查

```bash
# 檢查 watchdog 是否在運行
ps aux | grep gis_watchdog

# 檢查 watchdog state（最後更新時間）
cat "C:\Users\hans\Desktop\大崩儀器DATA回傳\.watchdog_state.json"
```

若 `known_pending` 與 `sensor_config.json` 的 `pending_set` 不一致，代表 watchdog 已停止運作。

## ⚠️ 已知陷阱

### 1. Watchdog 未運行 = TG 無聲無息失敗

Watchdog 是事件驅動，不會主動回報自己的狀態。如果它 crash 或被誤殺，所有後續異常都會被忽略，使用者不會收到任何通知。**每次系統重啟後需手動啟動 watchdog。**

### 2. Hermes secret redaction 破壞 write_file 寫入的程式碼

使用 `write_file` 寫入含 token 讀取的 Python 程式碼時，Hermes 的 secret redaction 可能將程式碼中的引號配對錯亂，把 token 值處的 `***` 注入到程式碼中，破壞語法。**每次用 write_file/patch 修改 watchdog 後，必須立刻用 `read_file` 確認 token 讀取行完整正確**，再啟動 watchdog。

發生過的實例：原本正確的字串拼接 `"TELEGRAM" + "_BOT_TOKEN="` 被 redaction 干擾後變成語法錯誤的 `startswith("TELEGRAM" + "_BOT_TOKEN=*** _token = ...)`。

### 3. Numpy venv 崩潰導致 matplotlib 無法匯入

Hermes 的 venv 可能因 numpy 升級導致 ABI 不相容：

```
AttributeError: module 'numpy._globals' has no attribute '_signature_descriptor'
```

這會讓 matplotlib 完全無法匯入，watchdog 繪圖失敗。修復：`pip install --force-reinstall numpy`。詳見 `references/numpy-venv-pitfall.md`。

## 故障排除：TG 沒收到警報

當主人說「有異常但 TG 沒收到」時，**依序檢查**：

| 步驟 | 檢查項目 | 命令 |
|:--|:--|:--|
| 1 | Watchdog 是否在跑？ | `process(action='list')` 找 `gis_watchdog` |
| 2 | pending_set 有東西嗎？ | 讀 `sensor_config.json` 的 `pending_set` |
| 3 | ccd_status 有 offline 嗎？ | 讀 `sensor_config.json` 的 `ccd_status` |
| 4 | known_pending 是否落後？ | 比對 `.watchdog_state.json` 和 `pending_set` |
| 5 | known_ccd_offline 是否落後？ | 比對 `.watchdog_state.json` 和 `ccd_status` |
| 6 | 腳本語法完整嗎？ | `read_file` 檢查 token 讀取行（可能被 Hermes redaction 破壞） |
| 7 | numpy 正常嗎？ | `python -c "import matplotlib"` |

### 最常見的故障模式

**A. Watchdog 根本沒在跑** → TG 完全無聲。重啟即可，啟動掃描會補推遺漏異常。

**B. Token 行被寫壞** → 語法錯誤，程式根本無法啟動。Hermes 的 secret redaction 在 write_file 時可能破壞含 `TELEGRAM_BOT_TOKEN` 字串的程式碼，**每次寫完必須用 read_file 確認**。

**C. Numpy ABI 崩潰** → `pip install --force-reinstall numpy`，詳見 `references/numpy-venv-pitfall.md`。

### 手動補推遺漏警報

如果 watchdog 掛掉期間有異常漏推，直接透過 Hermes 的 `send_message` 補發：

```
send_message(target="telegram", message="🧊 <b>⚠️ 數據凍結</b>\n📍 測站：<code>DS002_04_TM</code>\n📋 ...\nMEDIA:<chart_path>")
```

## 相關檔案

- Watchdog：`scripts/gis_watchdog.py`（v2.4，只監聽 sensor_config.json + 啟動掃描 + 儀器三層級 + CCD 斷線推播）
- 繪圖引擎：`gis_utils_v1.py`
- 專家分析：`skills/work/gis_expert_monitor_skill.py`
- GIS 專案：`C:\\Users\\hans\\Desktop\\大崩儀器DATA回傳`
- Numpy venv 陷阱：`references/numpy-venv-pitfall.md`
- Watchdog 架構：`references/watchdog-architecture.md`
