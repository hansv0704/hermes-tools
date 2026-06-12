## `git add -A` 大檔案災難與復原

### 災難情境
全倉庫同步 (`git add -A`) 吞入 135MB docx（`作業區/`），超過 GitHub 100MB 限制。**所有 push 被擋死**，cron 持續 error。另一台電腦的 sync 也在中間時段 push 了這個檔案。

### 偵測
```bash
git push --dry-run 2>&1 | grep "larger than"
# GH001: Large files detected. File ...docx is 135.92 MB
```

### 切除步驟
1. 加 `.gitignore`：`作業區/`、`*.docx`、`~$*.xlsx`、`temp_sync_workplace/`
2. `git rm -r --cached "作業區"`
3. 從歷史徹底切除（`filter-branch`，不是 `rm`）：
```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch '作業區/115年度*.docx'" \
  --prune-empty origin/main..HEAD
```
4. `git push --force-with-lease`

### 預防
`.gitignore` 必須明確排除大檔案目錄和暫存檔。cron 執行 sync 前確保 `.gitignore` 是最新的。`git add -A` 會吞入任何未 ignore 的檔案，沒有第二次機會。
