---
name: alice-gis-monitor
description: "GIS 監控系統 — 即時感測器監控、異常偵測、自動繪圖推播折線圖。支援手動查詢指定測站圖表。"
version: 2.1.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, gis, monitoring, sensor, alert, chart]
    source: "移植自 Alice Bot GIS 監控子系統"
---

# GIS 監控系統

當主人要求查看 GIS 測站折線圖時，**你必須實際執行 terminal 命令來繪圖**，不能只描述。

## ⚠️ 強制規則

**當主人說「給我看 XX 的折線圖」「查 XX 測站」「顯示 XX 圖表」等，你必須：**

1. 用 terminal 執行以下命令（替換 UID）：
2. 讀取 terminal 輸出，取得圖檔路徑
3. **實際發送圖片給主人**（不是描述圖片內容）

不允許只回文字描述而不執行 terminal 命令。

## 手動繪圖命令（複製貼上執行）

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python -c "
import sys, json
sys.path.insert(0, 'skills/work')
from gis_expert_monitor_skill import GisExpertMonitorSkill
skill = GisExpertMonitorSkill()
result = skill.execute('get_gis_chart', {'uid': 'UID_PLACEHOLDER'}, {})
print(json.dumps(result, ensure_ascii=False))
"
```

將 `UID_PLACEHOLDER` 替換為主人指定的測站 ID（例如 `DS144_02`、`DS145_03`）。

## terminal 輸出解讀

- 成功：`{"status": "success", "file_path": "C:\\...\\監測圖表\\...png", "message": "..."}`
- 失敗：`{"status": "error", "message": "..."}`

## 發送圖片給主人

取得 `file_path` 後，使用 terminal 發送：

```bash
curl -s -X POST "https://api.telegram.org/bot%TELEGRAM_BOT_TOKEN%/sendPhoto" -F "chat_id=8138000028" -F "photo=@FILE_PATH" -F "caption=DS144_02 24h 趨勢圖"
```

將 `%TELEGRAM_BOT_TOKEN%` 替換為環境變數 `$TELEGRAM_BOT_TOKEN` 的值，`FILE_PATH` 替換為圖檔路徑。

## 注意

- **必須實際執行 terminal 命令**，不能只回文字
- 圖表格式：GPS 變位 / TM 傾斜儀 / GW 水位計 三連圖
- 所有依賴（matplotlib、gis_utils）已安裝

## 相關檔案

- 繪圖引擎：`C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\gis_utils_v1.py`
- 專家分析：`skills/work/gis_expert_monitor_skill.py`
- Watchdog：`scripts/gis_watchdog.py`（背景運行中）
