"""
記憶自動壓縮腳本
每 2 小時檢查 MEMORY.md 用量，> 80% 自動濃縮
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

USERPROFILE = Path(os.environ["USERPROFILE"])
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", USERPROFILE / "AppData" / "Local"))

MEMORY_FILE = LOCALAPPDATA / "hermes" / "profiles" / "alice" / "memories" / "MEMORY.md"
CHAR_LIMIT = 3500
THRESHOLD = 0.8  # 80%

REPO_DIR = Path(os.environ.get("HERMES_WORKSPACE",
    USERPROFILE / "Desktop" / "Hermes工具區"))


def compress():
    if not MEMORY_FILE.exists():
        return

    text = MEMORY_FILE.read_text(encoding="utf-8")
    entries = [e.strip() for e in text.split("§") if e.strip()]
    size = len(text)

    # 計算用量
    pct = size / CHAR_LIMIT
    if pct < THRESHOLD:
        # 安靜：沒超過 80%
        return

    print(f"[!] 記憶用量 {pct:.0%} ({size}/{CHAR_LIMIT})，觸發壓縮")

    # 合併策略：找重複指紋（前 60 字相同）的條目
    seen = {}
    merged = []
    for entry in entries:
        key = entry[:60]
        if key in seen:
            # 合併：保留較長的版本
            existing = seen[key]
            if len(entry) > len(existing):
                seen[key] = entry
        else:
            seen[key] = entry

    new_entries = list(seen.values())
    new_text = "\n§\n".join(new_entries) + "\n"
    new_size = len(new_text)
    new_pct = new_size / CHAR_LIMIT

    print(f"[OK] 壓縮完成：{len(entries)}→{len(new_entries)} 條，{size}→{new_size} chars ({pct:.0%}→{new_pct:.0%})")

    # 寫入本地
    MEMORY_FILE.write_text(new_text, encoding="utf-8")
    default_mem = LOCALAPPDATA / "hermes" / "memories" / "MEMORY.md"
    default_mem.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MEMORY_FILE, default_mem)

    # 同步到工作區並 push
    if REPO_DIR.exists():
        repo_mem = REPO_DIR / "memory" / "MEMORY.md"
        repo_mem.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MEMORY_FILE, repo_mem)
        try:
            subprocess.run(["git", "add", "memory/"],
                           cwd=str(REPO_DIR), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m",
                            f"compress: auto {len(entries)}→{len(new_entries)}條({new_pct:.0%})"],
                           cwd=str(REPO_DIR), capture_output=True, check=True)
            subprocess.run(["git", "push"],
                           cwd=str(REPO_DIR), capture_output=True, check=True, timeout=30)
            print("[OK] 已推送到 GitHub")
        except Exception as e:
            print(f"[X] Git 失敗: {e}")


if __name__ == "__main__":
    compress()
