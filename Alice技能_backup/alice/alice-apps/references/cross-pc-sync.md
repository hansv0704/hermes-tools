# 跨電腦同步架構（GitHub + 加密）

## 架構總覽

```
電腦A（主要）                      GitHub                       電腦B（次要）
──────────                       ──────                       ──────────
memories/                        hermes-tools/                memories/
  USER.md   ──cron/30min──→       memory/        ──git pull──→  USER.md
  MEMORY.md ←────────────────     ├── USER.md   （手動或 cron） MEMORY.md
              git pull            └── MEMORY.md
                                  
.env                              .env.enc                     .env
  ──openssl enc──→                （aes-256-cbc, 密碼0704）     ←──openssl dec──
```

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `.env.enc` | openssl aes-256-cbc 加密的 API keys，密碼 0704 |
| `memory/USER.md` | Hermes user profile 備份 |
| `memory/MEMORY.md` | Hermes memory entries 備份 |
| `scripts/sync_memory_github.py` | 比對 memories/ → repo memory/ → git push |
| `一鍵安裝.bat` | 6 步驟全自動部署 |

## sync_memory_github.py 邏輯

```
push 模式（cron 用）：
  1. 讀取 profiles/alice/memories/{USER,MEMORY}.md
  2. 比較 repo memory/ 目錄
  3. 有差異 → 複製到 repo → git add → git commit → git push
  4. 無差異 → 安靜退出（stdout 空 = cron 不發通知）

pull 模式（另一台電腦手動）：
  1. git pull
  2. 複製 repo memory/ → profiles/alice/memories/ + default memories/
```

## 新電腦部署

```bash
git clone https://github.com/hansv0704/hermes-tools.git "%USERPROFILE%\Desktop\Hermes工具區"
cd /d "%USERPROFILE%\Desktop\Hermes工具區"
一鍵安裝.bat
# 輸入解密密碼: 0704
```

> ⚠️ 不要用 `curl -o setup.bat` — Windows cmd 對 BOM/編碼敏感，容易解析錯誤。用 `git clone` 最可靠。

自動完成（6 步驟）：
1. 檢查 Python/Git/Hermes
2. pip install 依賴（從 requirements.txt）
3. **互動輸入密碼 0704** → openssl 解密 .env.enc → .env
4. 複製 memory/ → alice + default memories/
5. 安裝 skills
6. `hermes profile use alice` 設為預設 → Gateway 背景服務啟動

### 安裝後

打開桌面版 Hermes，對 Alice 說「幫我建立記憶同步 cron」。
cron 由 Alice 用 cronjob 工具建立（`hermes cron create` CLI 不支援 `--no_agent` 參數，無法從 .bat 建立）。

## Gateway 背景服務

```bash
# 安裝（開機自動啟動）
echo Y | hermes -p alice gateway install

# 狀態檢查
hermes -p alice gateway status
```

⚠️ 桌面版關閉時內建 Gateway 也會停止。必須用 `gateway install` 裝背景服務才能 24 小時 TG 在線。

## Hermes Memory 關鍵發現

- Memory 不是 SQLite，是 `memories/` 目錄下的 `USER.md` 和 `MEMORY.md` 純文字檔
- `§` 字元分隔多個條目
- Profile 獨立：`profiles/alice/memories/` vs `memories/`（default）
- 使用者務必用 `hermes -p alice`，否則會讀到空的 default profile

## 加密/解密 .env

```bash
# 加密
openssl enc -aes-256-cbc -pbkdf2 -pass pass:0704 -in .env -out .env.enc

# 解密
openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:0704 -in .env.enc -out .env
```

Git for Windows 自帶 openssl（`C:\Program Files\Git\usr\bin\openssl.exe`）

## 使用注意

- Git push 需要 credential helper（`git config --global credential.helper manager-core`）
- 一鍵安裝自動設 alice 為預設 profile，桌面版打開就是 Alice，**不需要手動 `hermes -p alice`**
- `HERMES_WORKSPACE` 環境變數由一鍵安裝自動寫入 .env
- **「MEGA」= 兆豐證券**，不是雲端硬碟。跨電腦同步媒介是 GitHub。
- cron 必須由 Alice 在對話中建立（`hermes cron create` CLI 不支援 `--no_agent`，一鍵安裝中的 CLI 呼叫會失敗）
- protobuf 版本衝突：`protobuf>=3.20.2,<6.0.0`（`google-ai-generativelanguage` 不支援 6.x）
- cmd 對 batch 檔案的 BOM 敏感，curl 下載可能引入編碼問題 → 用 git clone
