# 桌面版崩潰循環模式 — 完整日誌分析

## 實例（2026-06-12）

### 診斷結果

| 檢查項目 | 結果 |
|----------|------|
| `hermes doctor` | ✅ 全部通過 |
| `python --version` | ✅ Python 3.11.15 |
| `python -c "import numpy"` | ✅ numpy 2.4.6 OK |
| CLI 直接執行 | ✅ 正常（對話就是透過 CLI 進行） |
| 桌面版啟動 | ❌ 0xC0000005 |

**結論**：venv 完全健康，問題純粹是 Windows DEP/Defender 在 Electron spawn 子行程時介入。

### 桌面日誌中的崩潰循環

```
[hermes] [boot] Starting Hermes backend via existing Hermes CLI
[hermes] [boot] Waiting for Hermes backend to become ready
[hermes] Hermes backend exited (3221225477)        ← 0xC0000005 DEP 擊殺
[hermes] [boot] Hermes backend exited before it became ready (3221225477).

[hermes] [boot] Starting Hermes backend via existing Hermes CLI  ← 自動重試
[hermes] Machine dashboard already running on port 9122.         ← Port 衝突
[hermes] Hermes backend exited (0)                               ← 正常退出

[hermes] [boot] Starting Hermes backend via existing Hermes CLI  ← 再次重試
[hermes] Hermes backend exited (3221225477)        ← 又是 DEP 擊殺
```

### 退出碼對照

| 退出碼 | 十進位 | 十六進位 | 含義 |
|--------|--------|----------|------|
| `3221225477` | 3221225477 | `0xC0000005` | STATUS_ACCESS_VIOLATION — DEP/記憶體違規 |
| `0` | 0 | `0x0` | 正常退出（通常是 Port 已被佔用，後端自願退出） |

### 修復路徑

1. **Defender 排除**（治本）：`Defender排除Hermes.bat`（需管理員權限）
2. **釋放 Port 9122**：`taskkill /f /pid <PID>` 清理殘留 gateway
3. **僅在 doctor 失敗時重建 venv**：`修復Hermes.bat`

### Defender 排除失敗時的 PowerShell 錯誤

```
Add-MpPreference : HRESULT 0xc0000142
```
→ 權限不足。必須「以系統管理員身分執行」bat 檔案。**無法從 Hermes terminal 對話中繞過**，因為 terminal 工具不具有管理員權限。

### Port 9122 佔用檢查

```bash
netstat -ano | grep ':9122'
# 若顯示 LISTENING，記下 PID
powershell -Command "Get-Process -Id <PID> | Select-Object Id,ProcessName,Path"
# 確認是否為殘留的 hermes/python 行程
```

### Python subprocess spawn 診斷（終極 DEP 驗證）

此測試可**無爭議地**證明 venv 健康但 Electron spawn 被 DEP 攔截：

```python
import subprocess, os, time

hermes = os.path.expandvars(r'%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe')

# 方式 1：快速測試（會因 gateway 已在跑而 exit 1，非 crash）
r = subprocess.run([hermes, 'gateway', 'run', '--profile', 'alice'],
                   capture_output=True, text=True, timeout=8,
                   creationflags=subprocess.CREATE_NO_WINDOW)
print(f'exit={r.returncode}')  # 1 = gateway 已在跑（正常）；3221225477 = crash

# 方式 2：背景啟動 gateway（驗證長期存活）
proc = subprocess.Popen([hermes, 'gateway', 'run', '--profile', 'alice'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW)
time.sleep(3)
if proc.poll() is None:
    print(f'Gateway PID {proc.pid} 存活 — venv 健康')
else:
    print(f'Gateway died with code {proc.poll()}')
```

**實測結果（2026-06-12）**：Python spawn 的 gateway (PID 45260) 在 ports 9120-9130 上成功監聽，持續運行。同時段 Electron spawn 的 hermes.exe 仍在回傳 0xC0000005。**鐵證**。

### Gateway 監聽埠口範圍

成功啟動的 gateway 可能在以下埠口監聽（2026-06-12 實測）：

```
Port 9120: LISTENING
Port 9121: LISTENING
Port 9123: LISTENING
Port 9125: LISTENING
Port 9127: LISTENING
Port 9128: LISTENING
Port 9129: LISTENING
Port 9130: LISTENING
```

不應假設 gateway 只在 9122——桌面版可能動態選擇可用埠口。

### 已知可用的繞過方案

| 方案 | 效果 | 限制 |
|------|------|------|
| Python `subprocess.Popen` 啟動 gateway | ✅ gateway 正常運行 | 桌面版仍會嘗試 spawn 自己的 hermes.exe |
| CLI 手動 `hermes gateway run` | ✅ 正常 | 同上，且須保持 terminal 開啟 |
| Defender 排除 | ✅ 根治 | 需管理員權限，無法從 terminal 對話中執行 |
| `修復Hermes.bat` (venv 重建) | ⚠️ 不適用於 DEP 情況 | venv 本來就健康，重建無助於解決 DEP |
