# 💰 投資代理人 — 專案總覽
> **最後更新**：2026-06-02 08:10

## 🎯 專案目標
建立一個獨立於 Telegram 的 AI 自主投資機器人，具備：
- 任務設定 → 策略討論 → AI 研究 → 自主下單 → 績效追蹤
- 24/7 背景掃描
- 兆豐 API 實盤交易
- 紙上/實盤雙軌運行

## 🏗️ 架構
- **類型**：獨立 Flask 伺服器（port 5002）
- **啟動**：`啟動投資代理人儀表板.bat`
- **⚠️ 嚴禁**：整合進 Telegram / handlers.py

## 📂 核心檔案

| 檔案 | 用途 |
|:--|:--|
| `ui_server.py` | Flask 後端 API + 頁面路由 |
| `templates/dashboard.html` | 單頁化操作介面（747行/47K） |
| `autonomous_investment_agent.py` | DeepSeek 驅動投資決策 |
| `mission_executor.py` | 任務執行器 |
| `mission_parser.py` | 自然語言任務解析 |
| `strategy_engine.py` | 策略評分引擎 |
| `paper_trading_engine.py` | 紙上交易模擬 |
| `live_trading_engine.py` | 實盤交易引擎 |
| `MEGA/SpeedyAPI_PY/` | 兆豐 API |

## 🔑 關鍵設計決策
1. 兆豐登入區塊在 dashboard.html 最頂層
2. Step 1→2→3 依序解鎖
3. Step 2 不用下拉選單，而是 AI 策略討論
4. 投資金額從 Step 1 輸入框取得
