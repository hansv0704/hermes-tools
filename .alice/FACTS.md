# 📌 Alice 核心事實（不可變更）
> **最後更新**：2026-06-02 08:10
> ⚠️ 此文件中的事實擁有最高權威。若與記憶衝突，以此為準。

---

## 🏗️ 架構邊界（鐵律 #18）

### 投資代理人
- **身份**：獨立 Flask 伺服器（port 5002）
- **嚴禁**：整合進 Telegram / handlers.py
- **嚴禁**：在 handlers.py 中加入任何投資相關 Telegram 指令
- **UI**：儀表板 HTML（templates/dashboard.html）
- **後端**：ui_server.py（Flask API）
- **啟動**：`啟動投資代理人儀表板.bat`
- **相關檔案**：autonomous_investment_agent.py, mission_executor.py, mission_parser.py, strategy_engine.py, paper_trading_engine.py, live_trading_engine.py

### Alice 核心 / Telegram
- **handlers.py** 僅處理 Telegram 聊天指令
- **不應包含**：投資下單、股票查詢（這些歸投資代理人管）

---

## 🔑 系統資訊

| 項目 | 值 |
|:--|:--|
| 主人 Telegram ID | 8138000028 |
| 主人名稱 | 顥宇 |
| 主人職業 | GIS 專家 / 開發者 / 投資者 |
| 居住地 | 台南市仁德區 |
| 工作設備 | Windows, Python 3.13, VS Code |
| 專業軟體 | ArcMap, Google Earth Pro |

---

## 📂 關鍵路徑

| 用途 | 路徑 |
|:--|:--|
| Alice 專案根 | C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953 |
| GIS 專案 | C:\Users\hans\Desktop\大崩儀器DATA回傳 |
| GIS 核心 | monitor.py, sensor_config.json, 啟動監控.bat |
| 兆豐 API | MEGA/SpeedyAPI_PY/ |
| 投資儀表板 | templates/dashboard.html |

---

## 🔒 不可變更的設計決策

1. **投資代理人 ≠ Telegram**：兩個獨立系統，不耦合
2. **兆豐登入在頂層**：dashboard.html 中兆豐登入區塊在最上方
3. **紙上/實盤隔離**：紙上交易不影響真實帳戶
4. **GIS 監控獨立**：有自己的監控循環，不依賴 Alice
