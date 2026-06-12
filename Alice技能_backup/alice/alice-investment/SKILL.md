---
name: alice-investment
description: "投資代理人互動 — 與獨立的投資代理人 Flask 伺服器 (port 5002) 通訊。啟動/停止自主投資循環、查詢狀態、下單操作。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, investment, trading, stock, autonomous]
    source: "移植自 Alice Bot 投資子系統"
---

# 投資代理人互動

## ⚠️ 強制規則：主人要求查詢投資狀態時，你必須實際執行 curl 命令查詢 API。禁止憑記憶回答。下單操作需主人明確授權。

主人的投資代理人是一個獨立的 Flask 伺服器（port 5002）。

## ⚠️ 鐵律

1. **投資代理人是獨立系統**（port 5002），不整合進 Telegram
2. **紙上/實盤隔離**：paper trading 不影響真實帳戶
3. **下單操作需主人明確授權**

## 觸發條件

- 主人要求啟動/停止自主投資循環
- 主人查詢投資狀態、持倉
- 主人要求執行投資策略分析
- 主人要求切換紙上/實盤模式

## 可用操作

### 啟動投資代理人儀表板

```bash
# 如果尚未運行，啟動儀表板
start "" "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\啟動投資代理人儀表板.bat"
```

### 啟動自主 AI 投資循環

```bash
curl -X POST http://localhost:5002/api/ai/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "paper", "budget": 100000}'
```

### 停止自主投資循環

```bash
curl -X POST http://localhost:5002/api/ai/stop
```

### 查詢投資狀態

```bash
curl -s http://localhost:5002/api/ai/status | python -m json.tool
```

### 查詢持倉

```bash
curl -s http://localhost:5002/api/portfolio | python -m json.tool
```

### AI 策略討論

```bash
curl -X POST http://localhost:5002/api/ai/discuss \
  -H "Content-Type: application/json" \
  -d '{"query": "分析台積電2330目前的投資價值"}'
```

### 取得 AI 交易工具箱列表

```bash
curl -s http://localhost:5002/api/ai/toolkit | python -m json.tool
```

## 儀表板 API 端點

| 端點 | 方法 | 說明 |
|:--|:--|:--|
| `/api/ai/start` | POST | 啟動自主投資 |
| `/api/ai/stop` | POST | 停止自主投資 |
| `/api/ai/status` | GET | 投資狀態 |
| `/api/ai/discuss` | POST | AI 策略討論 |
| `/api/ai/toolkit` | GET | 交易工具箱 |
| `/api/portfolio` | GET | 持倉查詢 |
| `/api/mega/*` | * | 兆豐券商操作 |

## 自主投資循環架構

每 60 分鐘循環：
1. 新聞監控 → 抓取即時財經新聞
2. 題材變化分析 → LLM 分析新題材
3. 持倉風險評估 → 比對現有持倉
4. 策略調整建議 → LLM 產出方案
5. Telegram 推播 → 重要事件通知

## 設定 Cron 定時監控

可選：使用 Hermes cron 取代 autonomous_loop.py 的內部循環：

```bash
hermes cron create "every 60m" \
  --prompt "查詢投資狀態，分析持倉風險，若有異常通知主人" \
  --skills alice-investment,alice-taiwan-market \
  --deliver telegram
```

## 相關檔案

- 儀表板：`templates/dashboard.html`
- 後端：`ui_server.py` (115KB)
- 投資引擎：`autonomous_investment_agent.py`, `strategy_engine.py`
- 交易引擎：`paper_trading_engine.py`, `live_trading_engine.py`
- 任務系統：`mission_executor.py`, `mission_parser.py`
- AI 工具箱：`ai_trading_toolkit.py`
