---
name: alice-hermes-repair
description: Hermes Windows 更新崩潰修復工具包 — 一鍵修復、安全更新、Defender 排除。解決桌面版更新時的 0xC0000005 記憶體崩潰、Port 9122 死鎖、venv 損壞等常見 Windows 問題。
version: 2.0.0
category: alice
---

# Hermes Windows 修復工具包

## 問題背景

Hermes 桌面版 (Electron) 在 Windows 上更新時，會透過 `Hermes-Setup.exe --update` 啟動一個 Tauri 安裝程式，該程式在背景執行 `hermes update --yes --gateway`。這個過程常見以下 4 層失敗：

| 層級 | 問題 | 原因 | 解決 |
|------|------|------|------|
| 1 | 記憶體崩潰 (0xC0000005) | Windows DEP/防毒誤判 Python 背景孵化為惡意行為 | Defender 排除 |
| 2 | Port 9122 死鎖 | 前次崩潰殘留 process 佔用 port，或 CLI/gateway 已在運行 | taskkill 清理 |
| 3 | 前端沙盒卡死 | Chromium navigator.vibrate 安全阻擋 | 不影響核心功能，重啟即可 |
| 4 | venv 損壞循環 | 更新失敗後 venv 處於半更新狀態，Retry 永遠失敗 | 刪除 venv 重建 |

**⚠️ 關鍵認知**：0xC0000005 ≠ venv 損壞。**大多數情況 venv 是完全健康的**（CLI 可正常執行、hermes doctor 全過），崩潰純粹是 Windows DEP/Defender 在 Electron 嘗試 spawn `hermes.exe` 子行程時將其擊殺。**先診斷再修復，不要直接刪 venv。**

**⚠️ Port 衝突是煙霧彈**：即使手動清空 Port 9122、釋放所有殘留行程，桌面版 spawn 的 `hermes.exe` **仍然會被 DEP 擊殺**（多次 session 實測驗證：清空後桌面版找到 Port 9120 短暫成功，但後續重試仍觸發 0xC0000005）。Port 死亡循環中的 `exit(0)` 只是因為舊 gateway 佔用埠口讓 spawn 自願退出，不是根因。**Defender 排除是治本方案，CLI 繞過是治標方案。**

### ⚠️ CLI-first 繞過方案（不靠 Defender 排除）

當 Defender 排除無法立即生效時，可用 CLI 直接啟動 gateway 繞過 Electron DEP：

1. `taskkill /f /im Hermes.exe` + `taskkill /f /im hermes.exe` **殺光所有行程（包括殘留的子行程）**
2. 確認 ports 乾淨：`netstat -ano | grep 912`（應只剩原本連線的 gateway）
3. 從 CLI 啟動：`hermes gateway run --profile alice --replace`
4. Gateway 啟動後再開桌面版 → 桌面版偵測到現成 gateway 就直接連上，不 spawn 子行程

原理：桌面版 Electron 用 `child_process.spawn()` spawn `hermes.exe` 會觸發 DEP；但 CLI 直接啟動或 Python `subprocess.Popen()` 啟動不會。桌面版啟動時若發現 port 9120 已有 gateway，會顯示「Machine dashboard already running on port 9120」並直接連線，完全跳過 spawn 步驟。

**⚠️ `--replace` 陷阱（2026-06-12 發現）**：若已有 gateway 在跑，第二個 `gateway run --replace` 會啟動行程但不綁定任何 port（純 no-op 行程，佔用 RAM 但無功能）。**必須先殺光所有行程再啟動。**

一鍵方案：`啟動Hermes_CLI_Gateway.bat`（位於 `Hermes工具區`），詳見 `references/cli-gateway-workaround.md`。

### 桌面版崩潰循環模式

桌面版 Electron 會在後端崩潰後自動重試，形成可預測的循環模式。目前已知三種觸發路徑：

**路徑 A — Electron spawn DEP 擊殺**（已由 Defender 排除 + CLI 繞過解決）

```
桌面版 spawn hermes.exe → 0xC0000005 (DEP 擊殺)
    ↓ 自動重試
桌面版 spawn hermes.exe → 偵測到 Port 9122 被佔用 → exit 0
    ↓ 自動重試
桌面版 spawn hermes.exe → 0xC0000005 (再次 DEP 擊殺)
    ↓ 無限循環...
```

**路徑 B — `os.execvpe` profile re-exec 崩潰**（2026-06-12 發現，已修復）

