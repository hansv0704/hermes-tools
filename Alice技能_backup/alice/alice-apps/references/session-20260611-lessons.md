# 2026-06-11 Session Lessons

## 135MB docx 卡死全倉庫

B端 `git add -A` 吞入 `作業區/115年度...docx` (135MB)，超過 GitHub 100MB 限制，所有 push 被拒。

**切除步驟**：
```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch '作業區/115年度*.docx'" \
  --prune-empty e8fe613..HEAD
git push --force-with-lease
```

**預防**：`.gitignore` 加 `作業區/`、`*.docx`、`~$*.xlsx`

## .env 路徑反斜線消失

`echo HERMES_WORKSPACE=C:\Users\hans\Desktop\... >> .env` → 寫入變成 `C:UsershansDesktop...`。解法：Python `write_text()` 寫入。

## Cron 全面 error 根因

三個 cron (`69de7a924edc`, `2304e7f763ff`, `79afff73d2e5`) 持續 error。根因：(1) large file reject 卡死 push；(2) `HERMES_WORKSPACE` 路徑損壞；(3) script 名稱不匹配 (`sync_memory_push.py` 不存在)

## Hermes v3 五崩潰路徑

1. DEP 擊殺 (Defender 排除)
2. os.execvpe Segfault (Windows 用 subprocess.Popen + sys.exit)
3. profile re-exec 死循環
4. --replace 陷阱
5. 桌面版 vs CLI profile 獨立 (active-profile.json)

一鍵安裝若執行 `profile use alice` 必須同步建立 `%APPDATA%/Hermes/active-profile.json`

## Git 衝突策略

push 被拒 → `git stash` → `git pull --rebase` → `git stash pop` → commit → push。sync 腳本內建此邏輯。
