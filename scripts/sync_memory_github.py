"""
記憶 → GitHub 雙向合併同步腳本 v3
支援兩台電腦各自修改記憶，自動合併不覆蓋

策略：
  push: git pull → 合併條目（取聯集）→ push
  pull: git pull → 逐條比對 mtime → 只在 GitHub 較新時加入

條目合併規則：
  - MEMORY.md 用 § 分隔，逐條比對
  - 兩邊都有的條目 → 保留（不重複）
  - 只有一邊有的條目 → 加入
  - USER.md 同樣處理（§ 分隔）
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

USERPROFILE = Path(os.environ["USERPROFILE"])
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", USERPROFILE / "AppData" / "Local"))

HERMES_MEM_DIR = LOCALAPPDATA / "hermes" / "profiles" / "alice" / "memories"
HERMES_DEFAULT_MEM_DIR = LOCALAPPDATA / "hermes" / "memories"

REPO_DIR = Path(os.environ.get("HERMES_WORKSPACE",
    USERPROFILE / "Desktop" / "Hermes工具區"))
REPO_MEM_DIR = REPO_DIR / "memory"

FILES = ["USER.md", "MEMORY.md"]


def _parse_entries(path: Path) -> list[str]:
    """解析 § 分隔的條目，回傳條目列表（去空白、去重）"""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries = []
    for part in text.split("§"):
        cleaned = part.strip()
        if cleaned:
            entries.append(cleaned)
    return entries


def _merge_entries(local_entries: list[str], remote_entries: list[str]) -> list[str]:
    """合併兩份條目：取聯集，保留所有不重複的內容"""
    seen = set()
    merged = []
    # 先放本地的（保持順序）
    for e in local_entries:
        key = e[:80]  # 前80字當指紋
        if key not in seen:
            seen.add(key)
            merged.append(e)
    # 再加入遠端有但本地沒有的
    for e in remote_entries:
        key = e[:80]
        if key not in seen:
            seen.add(key)
            merged.append(e)
    return merged


def push():
    """本地記憶 → GitHub（先合併再 push）"""
    if not REPO_DIR.exists():
        print(f"[X] Repo 不存在: {REPO_DIR}")
        return False

    # 1. git pull 取得最新
    try:
        subprocess.run(["git", "pull"],
                       cwd=str(REPO_DIR), capture_output=True, timeout=30)
    except Exception:
        pass  # 可能已經是最新

    REPO_MEM_DIR.mkdir(parents=True, exist_ok=True)
    any_changed = False

    for fname in FILES:
        local_file = HERMES_MEM_DIR / fname
        repo_file = REPO_MEM_DIR / fname

        if not local_file.exists():
            continue

        # 解析本地和 GitHub 的條目
        local_entries = _parse_entries(local_file)
        repo_entries = _parse_entries(repo_file)

        # 合併
        merged = _merge_entries(local_entries, repo_entries)

        # 產生合併內容
        merged_text = "\n§\n".join(merged) + "\n"

        # 只有真的不同才寫入
        old_text = repo_file.read_text(encoding="utf-8") if repo_file.exists() else ""
        if merged_text != old_text:
            repo_file.write_text(merged_text, encoding="utf-8")
            print(f"[OK] 已合併: {fname} (本地{len(local_entries)}條 + 遠端{len(repo_entries)}條 → {len(merged)}條)")
            any_changed = True

    if not any_changed:
        return True  # 安靜

    # 2. git commit + push（全倉庫同步，push 被拒時 rebase 重試）
    def try_push():
        subprocess.run(["git", "add", "-A"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m",
                        f"sync: auto {datetime.now().strftime('%m/%d %H:%M')}"],
                       cwd=str(REPO_DIR), capture_output=True, check=True)
        subprocess.run(["git", "push"],
                       cwd=str(REPO_DIR), capture_output=True, check=True, timeout=30)

    try:
        try_push()
        print("[OK] 已推送到 GitHub")
    except subprocess.CalledProcessError:
        # push 被拒 → rebase 重試
        try:
            subprocess.run(["git", "pull", "--rebase"],
                           cwd=str(REPO_DIR), capture_output=True, timeout=30)
            try_push()
            print("[OK] 已推送到 GitHub (rebase)")
        except subprocess.CalledProcessError as e:
            print(f"[X] Git 失敗: {e.stderr.decode() if e.stderr else e}")
            return False
    except subprocess.TimeoutExpired:
        print("[X] Git push 逾時")
        return False

    return True


def pull():
    """GitHub → 本地（版本變更整份覆蓋，否則逐條合併）"""
    try:
        subprocess.run(["git", "pull"],
                       cwd=str(REPO_DIR), capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"[X] Git pull 失敗: {e}")
        return False

    HERMES_MEM_DIR.mkdir(parents=True, exist_ok=True)
    HERMES_DEFAULT_MEM_DIR.mkdir(parents=True, exist_ok=True)

    # 檢查版本號：主機壓縮過 → 整份覆蓋
    remote_ver_file = REPO_MEM_DIR / ".version"
    local_ver_file = HERMES_MEM_DIR / ".version"
    if remote_ver_file.exists():
        try:
            remote_ver = int(remote_ver_file.read_text().strip())
            local_ver = int(local_ver_file.read_text().strip()) if local_ver_file.exists() else 0
            if remote_ver > local_ver:
                for fname in FILES:
                    src = REPO_MEM_DIR / fname
                    if src.exists():
                        shutil.copy2(src, HERMES_MEM_DIR / fname)
                        shutil.copy2(src, HERMES_DEFAULT_MEM_DIR / fname)
                shutil.copy2(remote_ver_file, local_ver_file)
                print(f"[OK] 版本 v{local_ver}→v{remote_ver}，整份覆蓋")
                return True
        except:
            pass

    # 逐條合併
    pulled = False

    for fname in FILES:
        repo_file = REPO_MEM_DIR / fname
        local_file = HERMES_MEM_DIR / fname
        if not repo_file.exists():
            continue

        local_entries = _parse_entries(local_file)
        repo_entries = _parse_entries(repo_file)

        # 找出 GitHub 有但本地沒有的條目
        local_keys = {e[:80] for e in local_entries}
        new_entries = [e for e in repo_entries if e[:80] not in local_keys]

        if new_entries:
            merged = local_entries + new_entries
            local_file.write_text("\n§\n".join(merged) + "\n", encoding="utf-8")
            HERMES_DEFAULT_MEM_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_file, HERMES_DEFAULT_MEM_DIR / fname)
            print(f"[OK] 從 GitHub 加入 {len(new_entries)} 條新記憶: {fname}")
            pulled = True
        else:
            print(f"[=] 無新條目: {fname}")

    if pulled:
        print("[OK] 記憶已合併")
    else:
        print("[OK] 無需同步")

    # 部署更新的腳本到 alice profile
    for subdir, target_name in [("scripts", "scripts"), ("hermes_skills", "skills/alice")]:
        src_dir = REPO_DIR / subdir
        if src_dir.exists():
            dst_dir = LOCALAPPDATA / "hermes" / "profiles" / "alice" / target_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            for f in src_dir.rglob("*"):
                if f.is_file() and f.suffix in (".py", ".md", ".bat", ".txt"):
                    rel = f.relative_to(src_dir)
                    dst = dst_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists() or f.read_bytes() != dst.read_bytes():
                        shutil.copy2(f, dst)
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull()
    else:
        print("用法: python sync_memory_github.py [push|pull]")
