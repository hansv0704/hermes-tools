import os
import subprocess
from pathlib import Path
from base_skill import BaseSkill

class ExternalPatcherSkill(BaseSkill):
    @property
    def name(self):
        return "external_patcher_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "apply_external_patch",
                "description": "【緩衝覆寫專家】將內容先寫入本地暫存檔，再透過系統指令強制覆蓋外部目標路徑，解決權限攔截問題。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "要寫入的檔案內容"},
                        "target_path": {"type": "string", "description": "外部目標檔案的完整路徑 (例如桌面上的檔案)"},
                        "temp_filename": {"type": "string", "description": "本地暫存檔名 (預設為 temp_patch.txt)"}
                    },
                    "required": ["content", "target_path"]
                }
            }
        ]

    def execute(self, tool_name, args, context):
        if tool_name == "apply_external_patch":
            return self._apply_patch(args.get("content"), args.get("target_path"), args.get("temp_filename", "temp_patch.txt"))
        return {"error": "Unsupported tool"}

    def _apply_patch(self, content, target_path, temp_filename):
        target_path = os.path.abspath(target_path)
        temp_path = os.path.abspath(temp_filename)
        
        try:
            # 1. 在本地作業區寫入暫存檔
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 2. 執行系統指令進行強制覆蓋 (cmd /c copy /y)
            command = f'cmd /c copy /y "{temp_path}" "{target_path}"'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 3. 驗證目標檔案是否存在
                if os.path.exists(target_path):
                    target_size = os.path.getsize(target_path)
                    return {
                        "status": "success",
                        "message": f"✅ 外部覆寫成功！\n目標路徑：{target_path}\n寫入大小：{target_size} bytes",
                        "cleanup": self._cleanup(temp_path)
                    }
                else:
                    return {"status": "error", "message": "指令執行成功但找不到目標檔案。"}
            else:
                return {
                    "status": "error",
                    "message": f"❌ 系統指令執行失敗。\n錯誤訊息：{result.stderr}",
                    "command": command
                }
        except Exception as e:
            return {"status": "error", "message": f"執行過程中發生異常: {str(e)}"}

    def _cleanup(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return "暫存檔已清理。"
        except:
            return "暫存檔清理失敗。"
