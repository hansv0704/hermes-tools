# os.execvpe Profile Re-exec Crash on Windows

## 問題鏈（2026-06-12 完整記錄）

### 觸發條件
1. Active profile 設為非 default（如 alice）
2. 桌面版啟動時 spawn `hermes -p alice dashboard`
3. Python 偵測到 `get_active_profile_name() != "default"` 
4. 觸發 `os.execvpe` re-exec 成 `-p default --open-profile alice`
5. Windows 上 `os.execvpe` 崩潰（ACCESS VIOLATION）

### 真正的修復（三層）

**層 1：`os.execvpe` → `subprocess.Popen` + `sys.exit(0)`**

檔案：`hermes_cli/main.py` 第 10369-10377 行

```python
if sys.platform == "win32":
    subprocess.Popen(
        [sys.executable] + reexec_argv[1:],
        env=env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
    sys.exit(0)
else:
    os.execvpe(sys.executable, reexec_argv, env)
```

**層 2：`_apply_profile_override` 設定環境變數標記**

檔案：`hermes_cli/main.py` 第 455 行

```python
os.environ["HERMES_PROFILE_FROM_CLI"] = "1"
```

**層 3：re-exec 檢查加上 CLI profile 豁免**

檔案：`hermes_cli/main.py` 第 10331 行

```python
and not os.environ.get("HERMES_PROFILE_FROM_CLI")
```

### 為什麼層 2+3 需要環境變數而不是 `args.profile`

`_apply_profile_override` 找到 `--profile alice` 後會從 `sys.argv` **移除**該參數（第 456-458 行），所以後續 argparse 的 `args.profile` 永遠是空字串。只能用環境變數傳遞此資訊。

### 桌面版 vs CLI profile 系統是獨立的

| 系統 | 設定位置 | 指令 |
|------|---------|------|
| CLI | `~/.hermes/profiles/.active_profile` | `hermes profile use <name>` |
| 桌面版 | `%APPDATA%/Hermes/active-profile.json` | 編輯 JSON 檔案 |

桌面版啟動時讀取 `active-profile.json` 來決定 spawn 參數。`hermes profile use default` 只改 CLI 側，桌面版不會跟著變。

### 完整使用流程（保有 Alice sessions）

1. 確認 `main.py` 已有層 1 + 層 2 + 層 3 補丁
2. 建立 `%APPDATA%/Hermes/active-profile.json`，內容：
   ```json
   {"profile": "alice"}
   ```
3. 關閉桌面版 → 重新打開
4. 桌面版 spawn `hermes --profile alice dashboard`
5. `_apply_profile_override` 設定 `HERMES_PROFILE_FROM_CLI=1`
6. `cmd_dashboard` 看到旗標 → 跳過 re-exec
7. Dashboard 直接用 alice profile 啟動 → sessions 回來

### 一鍵安裝注意事項

bootstrap.bat 或部署腳本如果自動執行 `hermes profile use alice`，會導致桌面版在下一次啟動時進入 execvpe 崩潰循環。必須：

1. 在 `hermes profile use alice` 之後立即建立 `%APPDATA%/Hermes/active-profile.json`
2. 或在一鍵安裝中納入 main.py 層 1+2+3 的修補
3. 或將 active profile 保持為 default，僅在 gateway 啟動時指定 profile
