---
name: alice-apps
description: "Alice 應用程式管理面板 — 啟動、停止、操控所有獨立子系統（LiveCode Studio、投資儀表板、GameStudio、N8N、DataHub、Cloud Sync、跨PC同步）。這些 APP 設計為 AI 可操控的工具。"
version: 1.3.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, apps, launcher, studio, dashboard, games, sync]
---

# Alice 應用程式管理面板

主人的所有獨立子系統統一管理入口。每個 APP 由 Hermes 啟動、停止、操控，同時主人也可獨立存取。

## ⚠️ 強制規則

當主人說「啟動 XX」「打開 XX」「關閉 XX」時，你**必須實際執行 terminal 命令**來啟動/停止對應的 APP。禁止只回文字。

---

## 🏗️ 多端點同步架構

當主人在多台電腦之間切換工作時，一鍵同步所有狀態。

### 初始安裝（雙擊 bootstrap.bat）

新電腦最簡單方式：
1. 瀏覽器打開 https://raw.githubusercontent.com/hansv0704/hermes-tools/main/bootstrap.bat → 另存新檔
2. 雙擊 `bootstrap.bat` → 自動 git clone + 執行一鍵安裝 → 輸入密碼 0704 → 完成

> ⚠️ 不要用 curl 下載 .bat — cmd 對 BOM/編碼敏感。`bootstrap.bat` 是純 ASCII，可安全雙擊。也不用 GitHub zip 下載 — zip 會破壞換行符號導致閃退。

bootstrap.bat 做的事：
```
git clone (或 pull 更新) → call 一鍵安裝.bat
```

一鍵安裝 6 步驟：檢查工具 → pip 依賴 → **互動輸入密碼 0704** → 同步記憶 → 安裝 skills → 設 alice 預設 profile + Gateway 背景服務

### 持續同步機制（v3 逐條合併）

| 層級 | 媒介 | 方向 | 頻率 |
|------|------|------|------|
| **全倉庫**（skills/scripts/memory/config） | GitHub | **`git add -A` + commit + push** / `git pull` + 自動部署 | 每 30 分鐘 cron |
| 設定（.env） | 加密 .env.enc | 一次性互動解密（密碼 0704） | 一鍵安裝時 |

**同步腳本 v3**（`scripts/sync_memory_github.py`）：
- **push**：`git pull` → 合併 memory 條目（union merge）→ **`git add -A`**（全倉庫）→ commit → push。不只記憶，skills、scripts、bootstrap.bat 全部一起同步。
- **pull**：`git pull` → 部署 `scripts/` 和 `hermes_skills/` 到 alice profile → 合併記憶條目（只拉新條目，不覆蓋本地）。
- 無差異 → 安靜 skip（cron 不推送通知）。
- 一鍵安裝會將此腳本複製到 `profiles/alice/scripts/`。
- 需要 `HERMES_WORKSPACE` 環境變數（一鍵安裝自動寫入 `.env`）。

### ⚠️ 多端點常見陷阱

- **不需要 `hermes -p alice`** — 一鍵安裝會自動執行 `hermes profile use alice`，桌面版打開就是 Alice。
- 記憶檔案是 `memories/USER.md` + `MEMORY.md` 純文字檔（以 `§` 分隔條目），不是 SQLite。
- `.env.enc` 用 openssl aes-256-cbc 加密，密碼 0704（互動輸入，不寫死在腳本中）。
- **「MEGA」是兆豐證券縮寫**，不是 MEGA.nz 雲端硬碟。路徑中的「MEGA備份」是兆豐相關資料夾，**不能用於跨電腦同步**。
- Hermes 的 secret redaction 會在顯示層遮蔽 `%VAR%` 和 API key，驗證 batch 檔案內容需 `python -c` + `rb` 讀取原始位元組。
- cron job script 名稱必須與 `profiles/alice/scripts/` 下的實際檔案名稱一致。
- batch 檔案在非中文 Windows 終端會因 Unicode 框線（╔═╗）或 emoji 亂碼，一律用 ASCII（+====+、[X][OK][!]）。
- `hermes cron create` 的 CLI **不支援 `--no_agent`**，該參數僅限 cronjob 內部工具。cron 一律由 Alice 在對話中用 cronjob 工具建立。
- **Gateway 在桌面版關閉時會一起停止**。需用 `hermes -p alice gateway install`（背景服務）保持 TG 24 小時在線。
- **Gateway install 需要回答 3 個互動提示**。用 `printf "N\nY\nY\n" | hermes -p alice gateway install`（N=不再立即啟動，Y=裝排程，Y=允許 UAC）。需手動點 UAC 確認。
- **pip protobuf 衝突**：`protobuf==6.33.6` 與 `google-ai-generativelanguage==0.6.15` 互衝。解法：`requirements.txt` 改 `protobuf>=3.20.2,<6.0.0`。
- **`git add -A` 大檔案陷阱**：全倉庫同步會吞入任何未 ignore 的檔案。若有 > 100MB 檔案（如 docx）會卡死所有 push。解法：(a) `.gitignore` 擋掉 `作業區/`、`temp_sync_workplace/`、`*.docx`、`~$*.xlsx`；(b) 若已誤入歷史，用 `git filter-branch --index-filter "git rm --cached --ignore-unmatch '<file>'" --prune-empty <base>..HEAD` 切除 + `git push --force-with-lease`。
- **Cron error 診斷**：若 cron 持續報 error 但腳本手動跑正常，先檢查 git push 是否被拒（`git push --dry-run`）。常見原因：non-fast-forward（另一台電腦在中間 push）或 large file reject。
- **Git 衝突自動化解**：push 被拒時先 `git stash` → `git pull` → `git stash pop` → 重新 commit + push。sync 腳本內建 rebase 重試機制。
- **`.env` 路徑反斜線陷阱**：`echo PATH=C:\... >> .env` 時 cmd 會吃掉反斜線。寫入路徑用 Python `write_text()`，或用 `%VAR:\=\\%` 替換。
- **`hermes config` 無 `get` 子命令**：用 `hermes -p alice config show | grep <key>`，或直接讀 `config.yaml`。

