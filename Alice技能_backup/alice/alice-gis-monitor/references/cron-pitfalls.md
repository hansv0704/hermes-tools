# Hermes Cron Job 常見陷阱與解決方案

> 記錄 GIS 監控 cron 從搭建到穩定運行的所有踩坑經驗。

## 1. Script 路徑 — profile 隔離

| 情境 | 正確路徑 |
|:--|:--|
| CLI `hermes cron create --script X` | `~/.hermes/scripts/X` |
| Gateway alice profile 執行 | `~/.hermes/profiles/alice/scripts/X` |
| cronjob tool `profile=alice` | 同上，alice profile |

**教訓**：script 要同時放在兩個位置，確保 CLI 建立和 gateway 執行都能找到。

## 2. Delivery 目標

CLI `hermes cron create` 預設 `deliver=local`（不發送）。
建立後必須用 `cronjob action=update deliver=origin` 改成送到 Telegram。

## 3. Token / Secret 在 no_agent 腳本中

Hermes 的 secret redaction 會把 `os.getenv("TELEGRAM_BOT_TOKEN")` 回傳的空字串也遮蔽為 `***`，寫入檔案時破壞 Python 語法。

**不可行的做法**：
- 在腳本中 `os.getenv("TOKEN")` → cron 環境無此變數
- 從 `.env` 讀取 → redaction 在寫入時破壞字串

**可行方案**：
- 改用 LLM 模式（`no_agent=false`），讓 agent 讀自己的 `.env` 發送
- 或用 `--script` 做 data-collection pre-hook，LLM 處理推送

## 4. CLI vs cronjob tool

| 方式 | 語法 | 注意 |
|:--|:--|:--|
| `hermes cron create` | `"schedule" "prompt" --name X --skill Y --profile Z` | prompt 是 positional arg，注意引號 |
| `cronjob` tool | `action=create schedule=... prompt=...` | 支援更多參數但 profile 支援不穩定 |

**推薦**：用 `hermes -p alice cron create` CLI 建立，再用 `cronjob update` 補 delivery。

## 5. 環境依賴檢查

腳本失敗 (exit code 1) 常見原因：
- `matplotlib` 未安裝 → `pip install matplotlib`
- `requests` 未安裝 → `pip install requests`
- Python 模組找不到 → 確認 `sys.path.insert` 指向正確目錄

## 6. Script 輸出格式協定

GIS 輪詢腳本使用 pipe-delimited 輸出讓 LLM 解析：

```
GIS_OK|{known_count} known, {new_count} new    ← 正常
CHART|{uid}|{level_text}|{file_path}           ← 新異常，需推送圖表
GIS_ERR|{uid}|{error_msg}                      ← 錯誤
```

LLM prompt 應明確指示如何處理每種輸出格式。