當 active profile 設為非 default（如 alice）時，dashboard 啟動邏輯會呼叫 `os.execvpe` 重新執行自己（`-p default --open-profile alice`）。Windows 上 `os.execvpe` 不是真正的 exec——CRT 用 spawn + exit 模擬，從 Electron spawn 的子行程中呼叫時會間歇性 ACCESS VIOLATION。

崩潰點：`hermes_cli/main.py:10364` → `os._execvpe`

修復（已在 main.py 實作）：Windows 上用 `subprocess.Popen(DETACHED_PROCESS | CREATE_NO_WINDOW)` + `sys.exit(0)` 取代 `os.execvpe`。POSIX 保持原有 `os.execvpe`（真正的 replace process image）。

**最簡單的繞過**：`hermes profile use default` 直接把 active profile 切成 default，dashboard 啟動時就不會進入 execvpe re-exec 路徑。

⚠️ **但這樣做桌面版會以 default profile 啟動，Alice 的 sessions/記憶/設定都不會出現。** 若要保有 Alice 的 sessions，必須搭配三層修復（見 `references/os-execvpe-crash.md`）。

**桌面版 vs CLI 的 profile 系統是獨立的**：

| 系統 | 設定位置 | 指令 |
|------|---------|------|
| CLI | `~/.hermes/profiles/.active_profile` | `hermes profile use <name>` |
| 桌面版 | `%APPDATA%/Hermes/active-profile.json` | 編輯 JSON 檔案 |

桌面版啟動 dashboard 時讀取 `active-profile.json`，若為 `alice` 則 spawn `hermes --profile alice dashboard`。必須搭配層 2 的 `args.profile` 檢查才能避免重新觸發 re-exec。

**完整三層修復後的使用流程**：
1. 確認 `main.py` 已有層 1（execvpe 安全替代）+ 層 2（args.profile 檢查）補丁
2. 建立 `%APPDATA%/Hermes/active-profile.json` 內容為 `{"profile": "alice"}`
3. 關閉桌面版 → 重新打開 → 桌面版用 `--profile alice` spawn dashboard → 不觸發 re-exec → Alice 的 sessions 全部回來

完整診斷與修復細節：見 `references/os-execvpe-crash.md`。

從 `desktop.log` 看到交替出現 `exited (3221225477)` 和 `exited (0)` 就是這個模式。Port 9122 可能被先前的 CLI session / gateway 殘留佔用。

完整日誌分析與退出碼對照：見 `references/crash-loop-pattern.md`。

## 診斷 SOP（先診斷再動手）

不要直接刪 venv。先走以下流程：

```bash
# Step 0: 檢查 active profile（2026-06-12 新增）
# 若 active profile 不是 default，桌面版啟動 dashboard 時會觸發 os.execvpe
# 路徑 B 崩潰。最簡單的修復：直接切成 default。
hermes profile list
# 若 ◆ 標記不是 default:  hermes profile use default

# Step 1: 檢查 CLI 是否正常
%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe doctor

# Step 2: 檢查 Python 是否可 import
%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe -c "import numpy; print('OK')"

# Step 3: 檢查桌面日誌中的退出碼
type %LOCALAPPDATA%\hermes\logs\desktop.log | findstr "exited"

# Step 4（新增）: Python subprocess spawn 測試 — 終極 DEP 區分法
python -c "
import subprocess, os
hermes = os.path.expandvars(r'%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe')
r = subprocess.run([hermes, 'gateway', 'run', '--profile', 'alice'],
                   capture_output=True, text=True, timeout=8,
                   creationflags=subprocess.CREATE_NO_WINDOW)
print(f'exit={r.returncode}')
"
```

| 診斷結果 | 退出碼 | 動作 |
|----------|--------|------|
| **Active profile ≠ default + 桌面崩潰** | `3221225477` | **路徑 B** → `hermes profile use default`（繞過 execvpe），無需重建 venv |
| CLI 正常 + Python 正常 + 桌面崩潰 | `3221225477` (0xC0000005) | **純 DEP 問題（路徑 A）** → 只需 Defender 排除，venv 無需重建 |
| CLI 失敗 + hermes doctor 報錯 | 任何 | venv 損壞 → 執行 `修復Hermes.bat` 深度修復 |
| CLI 正常 + 桌面顯示 Port 衝突 | `0` (正常退出) | Port 9122 被佔用 → taskkill 清理舊行程 |
| **Python spawn 成功、Electron spawn 崩潰** | Python: `1`（gateway 已在跑）或 timeout；Electron: `3221225477` | **鐵證：venv 健康，純 DEP**（Python subprocess 和 Electron child_process 使用不同 Windows API flag，只有後者觸發 DEP） |

