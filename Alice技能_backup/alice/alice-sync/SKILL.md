---
name: alice-sync
description: Alice 跨電腦同步架構 — 一鍵安裝、記憶雙向同步、自動壓縮、GitHub 全倉庫同步。涵蓋 bootstrap、sync_memory_github.py v3、auto_compress_memory.py、cron 管理、.env 加密。
version: 1.0.0
---

# Alice Sync — 跨電腦同步架構

## 架構總覽

```
主機（這台）                       B端（另台）
─────────                         ─────────
每30分 push/pull（全倉庫）         每30分 push/pull + deploy scripts/skills
每天03:00 檢查記憶>80%             ❌ 不管壓縮
  → 濃縮 → 遞增版本號 → push        ↓ pull 偵測版本變更 → 整份覆蓋
                                   ↓ 平日逐條合併（只加不刪）
```

## 核心腳本

| 腳本 | 用途 | 觸發 |
|------|------|------|
| `scripts/sync_memory_github.py` | 全倉庫雙向同步 | cron 每30分 |
| `scripts/auto_compress_memory.py` | 記憶壓縮 | cron 每天03:00 |
| `bootstrap.bat` | 新電腦雙擊安裝器 | 手動 |
| `一鍵安裝.bat` | 完整安裝流程 | bootstrap 呼叫 |

## 新電腦部署

1. 下載 `bootstrap.bat`（純 ASCII，避開 curl 編碼問題）
2. 雙擊 → 自動 git clone → 跑一鍵安裝
3. 輸入解密密碼（0704）
4. 一鍵安裝自動完成：解密 .env、複製記憶到 alice+default、安裝 skills、設 alice 為預設 profile、偵測 Gateway 避免搶 TG
5. 打開桌面版 Hermes → 說「幫我重建記憶同步 cron」

## Cron 管理

⚠️ 強制規則：cron 必須用 cronjob 工具建立，**勿用 CLI**（CLI 不支援 `--no_agent`）。

| Cron | 排程 | 腳本 | 說明 |
|------|------|------|------|
| 記憶GitHub同步 | every 30m | `scripts/sync_memory_github.py` | 全倉庫 push/pull |
| 記憶自動壓縮 | 0 3 * * * | `scripts/auto_compress_memory.py` | >80% 濃縮 |
| 每日開源推薦 | 30 9 * * * | LLM prompt | 推播到 TG |

## Sync v3 策略

### Push（全倉庫 `git add -A`）
1. git pull 取得最新
2. 記憶逐條合併（§ 分隔，前80字指紋去重，取聯集）
3. git commit + push
4. 被拒時自動 `git pull --rebase` 重試

### Pull（部署 + 版本偵測）
1. git pull
2. 檢查 `memory/.version`：版本變更 → 整份覆蓋（主機壓縮過）
3. 否則逐條合併：只加入 GitHub 有但本地沒有的條目
4. 自動部署 `scripts/` 和 `hermes_skills/` 到 Hermes profile

## .env 加密

- 演算法：openssl aes-256-cbc -pbkdf2
- 密碼：互動輸入（非寫死）
- 加密檔：`.env.enc` 放 repo
- 解密時機：一鍵安裝 [3/6]

## 常見問題與修復

### Git push 被拒（non-fast-forward）
→ 腳本內建 rebase 重試

### 135MB 大檔誤入 repo
→ `.gitignore` 必須擋 `作業區/`、`temp_sync_workplace/`、`*_backup.py`、`.n8n/`
→ 修復：`git filter-branch --index-filter "git rm --cached --ignore-unmatch <file>"`

### Telegram 多台電腦搶線
→ 次要電腦：`hermes -p alice config set telegram.enabled false`
→ Gateway 裝背景服務：`hermes -p alice gateway install`（需 UAC）

### Cron 腳本找不到
→ 腳本必須放在 `profiles/alice/scripts/` 下
→ cron create 的 script 路徑相對於該目錄

### 桌面版開 default profile 而非 alice
→ `hermes profile use alice` 設為預設
→ 一鍵安裝會自動執行此步驟

### 記憶壓縮後 B 端膨脹
→ v3 版本號機制：壓縮遞增 `.version`，B 端偵測後整份覆蓋

### curl 下載 bat 編碼錯誤
→ 用純 ASCII 的 `bootstrap.bat` 當入口，避開 BOM/中文編碼
→ 或直接用 `git clone`

### batch 變數 `%VAR%` 被 secret redaction 遮蔽
→ 用 `write_file` 寫入時 redaction 不影響，只看 terminal 輸出時會顯示 `***`
→ 驗證用 `python -c "open(path,'rb').read()"` 檢查原始位元組

## 記憶上限

- 目前：3500 chars（`hermes -p alice config set memory.memory_char_limit 3500`）
- 壓縮閾值：80%（2800 chars）
- 壓縮後約 7 條，~2600 chars（74%）

## 參考

- `references/sync-scripts-reference.md` — 腳本完整原始碼與 Git 修復步驟
