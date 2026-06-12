---
name: alice-l2-inspection
description: "L2 大規模崩塌監測巡檢表自動填寫 — Gemini 自動讀驗證碼登入 + Playwright DOM 精準操控。只填寫「填寫時間為空」的表單，預設不送出。"
version: 2.1.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, l2, gis, inspection, automation, captcha]
---

# L2 巡檢表自動填寫

完整自動化：Gemini 讀驗證碼登入 → 掃描表格判斷未填寫 → Playwright DOM 填寫。

## ⚠️ 強制規則

- 主人說「填 L2 表單」→ 執行 `python scripts/l2_fill.py`（**不含 --dry-run，會送出**）
- 測試/演示時 → 執行 `python scripts/l2_fill.py --dry-run`（只填不送）
- **沒有主人明確指示，絕不送出**

## 完整流程

```
1. Playwright 開瀏覽器 → L2 列表頁
2. 若未登入 → Gemini 自動讀驗證碼 → 填入帳密 → 登入（最多重試 4 次）
3. 掃描表格每一列 → cells[6]（填寫時間）為空 → 收集 ReportID
4. 逐一開表單 → get_by_label 精準勾選正常/無/儀器設備正常
5. 若 submit=True → scrollTo 底部 → 點擊 #btnCheck 送出
```

## 使用方式

```bash
# 填寫全部未填表單並送出（正式交辦）
python scripts/l2_fill.py

# 填寫全部未填但不送出（演示/檢查）
python scripts/l2_fill.py --dry-run

# 只填前 3 筆
python scripts/l2_fill.py 3
```

## 技術細節

| 環節 | 方法 |
|:--|:--|
| 登入 | Gemini-2.5-flash 辨識驗證碼 |
| 偵測未填 | 掃描 `<table>` 的 `cells[6]`（填寫時間欄） |
| 勾選 | `get_by_label("正常")` / `get_by_label("無")` / `get_by_label("儀器設備正常...")` |
| 送出 | `scrollTo` 底部 → `#btnCheck.click()` |
| 跳過已填 | `#btnCheck` 不可見 = 已送出 |

## 排程（災害事件期間）

Cron job `8cf51a05eff7`：`35 5,11,14,17,20,23 * * *`，目前暫停。事件期間用 `hermes cron resume 8cf51a05eff7` 恢復。
