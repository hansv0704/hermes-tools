"""
記憶自動壓縮腳本
每天凌晨 3 點檢查 MEMORY.md 用量，> 80% 自動濃縮
壓縮後遞增版本號，其他電腦 pull 偵測到版本變更會整份覆蓋
"""
import os
import sys
import re
import shutil
import subprocess
from pathlib import Path

USERPROFILE = Path(os.environ["USERPROFILE"])
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", USERPROFILE / "AppData" / "Local"))

MEMORY_FILE = LOCALAPPDATA / "hermes" / "profiles" / "alice" / "memories" / "MEMORY.md"
CHAR_LIMIT = 3500
THRESHOLD = 0.8

_raw_ws = os.environ.get("HERMES_WORKSPACE", "")
if _raw_ws:
    _raw_ws = re.sub(r'%([^%]+)%', lambda m: os.environ.get(m.group(1), m.group(0)), _raw_ws)
REPO_DIR = Path(_raw_ws) if _raw_ws else (USERPROFILE / "Desktop" / "Hermes工具區")


def compress():
    if not MEMORY_FILE.exists():
        return

    text = MEMORY_FILE.read_text(encoding="utf-8")
    entries = [e.strip() for e in text.split("§") if e.strip()]
    size = len(text)

    pct = size / CHAR_LIMIT
    if pct < THRESHOLD:
        return  # 沒超過 80%，安靜

    print(f"[!] 記憶用量 {pct:.0%} ({size}/{CHAR_LIMIT})，觸發壓縮")

    # 合併：同指紋（前 60 字）的條目只保留最長版
    seen = {}
    for entry in entries:
        key = entry[:60]
        if key in seen:
            if len(entry) > len(seen[key]):
                seen[key] = entry
        else:
            seen[key] = entry

    new_entries = list(seen.values())
    new_text = "\n§\n".join(new_entries) + "\n"
    new_size = len(new_text)
    new_pct = new_size / CHAR_LIMIT

    print(f"[OK] {len(entries)}→{len(new_entries)} 條，{size}→{new_size} chars ({pct:.0%}→{new_pct:.0%})")

    # 寫入本地
    MEMORY_FILE.write_text(new_text, encoding="utf-8")
    default_mem = LOCALAPPDATA / "hermes" / "memories" / "MEMORY.md"
    default_mem.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MEMORY_FILE, default_mem)

    # 同步到工作區
    if not REPO_DIR.exists():
        print(f"[X] Repo 不存在: {REPO_DIR}")
        return

    repo_mem = REPO_DIR / "memory" / "MEMORY.md"
    repo_mem.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MEMORY_FILE, repo_mem)

    # 遞增版本號（B 端偵測到版本變化 → 整份覆蓋）
    version_file = REPO_DIR / "memory" / ".version"
    try:
        ver = int(version_file.read_text().strip()) + 1
    except:
        ver = 1
    version_file.write_text(str(ver))

    # git push
    try:
        subprocess.run(["git", "add", "memory/"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m",
                        f"compress: {len(entries)}→{len(new_entries)}條 v{ver} ({new_pct:.0%})"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "push"],
                       cwd=str(REPO_DIR), capture_output=True, check=True, timeout=30)
        print(f"[OK] 已推送到 GitHub (v{ver})")
    except Exception as e:
        print(f"[X] Git 失敗: {e}")


if __name__ == "__main__":
    compress()
