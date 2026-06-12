---
name: alice-daily-briefing
description: Alice 每日自動化簡報 — GitHub Trending、技術新聞、市場摘要等定期研究報告的標準作業流程。以瀏覽器工具為主要資料來源，避免 cron 環境下的 execute_code / terminal HTTP 限制。
triggers:
  - "搜尋今日 GitHub 熱門"
  - "今日技術新聞"
  - "每日摘要"
  - "daily briefing"
  - 任何排程中的每日研究報告任務
---

# Alice 每日簡報工作流

本技能涵蓋 Alice 在 cron 排程下執行「每日研究報告」類任務的標準流程與避坑指南。核心場景為 GitHub Trending 搜尋，但模式可複用於其他需要從網頁提取結構化資訊的定期報告。

---

## 核心原則

### 1. 資料來源首選：browser 工具
在 cron 環境下，`execute_code` 被封鎖（需要使用者批准），`terminal` 的 curl + python 組合可能因 GitHub 反爬機制而 timeout。**直接使用 `browser_navigate` 存取目標頁面是最可靠的路徑。**

### 2. 第一頁即足夠
GitHub Trending 頁面透過 `browser_navigate` 初次載入即可取得 8-10 個 repo 的完整資訊（名稱、描述、語言、總星數、今日星數）。`browser_scroll` + `browser_snapshot` 反覆操作不僅效率低，且 snapshot 傾向截斷重複內容，不會有效擴展資料量。**不要浪費時間在滾動上。**

### 3. 質量勝於數量
報告挑選 **3-5 個**最值得關注的專案，按今日星數或總星數排序，附上：
- 倉庫名稱 + GitHub 連結
- 主要語言
- 總星數 + 今日新增星數
- 一句話描述 + Alice 視角的實用性評論
- 趨勢總結（關鍵字頻率表）

---

## 標準流程（GitHub Trending）

### Step 1: 導航
```
browser_navigate(url="https://github.com/trending")
```
初次載入的 snapshot 即包含所有必要欄位。不需要再呼叫 `browser_snapshot`。

### Step 2: 提取資料
從 snapshot 的 `<article>` 區塊中直接讀取：
- `heading` = repo 全名（owner / name）
- `paragraph` = 描述文字
- `StaticText "star N"` = 總星數
- `StaticText "N stars today"` = 今日新增星數
- `StaticText "<語言名>"` = 主要程式語言（通常緊鄰星數之前）

### Step 3: 篩選與排序
按 `stars today` 降冪排列，選取前 5 名。若有重複主題（如多個同類 agent-skills 專案），可適當替換為不同領域的專案以增加多樣性。

### Step 4: 格式化輸出
使用 Alice 秘書語氣（繁體中文）輸出：
- 每個專案使用 🥇🥈🥉🏅 排名圖示
- 格式：`owner / name` → 連結 → 語言 → 總星數 → 今日星數 → 描述 → Alice 評論
- 結尾附上趨勢關鍵字總結
- 主動詢問主人是否需要深入分析特定專案

---

## 避坑清單

| 陷阱 | 解法 |
|------|------|
| `execute_code` 在 cron 模式被封鎖 | 不要使用，直接用 browser 工具 |
| `terminal` curl + python 可能 timeout | GitHub 對非瀏覽器請求有嚴格限制，改用 browser |
| `browser_scroll` 後 snapshot 內容重複 | 初次載入就夠了，不要滾動 |
| `browser_console` JavaScript 語法錯誤 | snapshot 中的資料已結構化，直接解析 snapshot 即可 |
| 頁面要求登入才能 star | 不影響資料擷取，忽略 |

---

## 擴展場景

當任務非 GitHub Trending 而是其他定期報告（如 Hacker News 頭條、技術部落格摘要、市場快訊），遵循相同原則：
1. `browser_navigate` 直達目標頁面
2. 從 snapshot 提取結構化欄位
3. 篩選 3-5 個重點
4. Alice 風格繁體中文輸出
5. 結尾主動拋出下一步建議

---

## 交付範本

```
## 📊 [主題] — YYYY.MM.DD

[主人名]，[時間問候]。簡述今日趨勢主題...

### 🥇 No.1 — `owner / repo`
> 🔗 https://github.com/owner/repo
> [語言] ｜ ⭐ [總星數] ｜ 🔥 今日 +[N] stars

[描述]。Alice 評論...

[重複 x3-5]

### 📌 今日趨勢總結
| 關鍵字 | 熱度 |
|--------|------|
| ... | 🔥🔥🔥 |

---

有什麼想深入看的專案嗎？[主動建議下一步]
```