### 如何判斷 venv 是否損壞

```bash
# 快速檢查三項
hermes doctor              # 必須全部 ✓
python -c "import numpy"   # 已知會觸發 0xC0000005 的套件
hermes gateway status      # 確認 gateway 狀態
```

三項全過 = venv 健康，問題在 DEP/Defender。

### Python spawn vs Electron spawn 診斷原理

Python 的 `subprocess.Popen()` 和 Node.js 的 `child_process.spawn()` 使用不同的 Windows `CreateProcess` 旗標組合。Electron 的 spawn 觸發了 Windows DEP（資料執行防止）將 `hermes.exe` 子行程視為 code injection 而終止。若 Python spawn 可以成功啟動 gateway 且持續運行（`process(action='poll')` 確認），但桌面版 spawn 立即回傳 `0xC0000005`，則可以 100% 確定 venv 無損壞，問題在作業系統層級。

### ⚠️ `rm -rf venv` 需要使用者明確同意

Hermes 會封鎖沒有使用者明確同意的破壞性操作。在對話中執行 `rm -rf` 刪除 venv 前，**必須先用 `clarify` 工具取得使用者同意**，否則指令會因 timeout 被 BLOCKED。不可在未經同意的情況下嘗試繞過。

## 工具清單

六個核心腳本 + 一個說明檔位於 `%USERPROFILE%\\Desktop\\Hermes工具區\\`，透過 GitHub `hansv0704/hermes-tools` 雙機同步。

**若目錄不存在**：代表首次使用或新電腦，需從 Hermes 對話中建立。告知 Alice：「幫我在桌面建立 Hermes工具區」，Alice 會用 Python `encoding='utf-8-sig'` 寫入 bat（確保中文不亂碼）。建立完成後再依下方流程操作。

### 1. `修復Hermes.bat` — 一鍵修復
雙擊執行，全自動修復所有問題：
1. 終止所有 Hermes.exe / hermes.exe / python.exe
2. 釋放 Port 9122
3. 嘗試 CLI 更新（如果 CLI 還活著）
4. 如果 CLI 失敗 → 深度修復：刪除 venv → uv 重建 → pip 安裝 → hermes update
5. 重新啟動桌面版

### 2. `安全更新Hermes.bat` — 治本方案
**推薦日常使用**，避開桌面版的 buggy 更新按鈕：
```
git pull → hermes update --yes --gateway → hermes desktop --build-only
```
不會觸發 Electron handoff，避免 0xC0000005。

### 3. `Defender排除Hermes.bat` — 防毒排除
需要管理員權限。將 `%LOCALAPPDATA%\hermes` 和 `Hermes.exe`、`python.exe` 加入 Windows Defender 排除清單，防止誤殺。

**⚠️ 已知陷阱**：此 bat 使用 `2>nul` 吞掉所有錯誤輸出，即使排除失敗（如權限不足）使用者也會看到「✓ 已處理」。若執行後桌面版仍崩潰，請手動確認：`powershell -Command "Get-MpPreference | Select-Object -ExpandProperty ExclusionPath"`（需管理員）。

### 4. `啟動Hermes_CLI_Gateway.bat` — CLI 繞過 DEP 啟動
**Defender 排除無法立即生效時的備用方案**。先從 CLI 啟動 gateway（不經過 Electron spawn，不觸發 DEP），再開桌面版自動連上已有 gateway。詳見 `references/cli-gateway-workaround.md`。

### 5. `Hermes急救.bat` — 五合一自動診斷修復 🆕
**出事了先點這個**。全自動執行：
1. 清理殘留行程（taskkill 全殺）
2. 檢查 os.execvpe 修復是否存在，不見就 `git am` 還原
3. 檢查桌面版 `active-profile.json`，不見就建立
4. 設定 `git pull.rebase=true` 防止修復被覆蓋
5. CLI 啟動 gateway 繞過 DEP

雙擊 → 等 5 秒 → 開桌面版。範本：`templates/Hermes急救.bat`。

