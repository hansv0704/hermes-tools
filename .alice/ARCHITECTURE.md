# 🏗️ Alice 系統架構總覽
> **建立**：2026-06-02 10:18
> **用途**：AI 隨時可透過此文件「看懂自己」——了解整體架構、模組依賴、資料流、關鍵檔案。

---

## 第一層：系統分區

```
Alice 系統
├── 🧠 Alice 核心（Telegram Bot + Agent 大腦）
├── 💰 投資代理人（獨立 Flask 伺服器，port 5002）
├── 🗺️ GIS 監控（獨立監控循環）
├── 📟 LiveCode Studio（獨立編輯器 APP）
├── 📊 n8n 自動化（獨立 APP，port 5678）
└── 🎮 GameStudio（遊戲商業化，建置中，port 5003）
```

---

## 第二層：Alice 核心內部結構

```
alice_core/
├── agent.py              ← 大腦主控（工具路由、思考決策）
├── main.py               ← 啟動入口
├── handlers.py           ← Telegram 指令處理（純聊天層）
├── memory.py             ← 記憶管理（短期/長期/DuckDB）
├── telegram_bot.py       ← Telegram Bot 實作
├── skills/               ← 技能庫（可獨立呼叫的 Python 模組）
│   ├── live_code_studio_skill.py  ← LiveCode Studio 技能
│   ├── gis_data_matcher_skill.py   ← GIS Excel 配對技能（COM 自動化）
│   ├── os_control_skill.py         ← 系統操控技能
│   └── ...
├── .alice/               ← 系統知識中樞（本次對話讀取的檔案都在這裡）
│   ├── INDEX.md           ← 知識中樞導航
│   ├── FACTS.md           ← 不可變更事實
│   ├── TASK_BOARD.md      ← 開發看板
│   ├── LOG.md             ← 變更日誌
│   └── ARCHITECTURE.md    ← 本文件
└── backups/              ← 還原點備份
```

---

## 第三層：關鍵依賴關係

| 模組 A | 依賴方向 | 模組 B | 說明 |
|:--|:--|:--|:--|
| agent.py | → 呼叫 | skills/*.py | 大腦透過工具系統呼叫各技能 |
| handlers.py | → 使用 | telegram_bot.py | Telegram 指令轉發 |
| agent.py | → 讀寫 | memory.py | 大腦讀寫記憶 |
| agent.py | → 查詢 | DuckDB (facts) | 查詢 facts 表 |
| 投資代理人 | ✗ 不應 | handlers.py | 鐵律隔離：投資 API 不經 Telegram |
| GIS 監控 | ✗ 不應 | agent.py | 獨立監控循環，僅透過 gis_* 工具互動 |

---

## 第四層：資料流

```
主人 Telegram 訊息
  → telegram_bot.py
    → handlers.py（解析指令）
      → agent.py（AI 思考 + 工具路由）
        → skills/*.py（執行具體任務）
        → DuckDB（查詢 facts / 記憶）
        → .alice/*.md（讀取架構知識）
      → telegram_bot.py（回傳結果）
    → 主人 Telegram
```

---

## 第五層：獨立伺服器清單

| 伺服器 | Port | 啟動方式 | 用途 |
|:--|:--|:--|:--|
| 投資代理人 | 5002 | `啟動投資代理人儀表板.bat` | 股票分析、下單、策略 |
| n8n 自動化 | 5678 | 獨立 APP | Webhook、定時任務 |
| LiveCode Studio | 動態 | `live_code_studio_skill.py` | 程式碼編輯與自檢 |
| GIS 監控 | 無（背景循環） | `啟動監控.bat` | 測站數據監控 |
| GameStudio | 5003 | `啟動GameStudio.bat` | 遊戲商業化（建置中） |

---

## 第六層：核心鐵律來源

所有 L1 系統鐵律儲存於 DuckDB（透過 `add_core_directive` / `view_core_directives` 管理），並非實體 .md 檔案。`.alice/` 文件是鐵律的**補充說明**與**執行細節**，而非鐵律本身。
