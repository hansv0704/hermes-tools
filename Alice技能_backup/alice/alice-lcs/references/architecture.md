# LCS v5.2 架構細節

## 核心檔案

| 檔案 | 用途 |
|:--|:--|
| `skills/live_code_studio_skill.py` | 907 行，HTTP API + watchdog + 自我診斷 |
| `skills/lcs_template_v5.html` | 38KB，雙 Tab 前端（Monaco Editor） |
| `run_studio.py` | 啟動腳本，支援 `--daemon` / `--stop` |
| `啟動LiveCodeStudio.bat` | 一鍵背景啟動（pythonw + 自動開瀏覽器） |
| `關閉LiveCodeStudio.bat` | 一鍵關閉（PID 查找 + taskkill） |

## API 完整列表

| 方法 | 路徑 | v5.0 | v5.2 |
|:--|:--|:--|:--|
| POST | `/api/session/start` | ✅ | ✅ + auto_workspace |
| POST | `/api/session/stop` | ✅ | ✅ |
| POST | `/api/files/track` | ✅ | ✅（可選） |
| POST | `/api/files/untrack` | ✅ | ✅ |
| POST | `/api/workspace/add` | ✅ | ✅ + 24hr 近期標記 |
| POST | `/api/workspace/remove` | ✅ | ✅ |
| POST | `/api/self_review` | ✅ | ✅ 優先掃追蹤檔案 |
| GET | `/api/tree` | ✅ 雙來源 | ✅ 雙來源 |
| GET | `/api/tracked` | ✅ | ✅ |
| GET | `/api/session/info` | ✅ | ✅ |
| GET | `/api/workspace/list` | ✅ | ✅ |
| GET | `/api/read/<path>` | ✅ | ✅ 記憶體優先 |
| GET | `/api/diff/<path>` | ✅ | ✅ |
| POST | `/api/save` | ✅ | ✅ |
| GET | `/api/repl_logs` | ✅ | ✅ |
| POST | `/api/repl_logs_push` | ✅ | ✅ |
| GET | `/api/clear_notify/<path>` | ✅ | ✅ |

## Watchdog 偵測類型

| 類型 | 觸發條件 | `_modified_files` 值 |
|:--|:--|:--|
| 新檔案 | `old_meta is None` | `"new_file"` |
| 內容變更 | `hash != old_hash` | `"modified"` |
| 語法錯誤 | `.py` compile 失敗 | `"syntax_error: Line N"` |
| 手動追蹤 | `/api/files/track` | `"tracked"` |
| 近期修改 | workspace scan 時 mtime < 24hr | `"recent_change"` |

## 安全限制

- **auto_workspace**：目錄 > 5000 檔案 → 跳過（回傳 `"skipped"`）
- **BASE_DIR watchdog**：永不移除，確保舊 Alice 目錄始終被監控
- **目錄黑名單**：`__pycache__`、`.git`、`node_modules`、`backups`、`data`、`logs` 等

## 前端 Tab 邏輯

- **📝 操作紀錄**：只顯示 `_tracked_files`（Hermes 手動追蹤的檔案），按時間倒序
- **📂 工作區**：顯示永久工作區列表 + 檔案樹（來自 `_file_metadata`），🕐 標記近期修改
- **Session 狀態條**：🟢/🔴 根據 `_session_active`，顯示 `_session_workdir`
- **通知鈴鐺**：根據 `_modified_files` 數量顯示紅點
