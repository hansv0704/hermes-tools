# 📋 Alice 需求追蹤看板
> **最後更新**：2026-06-09 11:07
> **用途**：可視化各專案開發進度。AI 讀取時應基於語意判斷需要哪個專案段落，不再使用關鍵詞匹配。

---

## 💰 投資代理人

| # | 需求 | 狀態 | 優先級 | 對應 LOG | 備註 |
|:--|:--|:--|:--|:--|:--|
| 1 | Step 1：投資金額輸入框 | ✅ 完成 | P0 | 2026-06-02 凌晨 | |
| 2 | 步驟鎖定機制（Step 2/3 解鎖） | ✅ 完成 | P0 | 同上 | |
| 3 | Step 2：AI 策略討論 → 搜尋標的 | ✅ 完成 | P0 | 同上 | 移除下拉選單 |
| 4 | Step 3：懸浮說明 | ✅ 完成 | P1 | 同上 | |
| 5 | 後端資金對接（budget 參數） | ✅ 完成 | P0 | 同上 | |
| 6 | 兆豐登入移至最頂層 | ✅ 完成 | P0 | 同上 | |
| 7 | 持股收益 TAB 面板 | ✅ 完成 | P1 | 同上 | |
| 8 | 任務管理 TAB | 🔧 進行中 | P1 | | |
| 9 | AI 自主投資循環（真實下單） | ⬜ 待開發 | P0 | | 目前紙上交易 |
| 10 | 24/7 背景掃描 | ⬜ 待開發 | P2 | | |
| 11 | 即時風險監控面板 | ⬜ 待開發 | P2 | | |
| 12 | 策略績效回測功能 | ⬜ 待開發 | P3 | | |
| 13 | LLM Provider 橋接（call_llm → DeepSeek API） | ✅ 完成 | P0 | 2026-06-02 12:10 | Phase 1 辯論引擎 + Phase 2 動態映射可用 |
| 14 | Phase 2 Web 搜尋層（DuckDuckGo Lite 概念股網搜） | ✅ 完成 | P0 | 2026-06-02 13:48 | 快取→網搜→LLM 三層策略，大幅加速題材映射 |
| 15 | 兆豐 DLL 18 方法全線貫通（Skill→API→UI 三層補齊） | ✅ 完成 | P0 | 2026-06-02 17:18 | Phase 1 Skill + Phase 2 API + Phase 3 UI，四層全覆蓋 |
| 16 | Phase 4 Step 1：證券交易操作 UI（下單/刪單/委託/成交） | ✅ 完成 | P0 | 2026-06-08 11:50 | dashboard.html 補齊證券操作閉環面板 + 5 JS 函數 |
| 17 | Phase 4 Step 2：行情即時訂閱（即時報價面板） | ✅ 完成 | P1 | 2026-06-08 12:45 | MegaSpeedyQuoteSession: Subscribe/Unsubscribe/OnOrderBook/OnTrade + ui_server SSE 5 端點 + dashboard 即時五檔面板 |
| 18 | Phase 4 Step 3 / Phase A：AI 交易工具層（AITradingToolkit 雙模式 + AutonomousLoop 真實下單） | ✅ 完成 | P0 | 2026-06-08 12:06 | 新建 ai_trading_toolkit.py (6 工具) + 修改 autonomous_loop._handle_adjustment + ui_server.py 新增 8 條 /api/ai/toolkit/* 路由 |
| 19 | Phase B：UI 重新設計 — 四象限交易終端佈局（左資產+持股 / 中圖表+流程 / 右下單+狀態 / 底部決策日誌） | ✅ 完成 | P1 | 2026-06-08 12:30 | dashboard.html 從垂直堆疊重構為 CSS Grid 四象限 + 底部欄，保留所有 JS 函數，精簡 CSS/HTML |
| 20 | Phase 5：啟用自主 AI 投資 — 頂部一鍵啟動/停止按鈕（無需三步驟） | ✅ 完成 | P0 | 2026-06-08 12:57 | dashboard.html topbar 新增 ▶️啟動/⏹️停止按鈕 + aiStartDirect/aiStopDirect JS 函數，保留紙上/實盤切換 |

---

## 🧠 Alice 核心

| # | 需求 | 狀態 | 優先級 | 對應 LOG | 備註 |
|:--|:--|:--|:--|:--|:--|
| 1 | `.alice/` 系統知識中樞 | ✅ 完成 | P0 | 2026-06-02 08:17 | |
| 2 | 行動前讀取 `.alice/` 機制 | ✅ 完成 | P0 | 同上 | ⚠️ 已從關鍵詞匹配改為 AI 語意路由 |
| 3 | 記憶系統優化（分層隔離向量記憶） | ✅ 完成 | P2 | 2026-06-06 00:52 | 純Embedding隔離設計，永不觸發LLM循環 |
| 4 | Phase 4 需求備忘錄改造 | ✅ 完成 | P1 | 2026-06-02 15:32 | 簡化為讀取 REQUIREMENTS.md → 顯示核心需求 |
| 5 | 核心記憶與 `.alice/` 文件一致性校驗 | ⬜ 待規劃 | P1 | | |
| 6 | `.alice/` 架構重構（廢除關鍵詞匹配） | ✅ 完成 | P0 | 2026-06-02 10:18 | 改為 AI 語意路由 + ARCHITECTURE.md + ADSP 日誌同步 |
| 7 | Skill 自動生成閉環（經驗追蹤 + 自動建議） | ✅ 完成 | P0 | 2026-06-07 02:45 | 第1步完成：brain_orchestrator_skill.py 補完 record_skill_experience + 原子寫入 |
| 8 | Background Self-Review（Fork 子 Agent 審查記憶+技能質量） | ✅ 完成 | P0 | 2026-06-07 03:15 | 第2步完成：self_review_skill.py + agent.py 觸發機制 |
| 9 | Memory Evolution Engine（記憶評分/淘汰/摘要進化） | ✅ 完成 | P1 | 2026-06-07 03:30 | 第3步完成：價值型記憶管理（評分/衰減/淘汰/摘要閉環） |
| 10 | Gmail IMAP 讀取 Skill（gmail_skill.py） | ✅ 完成 | P1 | 2026-06-08 22:33 | 讀取收件匣/搜尋郵件/讀取郵件內容，IMAP + App Password 永久免 OAuth |
| 11 | DeepSeek 視覺橋接 Skill（deepseek_vision_bridge_skill.py） | 🔧 進行中 | P0 | | 截圖→Gemini Vision 分析→回傳 UI 座標，解決 DeepSeek 無視覺能力的限制 |
| 12 | Playwright CDP 瀏覽器獨立操控管道（playwright_browser_skill.py） | 🔧 進行中 | P0 | | 全新獨立操控方式：Chrome CDP 直連 + Playwright API，100% DOM 精準定位，廢除 Vision 座標猜測。邊界檢查：獨立 Skill 不整合現有 gis_skill，不影響 investment_agent，不修改 .bat 啟動流程 |

---

## 🗺️ GIS 監控

| # | 需求 | 狀態 | 優先級 | 對應 LOG | 備註 |
|:--|:--|:--|:--|:--|:--|
| 1 | 監控循環穩定運行 | ✅ 運行中 | P0 | | |
| 2 | 警報推播 | ✅ 運行中 | P0 | | |
| 3 | 巡檢回報表單自動填寫 Skill | ✅ 完成 | P0 | 2026-06-09 12:54 | v4.0：vision座標模式(預設/推薦) + keyboard改良 + CDP。根治v3.2死偏移量漏勾 |

---

## 🎮 遊戲開發 (GameStudio)

| # | 需求 | 狀態 | 優先級 | 對應 LOG | 備註 |
|:--|:--|:--|:--|:--|:--|
| 1 | 遊戲商業化計畫 | ⬜ 待展開 | P3 | | |

---

**狀態圖例**：✅ 完成 | 🔧 進行中 | ⬜ 待開發 | ⏸️ 暫停
**優先級**：P0=緊急/核心 | P1=重要 | P2=一般 | P3=低優先