### 6. `初始化新端.bat` — 新電腦一鍵就緒 🆕
新電腦或重灌後第一個雙擊。自動：檢查 repo → `git am` 修復 → 建立 `active-profile.json` → xcopy 還原記憶/技能 → 設定 rebase。

### 7. `auto_sync.bat` — cron 自動同步 🆕
由 cron job 每 30 分鐘觸發：`git stash` + `git pull --rebase` + `git stash pop`。衝突時強制覆蓋。同步後 xcopy 最新記憶/技能到備份。silent 運行。

### 8. `使用說明.txt` — 開箱即讀 🆕
雙擊打開，內含：檔案清單、同步流程、日常 SOP、殭屍說明、崩潰路徑對照表。

## 使用流程

### 首次設定（B 電腦）
```batch
cd %USERPROFILE%\Desktop\Hermes工具區
git pull
Defender排除Hermes.bat   ← 右鍵「以系統管理員身分執行」
```

### 日常更新
```batch
cd %USERPROFILE%\Desktop\Hermes工具區
安全更新Hermes.bat
```

### 出事了（桌面版崩潰循環）

```batch
# Step 0: 最簡單的修復 — 檢查 active profile
hermes profile list
# 若 ◆ 不是 default: hermes profile use default（繞過 execvpe 路徑 B）

# Step 0.5: 若要保留 Alice sessions，檢查桌面版 profile 設定
type %APPDATA%\Hermes\active-profile.json
# 若檔案不存在或內容為 default → 桌面版看不到 Alice sessions
# 需建立: echo {"profile":"alice"} > %APPDATA%\Hermes\active-profile.json
# （搭配 main.py 層 1+2 修復）

# 優先方案：CLI 繞過 DEP（不需管理員）
cd %USERPROFILE%\Desktop\Hermes工具區
啟動Hermes_CLI_Gateway.bat

# 治本方案：Defender 排除（需管理員）
Defender排除Hermes.bat   ← 右鍵「以系統管理員身分執行」

# 最後手段：深度修復（僅在 hermes doctor 失敗時使用）
修復Hermes.bat
```

## ⚠️ 強制規則

1. **先診斷再修復** — 執行 `hermes doctor` 和 Python import 測試，確認是 DEP 問題還是 venv 損壞，不要直接刪 venv
2. **桌面版崩潰先檢查 active profile** — `hermes profile list`。若 ◆ 不是 default，先執行 `hermes profile use default`，這能繞過 `os.execvpe` 路徑 B 崩潰（2026-06-12 新增）
3. **桌面版 profile 與 CLI profile 是獨立的** — 桌面版讀取 `%APPDATA%/Hermes/active-profile.json`，CLI 讀取 sticky 設定。`hermes profile use default` 只改 CLI 側，桌面版可能仍以舊 profile 啟動。若要桌面版用 alice 正常啟動，需建立 `active-profile.json` + main.py 層 1+2 修復（見 `references/os-execvpe-crash.md`）（2026-06-12 新增）
3. **bat 檔案必須使用 UTF-8 with BOM 編碼** — 否則 Windows cmd 會用 Big5 解析導致中文全變亂碼。用 Python `encoding='utf-8-sig'` 寫入即可
4. **永遠不要點桌面版的 Update 按鈕** — 使用 `安全更新Hermes.bat` 代替
5. **修復失敗時，先執行 `Defender排除Hermes.bat` 再重試**
6. **腳本中的路徑使用 `%LOCALAPPDATA%` 變數**，不寫死使用者名稱
7. **桌面版崩潰時先檢查 desktop.log** — `findstr "exited" %LOCALAPPDATA%\hermes\logs\desktop.log`，確認是 0xC0000005 還是 Port 衝突
8. **`--replace` 無法在已有 gateway 時綁定 port** — 必須先 `taskkill /f /im hermes.exe` 殺光所有行程再啟動新 gateway
9. **`Defender排除Hermes.bat` 若仍用 v1（含 `2>nul`），錯誤會被吞掉** — 應更新為 v2 版（`templates/Defender排除Hermes_v2.bat`），用 `-ErrorAction Stop` + 逐項檢查 errorlevel
10. **一鍵安裝/deploy 腳本若執行 `hermes profile use <非default>`** — 必須在之後立即建立 `%APPDATA%/Hermes/active-profile.json`，否則桌面版下次啟動會觸發 `os.execvpe` 崩潰循環（路徑 B）。或納入 main.py 層 1+2+3 修補。（2026-06-12 新增）
11. **桌面版 profile 和 CLI profile 是獨立的** — `hermes profile use` 不影響桌面版。若桌面版需以特定 profile 啟動，必須編輯 `%APPDATA%/Hermes/active-profile.json`。（2026-06-12 新增）
12. **`os.execvpe` 在 Windows 上絕不可靠** — 永遠不要假設它像 POSIX 一樣 atomic。從 Electron spawn 的子行程中呼叫尤其危險。Windows 上 re-exec 一律使用 `subprocess.Popen(DETACHED_PROCESS|CREATE_NO_WINDOW)` + `sys.exit(0)`。（2026-06-12 新增）

