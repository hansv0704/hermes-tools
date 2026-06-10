"""
記憶雲端同步腳本 v2
將 Hermes 記憶檔案雙向同步到 MEGA 雲端資料夾
在多台電腦之間保持記憶一致

模式：
  python sync_memory.py push    → 強制上傳到 MEGA
  python sync_memory.py pull    → 強制從 MEGA 下載
  python sync_memory.py auto    → 自動判斷方向（cron 用）
  python sync_memory.py         → 預設 auto

雙向邏輯 (auto)：
  1. 比較本地 vs MEGA 的檔案修改時間
  2. 本地較新 → push（上傳）
  3. MEGA 較新 → pull（下載）
  4. 相同 → skip（安靜，不輸出 = cron 不推送通知）
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone

# 自動偵測使用者目錄（不寫死使用者名稱）
USERPROFILE = Path(os.environ["USERPROFILE"])
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", USERPROFILE / "AppData" / "Local"))

# Hermes alice profile 的記憶目錄
HERMES_MEMORY_DIR = LOCALAPPDATA / "hermes" / "profiles" / "alice" / "memories"
# 同時也同步 default profile（防止主人用 hermes 不加 -p alice）
HERMES_DEFAULT_MEMORY_DIR = LOCALAPPDATA / "hermes" / "memories"

# MEGA 同步目錄 — 優先讀取環境變數，否則自動偵測 Desktop 下的大崩儀器目錄
def find_mega_dir():
    env_dir = os.getenv("MEGA_SYNC_DIR", "")
    if env_dir:
        return Path(env_dir)
    # 自動搜尋桌面上的大崩儀器目錄
    desktop = USERPROFILE / "Desktop"
    for pattern in ["大崩儀器DATA回傳", "*大崩*", "*MEGA*"]:
        for p in desktop.glob(pattern):
            mega_mem = p / "MEGA備份" / "hermes_memory"
            if mega_mem.exists():
                return mega_mem
            if p.exists() and p.is_dir():
                # 嘗試直接找 MEGA備份/hermes_memory
                candidate = p / "MEGA備份" / "hermes_memory"
                if candidate.exists():
                    return candidate
    return None

MEGA_SYNC_DIR = find_mega_dir()
if MEGA_SYNC_DIR is None:
    # fallback: 預設路徑（可能是新電腦尚未設定 MEGA）
    MEGA_SYNC_DIR = USERPROFILE / "Desktop" / "大崩儀器DATA回傳" / "MEGA備份" / "hermes_memory"

FILES_TO_SYNC = ["USER.md", "MEMORY.md"]
TIMESTAMP_FILE = "last_sync.txt"


def _get_mtime(path: Path):
    """取得檔案修改時間，不存在回傳 epoch"""
    if path.exists():
        return path.stat().st_mtime
    return 0


def push(verbose=True):
    """上傳記憶到 MEGA"""
    MEGA_SYNC_DIR.mkdir(parents=True, exist_ok=True)
    any_uploaded = False
    for fname in FILES_TO_SYNC:
        src = HERMES_MEMORY_DIR / fname
        dst = MEGA_SYNC_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            if verbose:
                print(f"[OK] 已上傳: {fname}")
            any_uploaded = True
        else:
            if verbose:
                print(f"[!] 不存在: {fname}")
    if any_uploaded:
        (MEGA_SYNC_DIR / TIMESTAMP_FILE).write_text(datetime.now(timezone.utc).isoformat())
    if verbose:
        print(f"[OK] Push 完成")


def pull(verbose=True):
    """從 MEGA 下載記憶"""
    if not MEGA_SYNC_DIR.exists():
        if verbose:
            print(f"[X] MEGA 目錄不存在: {MEGA_SYNC_DIR}")
        return False
    any_downloaded = False
    HERMES_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for fname in FILES_TO_SYNC:
        src = MEGA_SYNC_DIR / fname
        dst = HERMES_MEMORY_DIR / fname
        if src.exists():
            # 只在來源比本地新時才複製
            if _get_mtime(src) > _get_mtime(dst):
                shutil.copy2(src, dst)
                if verbose:
                    print(f"[OK] 已下載: {fname}")
                any_downloaded = True
            else:
                if verbose:
                    print(f"[=] 已是最新: {fname}")
        else:
            if verbose:
                print(f"[!] MEGA 上不存在: {fname}")
    
    # 同步到 default profile（安全起見）
    HERMES_DEFAULT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for fname in FILES_TO_SYNC:
        src = HERMES_MEMORY_DIR / fname
        dst = HERMES_DEFAULT_MEMORY_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
    
    if verbose:
        print(f"[OK] Pull 完成")
    return any_downloaded


def auto():
    """自動判斷方向：本地新→push，MEGA新→pull，相同→安靜"""
    if not MEGA_SYNC_DIR.exists():
        # MEGA 目錄不存在，嘗試 push（首次設定）
        print("[!] MEGA 目錄不存在，嘗試 push...")
        push(verbose=True)
        return
    
    # 比較雙方的修改時間
    local_newer = False
    mega_newer = False
    
    for fname in FILES_TO_SYNC:
        local_file = HERMES_MEMORY_DIR / fname
        mega_file = MEGA_SYNC_DIR / fname
        local_mtime = _get_mtime(local_file)
        mega_mtime = _get_mtime(mega_file)
        
        if local_mtime > mega_mtime:
            local_newer = True
        elif mega_mtime > local_mtime:
            mega_newer = True
    
    if local_newer and not mega_newer:
        # 本地有更新 → push
        print(f"[→] 本地記憶較新，Push 到 MEGA")
        push(verbose=True)
    elif mega_newer and not local_newer:
        # MEGA 有更新 → pull
        print(f"[←] MEGA 記憶較新，Pull 到本地")
        pull(verbose=True)
    elif local_newer and mega_newer:
        # 兩邊都有更新（衝突）→ 以本地為準 push
        print(f"[!] 雙向都有更新，以本地為準 Push")
        push(verbose=True)
    else:
        # 完全相同 → 安靜（不輸出 = cron 不發通知）
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    elif cmd == "auto":
        auto()
    else:
        print("用法: python sync_memory.py [push|pull|auto]")
        print("預設 auto → 自動判斷方向（cron 用）")
