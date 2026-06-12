# Sync Scripts Reference

## sync_memory_github.py v3 — 關鍵邏輯

### 版本偵測（pull 入口）
```python
# 檢查 memory/.version：主機壓縮過 → 整份覆蓋
remote_ver_file = REPO_MEM_DIR / ".version"
local_ver_file = HERMES_MEM_DIR / ".version"
if remote_ver_file.exists():
    remote_ver = int(remote_ver_file.read_text().strip())
    local_ver = int(local_ver_file.read_text().strip()) if local_ver_file.exists() else 0
    if remote_ver > local_ver:
        # 整份覆蓋 USER.md + MEMORY.md
```

### Push 被拒重試
```python
def try_push():
    subprocess.run(["git", "add", "-A"], ...)
    subprocess.run(["git", "commit", ...])
    subprocess.run(["git", "push"], ...)

try:
    try_push()
except subprocess.CalledProcessError:
    subprocess.run(["git", "pull", "--rebase"], ...)
    try_push()  # 重試
```

### 逐條合併（§ 分隔）
```python
def _parse_entries(path):
    return [p.strip() for p in path.read_text().split("§") if p.strip()]

def _merge_entries(local, remote):
    seen = set()
    merged = []
    for e in local + remote:
        key = e[:80]  # 前80字當指紋
        if key not in seen:
            seen.add(key)
            merged.append(e)
    return merged
```

## auto_compress_memory.py — 關鍵邏輯

### 壓縮觸發
- 檢查 MEMORY.md char 長度
- >80% of CHAR_LIMIT (3500) → 觸發
- 合併同指紋（前60字）的條目，保留最長版
- 遞增 `memory/.version`
- git commit message: `compress: N→M條 v{ver} (X%)`

## Git 修復步驟（135MB 大檔）

```bash
# 診斷
git log --oneline -- "作業區/115年度*.docx"

# 切除
git filter-branch --force \
  --index-filter "git rm --cached --ignore-unmatch '作業區/115年度*.docx'" \
  --prune-empty <base_commit>..HEAD

# 推送
git push --force-with-lease
```

## .env 加密/解密

```bash
# 加密（主機執行一次）
openssl enc -aes-256-cbc -pbkdf2 -pass pass:0704 -in .env -out .env.enc

# 解密（一鍵安裝中使用，密碼互動輸入）
openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:%PASSWORD% -in .env.enc -out .env
```
