"""
記憶雲端同步腳本
將 Hermes 記憶檔案同步到 MEGA 雲端資料夾
在多台電腦之間保持記憶一致

使用方式：
  python sync_memory.py push    → 上傳記憶到 MEGA
  python sync_memory.py pull    → 從 MEGA 下載記憶
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

HERMES_MEMORY_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\profiles\alice\memories"))
MEGA_SYNC_DIR = Path(os.getenv("MEGA_SYNC_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳\MEGA備份\hermes_memory"))

FILES_TO_SYNC = ["USER.md", "MEMORY.md"]

def push():
    """上傳記憶到 MEGA"""
    MEGA_SYNC_DIR.mkdir(parents=True, exist_ok=True)
    for fname in FILES_TO_SYNC:
        src = HERMES_MEMORY_DIR / fname
        dst = MEGA_SYNC_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✅ 已上傳: {fname}")
        else:
            print(f"⚠️ 不存在: {fname}")
    # 寫入時間戳
    (MEGA_SYNC_DIR / "last_sync.txt").write_text(datetime.now().isoformat())
    print(f"✅ 同步完成 → {MEGA_SYNC_DIR}")

def pull():
    """從 MEGA 下載記憶"""
    if not MEGA_SYNC_DIR.exists():
        print(f"❌ MEGA 同步目錄不存在: {MEGA_SYNC_DIR}")
        return
    HERMES_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for fname in FILES_TO_SYNC:
        src = MEGA_SYNC_DIR / fname
        dst = HERMES_MEMORY_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✅ 已下載: {fname}")
        else:
            print(f"⚠️ MEGA 上不存在: {fname}")
    print(f"✅ 記憶已同步到 Hermes")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    else:
        print("用法: python sync_memory.py [push|pull]")
