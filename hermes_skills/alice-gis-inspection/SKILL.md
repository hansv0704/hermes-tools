---
name: alice-gis-inspection
description: "GIS 巡檢回報表單自動填寫 — 使用 pyautogui 自動勾選 GIS 監測系統的巡檢回報表單。支援三種模式：vision（座標點擊）、keyboard（Tab+Space）、CDP（Playwright DOM）。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, gis, automation, taiwan]
    source: "移植自 Alice Bot gis_inspection_reply_skill.py v4.0"
---

# GIS 巡檢回報表單自動填寫

## ⚠️ 強制規則：主人要求填寫巡檢表單時，你必須實際執行 terminal 命令來操控表單。禁止只回文字說明而不執行。

當主人需要填寫 GIS 監測系統的「巡檢回報表單」時使用此技能。

## 背景

主人的 GIS 監測系統有一個巡檢回報網頁表單，需要定期勾選三個 radio button：
1. **1.正常**（監測值連續趨勢）
2. **2.無**（監測值瞬時異常跳動）
3. **儀器設備正常，現地監測值達注意：加強守視**

## 觸發條件

- 主人明確要求填寫 GIS 巡檢回報表單
- GIS 監控 cron job 觸發異常需要回報
- 主人說「填巡檢表」「GIS 回報」「巡檢回報」等關鍵詞

## 執行方式

此技能調用 Alice 專案中的 Python 腳本。所有程式碼位於：
```
C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\skills\gis_inspection_reply_skill.py
```

### 方法 1：Vision 模式（推薦 — 最精準）

需要主人提供三個 radio button 的螢幕座標（0-1000 比例座標）。步驟：
1. 先請主人截圖並標記三個 radio 的座標位置
2. 或使用瀏覽器工具打開表單頁面，vision 分析定位
3. 執行 Python 腳本

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from gis_inspection_reply_skill import GisInspectionReplySkill
skill = GisInspectionReplySkill()
result = skill.execute('gis_fill_inspection_form', {
    'mode': 'vision',
    'click_create': False,
    'radio_coords': [[x1,y1], [x2,y2], [x3,y3]]
}, {})
print(result)
"
```

### 方法 2：Keyboard 模式（備用 — 無需座標）

當無法取得精確座標時使用 Tab+Space 鍵盤導航。**使用前請確保表單視窗在前景**。

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from gis_inspection_reply_skill import GisInspectionReplySkill
skill = GisInspectionReplySkill()
result = skill.execute('gis_fill_inspection_form', {
    'mode': 'keyboard',
    'click_create': False
}, {})
print(result)
"
```

### 方法 3：CDP 模式（如果 Chrome debug port 9222 開啟）

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from gis_inspection_reply_skill import GisInspectionReplySkill
skill = GisInspectionReplySkill()
result = skill.execute('gis_fill_inspection_form', {
    'mode': 'cdp',
    'click_create': False
}, {})
print(result)
"
```

## 參數說明

| 參數 | 類型 | 說明 |
|:--|:--|:--|
| `mode` | str | `vision`（推薦）、`keyboard`、`cdp` |
| `click_create` | bool | 是否勾選完後點擊「建立」送出。預設 False |
| `radio_coords` | list | vision 模式必要。三個座標 `[[x1,y1],[x2,y2],[x3,y3]]`，0-1000 比例 |

## 注意事項

- **此工具操控真實滑鼠鍵盤**，執行時不要移動滑鼠
- 執行前確保目標視窗在前景
- vision 模式的座標使用 0-1000 比例（非像素）
- 建議先用 `click_create=False` 測試，確認無誤後再設 True 送出
- 若 keyboard 模式失敗，提示主人改用 vision 模式

## 依賴

- `pyautogui` — 滑鼠鍵盤操控
- `pygetwindow` — 視窗偵測（可選）
- `Pillow` — 截圖驗證（可選）
- `playwright` — CDP 模式（可選）

## 相關檔案

- Alice 原始碼：`skills/gis_inspection_reply_skill.py`
- GIS 監控專案：`C:\Users\hans\Desktop\大崩儀器DATA回傳`
- 經驗紀錄：`memory/skill_experience.json`
