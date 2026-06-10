"""
記憶 → GitHub 自動同步腳本
比較本地 Hermes memories 與 repo memory/ 目錄，有變更就 push

模式：
  python sync_memory_github.py push   → 本地 → GitHub
  python sync_memory_github.py pull   → GitHub → 本地（另一台電腦用）
  python sync_memory_github.py        → 預設 push（cron 用）
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

USERPROFILE = Path(os.environ["USERPROFILE"])
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", USERPROFILE / "AppData" / "Local"))

# Hermes memories
HERMES_MEM_DIR = LOCALAPPDATA / "hermes" / "profiles" / "alice" / "memories"
HERMES_DEFAULT_MEM_DIR = LOCALAPPDATA / "hermes" / "memories"

# Repo memory 目錄（相對於腳本位置或環境變數）
REPO_DIR = Path(os.environ.get("HERMES_WORKSPACE",
    USERPROFILE / "Desktop" / "Hermes工具區"))
REPO_MEM_DIR = REPO_DIR / "memory"

FILES = ["USER.md", "MEMORY.md"]


def _files_differ(f1: Path, f2: Path) -> bool:
    if not f1.exists() or not f2.exists():
        return True
    return f1.read_bytes() != f2.read_bytes()


def push():
    """本地記憶 → GitHub repo"""
    if not REPO_DIR.exists():
        print(f"[X] Repo 不存在: {REPO_DIR}")
        return False

    changed = False
    REPO_MEM_DIR.mkdir(parents=True, exist_ok=True)

    for fname in FILES:
        src = HERMES_MEM_DIR / fname
        dst = REPO_MEM_DIR / fname
        if src.exists() and _files_differ(src, dst):
            shutil.copy2(src, dst)
            print(f"[OK] 已複製: {fname}")
            changed = True

    if not changed:
        # 沒變化 → 安靜
        return True

    # git add + commit + push
    try:
        subprocess.run(["git", "add", "memory/"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m",
                        f"sync: 記憶自動同步 {__import__('datetime').datetime.now().strftime('%m/%d %H:%M')}"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "push"],
                       cwd=str(REPO_DIR), capture_output=True, check=True, timeout=30)
        print("[OK] 已推送到 GitHub")
    except subprocess.CalledProcessError as e:
        print(f"[X] Git 失敗: {e.stderr.decode() if e.stderr else e}")
        return False
    except subprocess.TimeoutExpired:
        print("[X] Git push 逾時")
        return False

    return True


def pull():
    """GitHub repo → 本地記憶（只在 GitHub 較新時才覆蓋）"""
    # 先 git pull
    try:
        result = subprocess.run(["git", "pull"],
                                cwd=str(REPO_DIR), capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"[X] Git pull 失敗: {e}")
        return False

    # 複製 repo memory → Hermes（只在 GitHub 較新時）
    HERMES_MEM_DIR.mkdir(parents=True, exist_ok=True)
    HERMES_DEFAULT_MEM_DIR.mkdir(parents=True, exist_ok=True)
    pulled = False

    for fname in FILES:
        src = REPO_MEM_DIR / fname
        dst = HERMES_MEM_DIR / fname
        if src.exists():
            # 只在 GitHub 版本比本地新時才覆蓋
            if _files_differ(src, dst):
                src_mtime = src.stat().st_mtime if src.exists() else 0
                dst_mtime = dst.stat().st_mtime if dst.exists() else 0
                if src_mtime > dst_mtime:
                    shutil.copy2(src, dst)
                    shutil.copy2(src, HERMES_DEFAULT_MEM_DIR / fname)
                    print(f"[OK] 已同步（GitHub 較新）: {fname}")
                    pulled = True
                else:
                    print(f"[=] 跳過（本地較新）: {fname}")
            else:
                print(f"[=] 內容相同: {fname}")

    if pulled:
        print("[OK] 記憶已從 GitHub 拉取")
    else:
        print("[OK] 無需同步（本地已是最新）")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    else:
        print("用法: python sync_memory_github.py [push|pull]")
