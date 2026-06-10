import os
import shutil
import datetime
import json
import re
from pathlib import Path
from base_skill import BaseSkill
from config import logger

class SystemRecoverySkill(BaseSkill):
    @property
    def name(self):
        return "system_recovery_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "create_restore_point",
                "description": "建立系統還原點。這會鏡像備份所有核心代碼，並生成 Manifest 清單以便未來完整回溯。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "還原點描述，例如 '升級還原系統前'"
                        }
                    },
                    "required": ["description"]
                }
            },
            {
                "name": "list_restore_points",
                "description": "列出目前所有可用的系統還原點。",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "perform_restoration",
                "description": "【物理級回溯】將系統完整還原至指定點。會主動刪除備份點之後產生的所有非白名單檔案。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timestamp": {
                            "type": "string",
                            "description": "還原點的時間戳記 (例如 '20260507_144500')"
                        }
                    },
                    "required": ["timestamp"]
                }
            }
        ]

    def execute(self, function_name, args, context):
        backup_root = Path("backups/restore_points")
        backup_root.mkdir(parents=True, exist_ok=True)
        
        # 絕對保護白名單 (不參與還原刪除，也不會被覆蓋)
        whitelist = [
            "alice_core.db", 
            "logs", 
            "backups", 
            "credentials.json", 
            "token.json",
            ".git",
            "__pycache__",
            ".vscode",
            ".idea"
        ]

        if function_name == "create_restore_point":
            try:
                desc = args.get("description", "no_description")
                # 【修復】：自動清洗 Windows 非法字元
                desc = re.sub(r'[<>:"/\\|?*]', '_', desc)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                folder_name = f"{timestamp}_{desc}"
                target_dir = backup_root / folder_name
                target_dir.mkdir()

                manifest = {"files": [], "dirs": []}

                for item in Path(".").iterdir():
                    if item.name in whitelist or item.name == "backups":
                        continue
                    
                    if item.is_file():
                        shutil.copy2(item, target_dir / item.name)
                        manifest["files"].append(item.name)
                    elif item.is_dir():
                        shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)
                        manifest["dirs"].append(item.name)

                with open(target_dir / "manifest.json", "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4, ensure_ascii=False)

                all_backups = sorted([d for d in backup_root.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
                if len(all_backups) > 10:
                    for old_backup in all_backups[10:]:
                        shutil.rmtree(old_backup)

                return {
                    "status": "success",
                    "message": f"✅ 物理級還原點已建立：{folder_name}。已生成 Manifest 清單。",
                    "path": str(target_dir)
                }
            except Exception as e:
                logger.error(f"建立還原點失敗: {str(e)}")
                return {"status": "error", "message": f"建立還原點失敗: {str(e)}"}

        elif function_name == "list_restore_points":
            try:
                points = [d.name for d in backup_root.iterdir() if d.is_dir()]
                if not points:
                    return {"status": "success", "message": "目前沒有任何還原點紀錄。", "points": []}
                return {
                    "status": "success",
                    "message": f"找到 {len(points)} 個還原點。",
                    "points": sorted(points, reverse=True)
                }
            except Exception as e:
                return {"status": "error", "message": f"讀取還原點清單失敗: {str(e)}"}

        elif function_name == "perform_restoration":
            try:
                timestamp = args.get("timestamp")
                source_dir = next((d for d in backup_root.iterdir() if d.is_dir() and d.name.startswith(timestamp)), None)
                
                if not source_dir:
                    return {"status": "error", "message": f"❌ 找不到時間戳記為 {timestamp} 的還原點。"}

                manifest_path = source_dir / "manifest.json"
                if not manifest_path.exists():
                    return {
                        "status": "error", 
                        "message": "此還原點為 1.0 舊版格式，不具備 Manifest，無法執行物理級回溯。請手動處理或使用舊版邏輯。"
                    }

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                # --- 第一階段：物理清理 (Atomic Clean) ---
                for item in Path(".").iterdir():
                    if item.name in whitelist:
                        continue
                    
                    if item.is_file() and item.name not in manifest["files"]:
                        logger.warning(f"還原清理：物理刪除多餘檔案 -> {item.name}")
                        item.unlink()
                    elif item.is_dir() and item.name not in manifest["dirs"]:
                        logger.warning(f"還原清理：物理刪除多餘目錄 -> {item.name}")
                        shutil.rmtree(item)

                # --- 第二階段：鏡像還原 (Mirror Restore) ---
                for filename in manifest["files"]:
                    src_file = source_dir / filename
                    if src_file.exists():
                        shutil.copy2(src_file, Path(".") / filename)
                
                for dirname in manifest["dirs"]:
                    src_dir = source_dir / dirname
                    if src_dir.exists():
                        dest_dir = Path(".") / dirname
                        if dest_dir.exists():
                            shutil.rmtree(dest_dir)
                        shutil.copytree(src_dir, dest_dir)

                return {
                    "status": "success",
                    "message": f"⚠️ 系統已完成『物理級回溯』至 {source_dir.name}。備份點之後產生的所有多餘檔案已徹底清除。請立即輸入 /restart。"
                }
            except Exception as e:
                logger.error(f"物理還原失敗: {str(e)}")
                return {"status": "error", "message": f"執行物理還原失敗: {str(e)}"}

        return {"status": "error", "message": f"未知功能: {function_name}"}
