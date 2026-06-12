# .env Token 陷阱

## 問題

`.env` 檔案中可能殘留 `TELEGRAM_BOT_TOKEN=***` 的垃圾行（來自寫入失敗或手動編輯）。

watchdog 的 token 讀取邏輯使用 `startswith("TELEGRAM" + "_BOT_TOKEN=***` 匹配第一行，若垃圾行在前面，會取到 `***`（9 字元），導致 Telegram API 回 404。

## 症狀

- TG 推播失敗：`TG error: 404`
- Token 長度檢查：只有 9 字元（正常應為 46 字元）

## 修復

在 token 讀取邏輯中加入長度檢查：

```python
if len(val) < 20:
    continue  # 跳過垃圾行
```

## 預防

- `.env` 中只保留一行有效的 `TELEGRAM_BOT_TOKEN=xxx`
- 不要在 `.env` 中留下 `***` 佔位符
- cron/no_agent 腳本讀取 `.env` 時務必加長度驗證
