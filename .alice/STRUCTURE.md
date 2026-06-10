# 📐 Alice 目錄結構總覽
> **最後更新**：2026-06-02 08:10

```
Alice 專案根目錄/
├── .alice/                          ← 🆕 系統知識中樞（本次新建）
│   ├── SYSTEM_MANIFEST.md           # 總表 / 導航
│   ├── STRUCTURE.md                 # 本文件
│   ├── FACTS.md                     # 核心事實（不可變更）
│   ├── TASK_BOARD.md                # 需求追蹤看板
│   ├── DECISIONS.md                 # 重大決策記錄
│   └── projects/
│       ├── investment_agent/        # 💰 投資代理人
│       │   ├── OVERVIEW.md
│       │   └── LOG.md
│       ├── alice_core/              # 🧠 Alice 核心系統
│       │   ├── OVERVIEW.md
│       │   └── LOG.md
│       └── gis_monitor/             # 🗺️ GIS 監控系統
│           ├── OVERVIEW.md
│           └── LOG.md
├── agent.py                         # Alice 主代理人
├── main.py                          # 主入口
├── handlers.py                      # Telegram 指令處理（⚠️ 不應包含投資功能）
├── ui_server.py                     # 投資代理人 Flask 後端
├── templates/
│   ├── dashboard.html               # 投資代理人儀表板
│   └── index.html
├── MEGA/                            # 兆豐 API 相關
│   └── SpeedyAPI_PY/                # SpeedyAPI Python 封裝
├── memory/                          # 記憶系統
├── skills/                          # 技能庫
├── engines/                         # AI 引擎
├── backups/                         # 自動備份
└── 作業區/                          # GIS 工作文件
```
