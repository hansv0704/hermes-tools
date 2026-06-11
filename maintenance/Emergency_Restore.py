import os
import shutil
import json
from pathlib import Path

def emergency_restore():
    print("========================================")
    print("   Alice 艾莉絲 - 緊急系統救援工具 v2.0   ")
    print("       (物理淨化級環境回溯方案)          ")
    print("========================================")
    
    backup_root = Path("backups/restore_points")
    whitelist = [
        "alice_core.db", "logs", "backups", "credentials.json", "token.json",
        ".git", "__pycache__", ".vscode", ".idea"
    ]
    
    if not backup_root.exists():
        print("❌ 錯誤：找不到 backups/restore_points 資料夾！")
        input("按任意鍵退出...")
        return

    points = sorted([d for d in backup_root.iterdir() if d.is_dir()], reverse=True)
    
    if not points:
        print("❌ 錯誤：目前沒有任何可用的還原點。")
        input("按任意鍵退出...")
        return

    print("\n🕒 請選擇要還原的時間點：")
    for i, p in enumerate(points):
        print(f"[{i}] {p.name}")

    try:
        choice = int(input("\n請輸入編號 (或輸入 -1 取消): "))
        if choice == -1: return
        selected_point = points[choice]
    except (ValueError, IndexError):
        print("❌ 無效的選擇。")
        return

    manifest_path = selected_point / "manifest.json"
    if not manifest_path.exists():
        print("\n⚠️ 警告：此還原點為 1.0 舊版格式，不具備 Manifest。")
        print("將執行『覆寫式還原』，不會刪除多餘檔案。")
        confirm = input("是否繼續？ (y/n): ")
        if confirm.lower() != 'y': return
        manifest = None
    else:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    print(f"\n🚀 正在執行物理級還原至: {selected_point.name}...")

    # --- 第一階段：物理清理 (僅在有 Manifest 時執行) ---
    if manifest:
        print("\n🧹 正在清理『未來垃圾』...")
        for item in Path(".").iterdir():
            if item.name in whitelist: continue
            
            if item.is_file() and item.name not in manifest["files"]:
                print(f"  [-] 刪除多餘檔案: {item.name}")
                item.unlink()
            elif item.is_dir() and item.name not in manifest["dirs"]:
                print(f"  [-] 刪除多餘目錄: {item.name}")
                shutil.rmtree(item)

    # --- 第二階段：鏡像還原 ---
    print("\n📦 正在還原核心檔案...")
    if manifest:
        for filename in manifest["files"]:
            shutil.copy2(selected_point / filename, Path(".") / filename)
        for dirname in manifest["dirs"]:
            dest_dir = Path(".") / dirname
            if dest_dir.exists(): shutil.rmtree(dest_dir)
            shutil.copytree(selected_point / dirname, dest_dir)
    else:
        for f in selected_point.glob("*"):
            if f.is_file() and f.name != "manifest.json":
                shutil.copy2(f, Path(".") / f.name)
        if (selected_point / "skills").exists():
            shutil.copytree(selected_point / "skills", Path("skills"), dirs_exist_ok=True)

    print("\n✅ 物理級還原完成！")
    print("系統環境已回歸純淨。請重新啟動 Alice。")
    input("按任意鍵退出...")

if __name__ == "__main__":
    emergency_restore()
