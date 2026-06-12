---
name: alice-lcs
description: "Hermes ↔ LiveCode Studio v5.3 協作橋接 — Session 自動追蹤、持久化工作區、watchdog 全自動偵測。每次修改後無需手動通知，LCS 5 秒內自動標記。"
version: 5.3.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, lcs, livecode, audit, collaboration, auto-track]
---

# Alice LCS — Hermes ↔ LiveCode Studio 協作橋接

LCS 是 Hermes 操作的即時審計面板。主人打開 `http://localhost:5001` 就能看到 AI 的所有檔案修改。

## ⚠️ 強制規則

1. **開始重要工作前**，必須啟動 LCS session（`/api/session/start`）
2. Session 啟動後，LCS **自動**監控工作目錄（< 5000 檔案），watchdog 每 5 秒偵測新檔案與內容變更
3. **不需手動 `/api/files/track`** —— v5.2+ 全面自動化
4. 工作完成後可選擇性執行自我診斷

---

## 生命週期（v5.3 精簡版）

```
Session Start → (自動追蹤，5 秒內標記) → (可選: Self Review) → Session Stop
```

### Step 1: 啟動 Session（唯一手動步驟）

```bash
curl -s -X POST http://localhost:5001/api/session/start \
  -H "Content-Type: application/json" \
  -d "{\"workdir\": \"<目前工作目錄>\"}"
```

LCS 自動將 workdir 加入監控（若 < 5000 檔案），之後無需任何操作。

### Step 2: 自我診斷（可選）

```bash
curl -s -X POST http://localhost:5001/api/self_review
```

### Step 3: 結束 Session

```bash
curl -s -X POST http://localhost:5001/api/session/stop
```

---

## 手動追蹤（僅特殊情況）

當修改的檔案在監控範圍外（如臨時目錄、非工作區路徑），才需要手動追蹤：

```bash
curl -s -X POST http://localhost:5001/api/files/track \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"<相對路徑>\", \"content\": \"<檔案內容>\"}"
```

---

## 工作區管理

工作區已**持久化**（`lcs_workspaces.json`），重啟後自動恢復。預設涵蓋：
- `Alice Legacy`（舊 Alice 專案目錄）
- `Hermes Skills`（Hermes skill 目錄）

### 查詢

```bash
curl -s http://localhost:5001/api/workspace/list
```

### 手動新增（持久化）

```bash
curl -s -X POST http://localhost:5001/api/workspace/add \
  -H "Content-Type: application/json" \
  -d "{\"path\": \"C:/path/to/project\", \"name\": \"專案名稱\"}"
```

---

## 查詢 API

```bash
# Session 狀態
curl -s http://localhost:5001/api/session/info

# 追蹤檔案清單
curl -s http://localhost:5001/api/tracked

# 完整樹狀結構（追蹤 + 工作區 + 修改標記）
curl -s http://localhost:5001/api/tree
```

---

## LCS 生命週期管理

```bash
# 啟動（daemon 模式，從腳本所在目錄）
cd /d "%~dp0" && python run_studio.py --daemon

# 或雙擊啟動LiveCodeStudio.bat（自動檢測 + pythonw 背景執行）

# 停止
cd /d "%~dp0" && python run_studio.py --stop

# 檢查
python -c "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',5001)); s.close(); print('RUNNING' if r==0 else 'STOPPED')"
```

---

## 前端

主人瀏覽器：**http://localhost:5001**

- 📝 **操作紀錄** — Session 追蹤 + 近期變更
- 📂 **工作區** — 持久化監控目錄（預設涵蓋所有 Hermes 常用路徑）
- 🟢 **Session 狀態條** — 顯示 Hermes 連線狀態與工作目錄

---

## ⚠️ 常見問題

| 問題 | 原因 | 解法 |
|:--|:--|:--|
| Session 顯示「未連線」 | 未呼叫 `/api/session/start` | 執行 Step 1 |
| 修改的檔案沒出現 | 檔案在監控範圍外 | 手動 `/api/files/track` 或加入工作區 |
| 新檔案未被標記 | v5.1 以前舊版 bug | 已修復（v5.2） |
| Daemon 啟動失敗 | `datetime` import 順序 | 已修復（v5.3） |
| Auto-workspace 被跳過 | 目錄 > 5000 檔案 | 正常保護，手動加入工作區 |
| 重啟後工作區消失 | 使用 v5.2 以前版本 | v5.3 已持久化到 JSON |