> 📘 完整教訓清單：`references/pitfalls.md` / `references/git-add-a-large-file-disaster.md`

### 🔀 多電腦 TG 衝突處理

桌面版 Hermes 內建 Gateway。多台電腦同時開桌面版 → 多個 Gateway 搶同一個 TG Bot → 訊息丟失。

**解法**：次要電腦關閉 TG 連線：

```bash
hermes -p alice config set telegram.enabled false
```

只留一台當 TG 主機。次要電腦桌面版照開、照樣聊天，只是不接 TG。
## 📟 LiveCode Studio v5.3（Hermes 全自動協作面板）

- **Port**: 5001
- **用途**: Session 啟動後全自動追蹤所有檔案變更，無需手動操作。工作區持久化 + 預設涵蓋所有 Hermes 常用目錄。
- **自動追蹤**: `/api/session/start` → 自動加入工作區 → watchdog 5 秒內偵測
- **前端**: `http://localhost:5001`（雙 Tab：📝操作紀錄 / 📂工作區 + Session 狀態條）
- **相關 skill**: `alice-lcs`（完整 API 與架構細節）
- **相關資源**: `skills/live_code_studio_skill.py`（核心）、`skills/lcs_template_v5.html`（前端）、`skills/lcs_workspaces.json`（持久化工作區）

### ⚠️ 全面追蹤（v5.2+ 關鍵改進）

**不需要手動追蹤！** Session 啟動時 LCS 自動將工作目錄加入監控。Hermes 任何檔案操作在 5 秒內自動出現在前端面板。

```bash
# 唯一必要步驟：啟動 session
curl -s -X POST http://localhost:5001/api/session/start \
  -H "Content-Type: application/json" \
  -d "{\"workdir\": \"<目前工作目錄>\"}"
```

> 安全防護：目錄 > 5000 檔案自動跳過，避免超大目錄掃描凍結。
> v5.3: 工作區持久化到 `lcs_workspaces.json`，重啟後自動恢復。預設涵蓋 Alice Legacy + Hermes Skills 兩個目錄。新檔案也自動標記（v5.2 修復）。

### 啟動（支援 --daemon 背景模式）

```bash
cd /d "%~dp0" && python run_studio.py --daemon
```

`--daemon` 模式使用 `pythonw`，log 寫入 `logs/lcs_daemon.log`。雙擊 `.bat` 會自動偵測並背景啟動。

---

## 📊 投資代理人儀表板（股票交易）

- **Port**: 5002
- **用途**: 股票分析、策略、模擬/實盤下單
- **⚠️ 鐵律**: 獨立系統，不整合進 Telegram

### 啟動

```bash
start "" "%WORKSPACE%\啟動投資代理人儀表板.bat"
```

### API 端點（已啟動後可用）

| 端點 | 用途 |
|:--|:--|
| `curl localhost:5002/api/ai/status` | 查詢狀態 |
| `curl localhost:5002/api/ai/start` | 啟動自主投資 |
| `curl localhost:5002/api/ai/stop` | 停止自主投資 |
| `curl localhost:5002/api/portfolio` | 持倉查詢 |

