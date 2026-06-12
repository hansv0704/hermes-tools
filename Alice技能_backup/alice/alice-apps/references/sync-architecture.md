# 多端點同步架構 — 技術細節

> 這是 `alice-apps` 技能的參考文件。記錄跨電腦同步的完整技術架構、程式邏輯和已知坑點。

## 架構總覽

```
電腦A                              電腦B
─────                              ─────
memories/USER.md  ←── cron/30min ──→  memories/USER.md
memories/MEMORY.md ←── auto sync ──→  memories/MEMORY.md
       │                 MEGA              │
       └── push (本地較新)                 │
       ┌── pull (MEGA較新)                 │
       │                                   │
skills/         ←── git pull ──→       skills/
scripts/        ←── git pull ──→       scripts/
```

## sync_memory.py v2 核心邏輯

```python
def auto():
    for each file in [USER.md, MEMORY.md]:
        local_mtime = os.stat(local_file).st_mtime
        mega_mtime  = os.stat(mega_file).st_mtime

        if local_mtime > mega_mtime:  local_newer = True
        if mega_mtime > local_mtime:   mega_newer = True

    if local_newer and not mega_newer:   push()
    elif mega_newer and not local_newer:  pull()
    elif both newer:                      push()  # 衝突時以本地為準
    else:                                 pass    # 完全同步，安靜 skip
```

**關鍵設計決定**：auto 模式在兩邊相同時不輸出任何東西。因為 cron job 的 stdout 會被投遞，安靜 = 主人不會收到無意義的「已同步」通知。

## 雙 Profile 策略

一鍵安裝同時寫入兩個 profile 的 memories/：

```
alice profile:    %LOCALAPPDATA%\hermes\profiles\alice\memories\
default profile:  %LOCALAPPDATA%\hermes\memories\
```

原因：主人若不慎用 `hermes`（無 `-p alice`），default profile 至少有記憶，不會是空的。
但技能只在 alice profile，所以仍應使用 `hermes -p alice`。

## MEGA 目錄偵測

`sync_memory.py` 使用三層 fallback 定位 MEGA 目錄：
1. 讀取環境變數 `MEGA_SYNC_DIR`（一鍵安裝寫入 `.env`）
2. 自動搜尋桌面上的 `大崩儀器DATA回傳` 目錄
3. 預設路徑 `%USERPROFILE%\Desktop\大崩儀器DATA回傳\MEGA備份\hermes_memory`

## 一鍵安裝.bat 7 步驟

| 步驟 | 內容 |
|------|------|
| [1/6] | 檢查 Python / Git / Hermes |
| [2/6] | `pip install -r requirements.txt` |
| [3/6] | `git clone` hermes-tools 到 `Desktop\Hermes工具區` |
| [4/6] | 設定 API Keys + MEGA_SYNC_DIR + Telegram config + quick_commands（動態路徑） |
| [5/6] | 複製 skills + sync_memory.py 到 alice scripts/ |
| [6/6] | 從 MEGA 拉取記憶 → alice profile → default profile |
| [7/7] | `hermes -p alice cron create "every 30m" --script "scripts/sync_memory.py" --no_agent` |

## quick_commands 動態路徑

不使用寫死的絕對路徑，改用 `%%USERPROFILE%%`：

```yaml
quick_commands:
  studio:
    command: "set WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區 && start python \"%%WORKSPACE%%\run_studio.py\""
```

## 已知坑點

### Hermes Secret Redaction 遮蔽驗證

當 batch 檔包含 `%TG_TOKEN%` 或 `%DEEPSEEK_KEY%`，Hermes 會在 **所有輸出層**（read_file、terminal stdout、patch diff）將其遮蔽為 `***`。

**驗證方式**：用 Python 讀取原始位元組：
```bash
python -c "
with open('file.bat', 'rb') as f:
    raw = f.read()
import re
matches = re.finditer(b'%TG_TOKEN%', raw)
print(len(list(matches)))
"
```

### Cron Script 名稱必須一致

cron job 的 `--script` 參數必須與 `profiles/alice/scripts/` 下的實際檔案名稱完全一致。名稱不匹配會導致每 30 分鐘 error，且 cron 的 error 訊息不會主動推送（`--deliver local` 時）。

### Batch Unicode 相容性

- `╔═╗╚╝║` 等雙線框在非中文 Windows 終端亂碼 → 改用 ASCII `+====+`、`|`
- `❌✅⚠️` emoji 在舊 cmd 字型顯示方塊 → 改用 `[X]`、`[OK]`、`[!]`

### 變數替換陷阱

batch 中 `%VAR%` 在 `echo` 時必須寫為變數參照，而非寫死字面值：
- ❌ `echo TELEGRAM_BOT_TOKEN=*** > .env`
- ✅ `echo TELEGRAM_BOT_TOKEN=%TG_TOKEN%>> .env`
