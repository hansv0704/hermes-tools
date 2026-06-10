---
name: alice-apps
description: "Alice 應用程式管理面板 — 啟動、停止、操控所有獨立子系統（LiveCode Studio、投資儀表板、GameStudio、N8N、DataHub、Cloud Sync）。這些 APP 設計為 AI 可操控的工具。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, apps, launcher, studio, dashboard, games]
---

# Alice 應用程式管理面板

主人的所有獨立子系統統一管理入口。每個 APP 由 Hermes 啟動、停止、操控，同時主人也可獨立存取。

## ⚠️ 強制規則

當主人說「啟動 XX」「打開 XX」「關閉 XX」時，你**必須實際執行 terminal 命令**來啟動/停止對應的 APP。禁止只回文字。

---

## 📟 LiveCode Studio（程式碼編輯器）

- **Port**: 5001
- **用途**: AI 輔助程式碼編輯、版本比對、自我診斷
- **設計理念**: 給 AI 操控的程式碼工作室

### 啟動

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && start python run_studio.py
```

或用 terminal background：
```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python run_studio.py &
```

### 停止

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python run_studio.py --stop
```

### 檢查狀態

```bash
python -c "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',5001)); s.close(); print('RUNNING' if r==0 else 'STOPPED')"
```

### 開啟網頁介面

```
http://localhost:5001
```

---

## 📊 投資代理人儀表板（股票交易）

- **Port**: 5002
- **用途**: 股票分析、策略、模擬/實盤下單
- **⚠️ 鐵律**: 獨立系統，不整合進 Telegram

### 啟動

```bash
start "" "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\啟動投資代理人儀表板.bat"
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
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python run_game_studio.py &
```

### 停止

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && start "" "關閉GameStudio.bat"
```

---

## 🔗 N8N 自動化伺服器

- **Port**: 5678
- **用途**: Webhook、定時任務、工作流自動化

### 啟動

```bash
start "" "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\啟動 N8N 伺服器.bat"
```

### 健康檢查

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz
```

---

## 🗄️ DataHub（DuckDB 資料中樞）

主人的核心資料庫在 `data/alice_core.db`。用於查詢系統事實、任務紀錄。

### 查詢

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python -c "
import sys; sys.path.insert(0, 'skills')
from data_hub_skill import DataHubSkill
import json
skill = DataHubSkill()
result = skill.execute('manage_data_hub', {
    'action': 'query',
    'sql': 'YOUR_SQL_HERE'
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

---

## ☁️ Cloud Sync（Google Drive 備份）

### 全量備份

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python -c "
import sys; sys.path.insert(0, 'skills')
from cloud_sync_skill import CloudSyncSkill
import json
skill = CloudSyncSkill()
result = skill.execute('backup_architecture_to_cloud', {}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

---

## 📋 快速總覽

| APP | Port | 啟動命令 | 用途 |
|:--|:--|:--|:--|
| 📟 LiveCode Studio | 5001 | `python run_studio.py` | AI 程式碼編輯器 |
| 📊 投資儀表板 | 5002 | `.bat` 啟動 | 股票分析交易 |
| 🎮 GameStudio | 5003 | `python run_game_studio.py` | 遊戲開發 |
| 🔗 N8N | 5678 | `.bat` 啟動 | 工作流自動化 |
| 🗄️ DataHub | — | Python import | DuckDB 查詢 |
| ☁️ Cloud Sync | — | Python import | Google Drive 備份 |
