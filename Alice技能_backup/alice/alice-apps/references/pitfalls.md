# 多端點同步 — 實戰教訓集

本文件記錄在實際部署多電腦同步時踩過的坑和解決方案。

## 同步媒介演進

| 版本 | 媒介 | 問題 |
|------|------|------|
| v1 錯誤 | MEGA.nz 雲端 | 搞錯了 — MEGA 是兆豐證券縮寫，不是雲端硬碟 |
| v2 錯誤 | MEGA 本機目錄 | 路徑寫死 `C:\Users\hans`，換電腦失效 |
| v3 正確 | GitHub + openssl 加密 | 公開 repo 安全，純 ASCII bootstrap.bat 雙擊安裝 |

## batch 檔案編碼陷阱

- **curl 下載** → 編碼破壞（BOM、換行符號）
- **GitHub zip** → 換行符號破壞（`0` `it` `else` 等被解析為命令）
- **解法**：只放一個純 ASCII 的 `bootstrap.bat`，內容僅 `git clone` + `call 一鍵安裝.bat`
- **驗證**：用 `python -c` + `rb` 讀取原始位元組，terminal 會被 secret redaction 遮蔽

## Gateway 管理

### 桌面版內建 Gateway vs 獨立 Gateway

桌面版 Hermes 內建 Gateway，關閉桌面版 = Gateway 一起死。解決：
```bash
hermes -p alice gateway install   # 背景服務，開機自動跑
```

### Gateway install 互動提示

需回答 3 個問題：
```bash
printf "N\nY\nY\n" | hermes -p alice gateway install
# N = 不立即啟動（已經在跑）
# Y = 裝 Windows Scheduled Task
# Y = 允許 UAC（會跳出管理員確認視窗）
```

### 多電腦 TG 搶線

兩台以上電腦同時開桌面版 → 多個內建 Gateway 搶同一個 TG Bot → 誰都收不到。

**解法**：次要電腦關閉 TG：
```bash
hermes -p alice config set telegram.enabled false
```

### TG polling conflict 錯誤

```
Conflict: terminated by other getUpdates request
```
表示有多個 Gateway 在搶。檢查：`hermes -p alice gateway status`，確保只有一個 PID。

### DeepSeek credit 用完

TG 回應：`provider failed after retries`
Log 關鍵字：`payment / credit error`
暫時解法：`hermes -p alice gateway restart`
根本解法：充值 DeepSeek API

## pip 依賴衝突

`protobuf==6.33.6` + `google-ai-generativelanguage==0.6.15`：
```
The user requested protobuf==6.33.6
google-ai-generativelanguage 0.6.15 depends on protobuf <6.0.0 and >=3.20.2
```
解法：`protobuf>=3.20.2,<6.0.0`

## memory 同步 — pull 覆蓋陷阱（v3 已修）

**v2 致命缺陷**：`pull()` 無條件用 GitHub 覆蓋本地，不檢查哪邊比較新。
- 症狀：本地新增的記憶被 GitHub 舊版蓋掉
- 證據：MEMORY.md 被還原到舊時間戳

**v3 解法**：逐條 §-合併
- push 先 `git pull` → 解析 § 條目 → union merge（取聯集）→ `git push`
- pull 只拉 GitHub 有但本地沒有的新條目，不覆蓋既有
- 兩台電腦各自改記憶，互不衝突

## 一鍵安裝 — Gateway 衝突偵測

新電腦安裝時可能已有一台主電腦在跑 Gateway。一鍵安裝最後會自動檢查：
```bat
hermes -p alice gateway status | findstr "running"
if errorlevel neq 0 ( install + run ) else ( skip )
```
避免多台電腦搶同一個 TG Bot。

## secret redaction 驗證技巧

`read_file` / `patch` / terminal 輸出都會被遮蔽。驗證 batch 變數正確性：
```python
python -c "
with open(path, 'rb') as f:
    raw = f.read()
print(b'%TG_TOKEN%' in raw)  # True = 正確，False = 被寫死成 ***
"
```

## cron job CLI vs 內部工具

- `hermes cron create` CLI **不支援 `--no_agent`**（僅 cronjob 內部工具有）
- cron 一律由 Alice 在對話中用 `cronjob(action='create', ...)` 建立
- `--deliver local` + `no_agent=true` + stdout 有輸出 = 訊息發送；無輸出 = 安靜

## 記憶壓縮自動化

### 動機

隨著對話累積，記憶條目會膨脹超過 `memory_char_limit`（預設 2200 → 調至 3500），導致新條目無法寫入。

### 腳本：`scripts/auto_compress_memory.py`

每天凌晨 3:00 cron 執行（主電腦專屬，其他電腦不管）：
- 讀取 MEMORY.md，計算 char 用量百分比
- 若 > 80%（> 2800 chars）→ 合併重複條目（前 60 字指紋相同 → 保留較長版）
- 寫入本地 + sync default profile + git push
- 若 < 80% → 安靜 skip（無輸出 = cron 不推通知）

### 建立方式

Alice 對話中用 cronjob 工具：
```
schedule: 0 3 * * *
script: scripts/auto_compress_memory.py
no_agent: true
deliver: local
profile: alice
```

### 記憶上限調整

```bash
hermes -p alice config set memory.memory_char_limit 3500
```

## bootstrap.bat 雙擊安裝\n\n純 ASCII 的 bootstrap 腳本，內容僅 `git clone/pull` + `call 一鍵安裝.bat`。放在 GitHub repo 根目錄。\n\n新電腦最安全方式：**瀏覽器打開 raw URL → 右鍵另存新檔 → 雙擊**（不要用 curl，不要用 zip）。\n\n## `echo ... >> .env` 路徑反斜線陷阱\n\nWindows batch 中用 `echo VAR=C:\\path\\to\\dir>> .env` 追加環境變數時，反斜線會被當作跳脫字元吃掉，變成 `C:pathtodir`。\n\n解法：用 Python 寫入 `.env`，不要用 batch 的 `echo ... >>`。或用 `%%USERPROFILE%%` 變數在 runtime 展開。
