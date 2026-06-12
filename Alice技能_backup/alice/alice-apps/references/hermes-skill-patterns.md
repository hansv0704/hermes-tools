# Hermes 技能撰寫實戰筆記

從 Alice 遷移專案中學到的關鍵模式。

## 模式 1：強制執行規則

**問題**：技能只描述如何做，Agent 不會真的執行 terminal 命令，只回文字。

**解法**：每個需要實際執行的 skill，必須在第一段加入：

```markdown
## ⚠️ 強制規則：主人要求 XX 時，你必須實際執行 terminal 命令。禁止只回文字說明而不執行。
```

**案例**：alice-gis-monitor 原本只描述繪圖流程，TG 上問「給我看折線圖」只回文字。加入強制規則後才真的執行 terminal 繪圖。

## 模式 2：Quick Commands 應用程式啟動器

**問題**：獨立 APP 需要從 CLI/TG 快速啟動。

**解法**：使用 `hermes config set quick_commands`：

```bash
hermes config set quick_commands.<name>.type exec
hermes config set quick_commands.<name>.command '<shell command>'
```

這會在 CLI 和 TG 建立 `/name` 指令。例如：
- `/studio` → 啟動 LiveCode Studio (port 5001)
- `/invest` → 啟動投資儀表板 (port 5002)
- `/game` → 啟動 GameStudio (port 5003)
- `/n8n` → 啟動 N8N (port 5678)

## 模式 3：Cron 排程與 Profile 隔離

**問題**：Cron jobs 需要正確設定 profile，否則 gateway 不會執行。

**正確用法**：
```bash
hermes -p <profile> cron create "<schedule>" "<prompt>" --name "<name>" --skill <skill> --profile <profile>
```

**注意**：`cronjob` 工具的 `profile` 參數行為與 CLI `--profile` 不同。建議統一使用 CLI 建立 cron。

## 模式 4：Secret 遮蔽處理

**問題**：`TELEGRAM_BOT_TOKEN=***` 等敏感字串在 write_file/patch 時會被遮蔽，導致語法錯誤。

**解法**：
- 腳本中用 `os.getenv("TELEGRAM_BOT_TOKEN")` 讀取，不寫死 token
- 若必須從檔案讀取，用字串拼接避開遮蔽：`"TELEGRAM" + "_BOT_TOKEN"`
- 或讀取 Hermes .env（`%LOCALAPPDATA%\hermes\.env`）

## 模式 5：Watchdog vs Cron Polling

**問題**：原始設計是事件驅動（watchdog），不該改成定時輪詢（cron）。

**解法**：
- 保留原始事件驅動邏輯
- 寫成獨立 watchdog 腳本
- 透過 `terminal(background=true)` 啟動為背景程序
- 不要用 cron 取代 watchdog，除非原始就是排程設計

## 模式 6：APP .env 整合

**問題**：舊 APP 讀取自己的 .env，與 Hermes 的 .env 不同步。

**解法**：在 APP 頂部加入：
```python
from dotenv import load_dotenv
import os
_hermes_env = os.path.join(os.getenv("HERMES_HOME", 
    os.path.expandvars(r"%LOCALAPPDATA%\hermes")), ".env")
if os.path.exists(_hermes_env):
    load_dotenv(_hermes_env, override=False)
load_dotenv(override=True)  # 本地 .env 覆蓋
```

這樣 APP 同時讀 Hermes 和本地 .env，向後相容。