---

## 🎮 GameStudio（遊戲開發）

- **Port**: 5003
- **用途**: 遊戲商業化開發

### 啟動

```bash
cd "%WORKSPACE%" && python run_game_studio.py &
```

---

## 🔗 N8N 自動化伺服器

- **Port**: 5678
- **用途**: Webhook、定時任務、工作流自動化

### 啟動

```bash
start "" "%WORKSPACE%\啟動 N8N 伺服器.bat"
```

### 健康檢查

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz
```

---

## 📊 記憶壓縮自動化

防止記憶條目膨脹超過上限。主電腦自動維護。

### 運作機制

| 項目 | 設定 |
|------|------|
| 記憶上限 | **3,500 chars**（`hermes -p alice config set memory.memory_char_limit 3500`） |
| 壓縮閾值 | 用量 > 80%（> 2,800 chars）自動觸發 |
| 記憶壓縮腳本 | `scripts/auto_compress_memory.py` |
| Cron 頻率 | **每 3 小時**（`every 3h`） |

### 腳本邏輯

1. 讀取 `MEMORY.md`，計算 char 用量
2. 若 < 80% → 安靜 skip（cron 不推送通知）
3. 若 > 80% → 合併重複條目（前 60 字相同 = 重複，保留較長版）→ 寫入本地 + **遞增 `memory/.version`** + GitHub push

### 版本號覆蓋機制（B端自動接收壓縮結果）

主機壓縮時會遞增 `memory/.version`（v1→v2→v3...）。B端 pull 偵測到 remote_ver > local_ver → **整份覆蓋**本地記憶（不做 union merge，避免膨脹）。B端自己新增的記憶會在下次 push 合併回主機。

| 情境 | B端行為 |
|------|---------|
| remote_ver > local_ver | 整份覆蓋（主機壓縮過） |
| remote_ver == local_ver | 逐條合併（日常 sync） |
| B端 push | guild merge（聯集）推上 GitHub |

### 建立 Cron（由 Alice 對話中執行）

```
cronjob: schedule=every 2h, script=scripts/auto_compress_memory.py, no_agent=true, deliver=local, profile=alice
```

> 此 cron 由 Alice 用 cronjob 工具建立，CLI 不支援 `--no_agent`。

## 🧠 記憶同步（v3 逐條合併）

讓多台電腦共用同一套 Alice 設定與記憶。

- **腳本**: `scripts/sync_memory_github.py`（一鍵安裝自動複製到 `profiles/alice/scripts/`）
- **用途**: 比對本地 memories 與 GitHub repo，自動 git push
- **媒介**: GitHub（hermes-tools repo）+ openssl 加密 .env.enc（密碼 0704，互動輸入）

### 新電腦部署

```bash
git clone https://github.com/hansv0704/hermes-tools.git "%USERPROFILE%\Desktop\Hermes工具區"
cd /d "%USERPROFILE%\Desktop\Hermes工具區"
一鍵安裝.bat
# 輸入解密密碼: 0704
```

### 安裝後

打開桌面版 Hermes，對 Alice 說「幫我建立記憶同步 cron」— cron 由 Alice 用工具建立（CLI 參數不相容）。

### 手動同步

```bash
python "%HERMES_WORKSPACE%\scripts\sync_memory_github.py" push
python "%HERMES_WORKSPACE%\scripts\sync_memory_github.py" pull
```

### ⚠️ 重要

- Hermes 記憶是 `memories/USER.md` + `MEMORY.md` 純文字檔（以 `§` 分隔），不是 SQLite
- 一鍵安裝自動設 alice 為預設 profile（`hermes profile use alice`），桌面版打開就是 Alice
- **「MEGA」是兆豐證券縮寫**，不是 MEGA.nz 雲端硬碟。跨電腦同步用 GitHub，不是 MEGA。

---

## 📋 快速總覽

| APP | Port | 啟動命令 | 用途 |
|:--|:--|:--|:--|
| 📟 LiveCode Studio v5.3 | 5001 | `python run_studio.py --daemon` | Hermes 全自動協作審計面板 |
| 📊 投資儀表板 | 5002 | `.bat` 啟動 | 股票分析交易 |
| 🎮 GameStudio | 5003 | `python run_game_studio.py` | 遊戲開發 |
| 🔗 N8N | 5678 | `.bat` 啟動 | 工作流自動化 |
| 🗄️ DataHub | — | Python import | DuckDB 查詢 |
| ☁️ Cloud Sync | — | Python import | Google Drive 備份 |
| 🔄 跨PC同步 | — | `sync_memory_github.py` | GitHub + .env.enc 同步 |