## 技術細節

- Hermes 桌面版路徑：`%LOCALAPPDATA%\\hermes\\hermes-agent\\apps\\desktop\\release\\win-unpacked\\Hermes.exe`
- CLI 路徑：`%LOCALAPPDATA%\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe`
- uv 路徑：`%LOCALAPPDATA%\\hermes\\bin\\uv.exe`
- 更新流程源碼：`apps/bootstrap-installer/src-tauri/src/update.rs`

## 雙機同步架構 (2026-06-12)

整個 `Hermes工具區` 透過 GitHub repo `hansv0704/hermes-tools` 在 A/B 端之間同步。

### A/B 端定義

| | A端（公司） | B端（家用） |
|---|---|---|
| USERPROFILE | `C:\Users\hans` | `C:\Users\User` |
| 角色 | 主力機 | 備用機 |
| telegram.enabled | true | false（避免搶TG） |
| GIS/投資/L2 | ✅ 全部在這 | ❌ |

### 完整檔案清單

```
Hermes工具區/
├── 使用說明.txt              ← 開箱即讀
├── 初始化新端.bat            ← 新電腦第一個雙擊
├── 安全更新Hermes.bat         ← 日常更新（含 git stash 自動處理髒檔）
├── Hermes急救.bat (v2.0)     ← 出任何事就按（含殭屍清理）
├── Defender排除Hermes.bat    ← 治本方案（需管理員）
├── 修復Hermes.bat            ← 最後手段（重建 venv）
├── auto_sync.bat             ← cron 每30分鐘自動 git pull
├── .gitignore                ← Alice記憶_backup/ 和 Alice技能_backup/ 不入 git
├── 0001-...patch             ← os.execvpe 修復備份
├── Alice記憶_backup/         ← 記憶備份（不入 git，初始化自動 xcopy）
└── Alice技能_backup/         ← 技能備份（不入 git，初始化自動 xcopy）
```

### 同步機制

1. **GitHub repo**：`hansv0704/hermes-tools` 儲存所有 `.bat`、`.txt`、`.patch` 檔案。記憶和技能備份不入 git（`.gitignore`），透過 `xcopy` 手動同步
2. **Cron auto-sync**：A端每 30 分鐘自動 `git pull --rebase` + 備份最新記憶/技能到工具區（job: `146b20ef8325`）
3. **B端同步**：`git clone` 後雙擊 `初始化新端.bat`，自動 `git am` 修復 + xcopy 還原記憶/技能

### 新端初始化流程

```
1. git clone https://github.com/hansv0704/hermes-tools.git "%USERPROFILE%\Desktop\Hermes工具區"
2. cd "%USERPROFILE%\Desktop\Hermes工具區"
3. 初始化新端.bat
   → git am 套用 os.execvpe 修復
   → 建立 %APPDATA%/Hermes/active-profile.json
   → xcopy 還原 Alice 記憶和技能
4. 完成
```

### 路徑規範（強制）

所有 bat 腳本只使用 `%USERPROFILE%`、`%LOCALAPPDATA%`、`%APPDATA%` 變數，**嚴禁寫死 `C:\Users\hans\` 或 `C:\Users\User\`**。任務標記 `[A端]` 或 `[B端]` 區分執行對象。

## ⚠️ 與使用者溝通的語言規則

- **禁用內部技術術語**：不要對使用者說「gateway」「backend spawn」「re-exec」「port 9120」。使用者不需要懂這些
- **用使用者體驗描述**：「桌面版打開了」「Telegram 能跟我講話」「雙擊急救就好」「修復按鈕」
- **指令要具體**：不要說「啟動 gateway」，說「雙擊 Hermes急救.bat」
- **出事了 → 一句話答案**：不要解釋五層原因，直接說「雙擊 Hermes急救.bat」
