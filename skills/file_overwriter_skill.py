import os
from base_skill import BaseSkill

class FileOverwriterSkill(BaseSkill):
    @property
    def name(self):
        return "file_overwriter_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "overwrite_file",
                "description": "強制覆寫系統中的任何檔案 (用於硬編碼更新架構)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "目標檔案路徑"},
                        "content": {"type": "string", "description": "新的檔案內容"}
                    },
                    "required": ["file_path", "content"]
                }
            }
        ]

    def execute(self, tool_name, args, context):
        file_path = args.get("file_path")
        content = args.get("content")
        
        # 安全檢查：只允許覆寫當前目錄下的檔案
        abs_path = os.path.abspath(file_path)
        current_dir = os.getcwd()
        if not abs_path.startswith(current_dir):
            return {"error": "禁止存取目錄外的檔案。"}

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "message": f"檔案 {file_path} 已成功覆寫。"}
        except Exception as e:
            return {"error": str(e)}
