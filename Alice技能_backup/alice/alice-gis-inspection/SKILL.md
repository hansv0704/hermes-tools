---
name: alice-gis-inspection
description: "⚠️ 已棄用 — GIS 巡檢回報表單自動填寫（pyautogui 座標模式）。改用 alice-l2-inspection（Playwright DOM 精準操控）。"
version: 1.1.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, gis, automation, taiwan, deprecated]
    source: "移植自 Alice Bot gis_inspection_reply_skill.py v4.0 — 已由 alice-l2-inspection 取代"
---

# ⚠️ 已棄用 — 請改用 alice-l2-inspection

此技能使用 pyautogui 座標點擊，可靠度低（60%），已被 Playwright DOM 操控方案取代。

**請使用 `alice-l2-inspection` 技能**，100% 準確率，DOM 層級定位。

## 何時仍可用

- 緊急備用：當 Playwright 無法啟動時
- 非 L2 系統的桌面表單自動化

## 舊指令（保留參考）

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

## 棄用原因

- pyautogui 座標點擊受視窗焦點影響，Hermes 終端機搶焦點導致點擊失敗
- Tab+Space 鍵盤導航無法精準定位
- 無 DOM 層級驗證能力
- 已由 Playwright + Gemini 驗證方案完全取代
