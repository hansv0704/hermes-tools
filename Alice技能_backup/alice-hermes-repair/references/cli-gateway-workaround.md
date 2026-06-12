# CLI Gateway 繞過 DEP 方案

## 適用場景

- 桌面版 Hermes 持續崩潰循環（0xC0000005 → exit(0) → 0xC0000005）
- `hermes doctor` 全部通過，venv 健康
- `Defender排除Hermes.bat` 無法立即生效（需管理員、權限不足、或排除未實際寫入）

## 原理

桌面版 Electron 用 Node.js `child_process.spawn()` 啟動 `hermes.exe` 子行程時觸發 Windows DEP 擊殺。
但 CLI 直接啟動或 Python `subprocess.Popen()` 啟動的 gateway **不受 DEP 影響**。

桌面版啟動時會先檢查 port 9120 是否已有 gateway 在監聽：
- 若有 → 顯示「Machine dashboard already running on port 9120」→ 直接連線，不 spawn
- 若無 → 嘗試 spawn `hermes.exe` → DEP 擊殺 → 崩潰循環

因此先從 CLI 啟動 gateway，桌面版就會跳過 spawn 步驟，直接連上。

## 步驟

### 手動執行

```batch
:: Step 1: 殺光所有行程
taskkill /f /im Hermes.exe
taskkill /f /im hermes.exe

:: Step 2: 確認 ports 乾淨（應只看到現有連線的 gateway）
netstat -ano | findstr ":912"

:: Step 3: 從 CLI 啟動 gateway
start "" "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe" gateway run --profile alice --replace

:: Step 4: 等待 5 秒後啟動桌面版
timeout /t 5
start "" "%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe"
```

### 一鍵 bat

雙擊 `啟動Hermes_CLI_Gateway.bat`（位於桌面 `Hermes工具區`）。

## ⚠️ 已知陷阱

### `--replace` 不啟動新 gateway
若已有 gateway 在跑，再執行 `gateway run --replace` 只會啟動一個不綁定任何 port 的 no-op 行程。
**必須先殺光所有 hermes.exe 行程再啟動。**

### 殘留子行程佔用 ports
桌面版多次崩潰重試會留下多個 orphan 子行程，各自佔用 9121-9129 等 ports。
清理時要用 `tasklist` 確認，不只殺 PID 也要殺所有 `hermes.exe` 和 `Hermes.exe`。

### 驗證 gateway 成功啟動
```batch
netstat -ano | findstr ":9120"
```
應看到 `LISTENING` 狀態。若無，檢查 gateway 行程是否存活：`tasklist | findstr hermes`

## 實測記錄

### 2026-06-12 Session
- 桌面 log 顯示 10+ 次 0xC0000005 → exit(0) 循環
- 8 個殘留子行程佔用 ports 9121-9129
- `--replace` 在已有 gateway 時啟動 no-op 行程（PID 2568，無 port 綁定）
- 全殺後重啟 gateway → 成功綁定 ports
- 驗證：Python `subprocess.Popen` 可成功啟動長期存活的 gateway
