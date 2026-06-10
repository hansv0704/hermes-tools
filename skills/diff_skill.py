import difflib
from base_skill import BaseSkill

class DiffSkill(BaseSkill):
    @property
    def name(self):
        return "diff_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "generate_diff",
                "description": "【開發者工具】生成兩個字串之間的差異摘要 (Unified Diff 格式)。用於 ADSP 異動報告。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "old_text": {"type": "string", "description": "原始內容"},
                        "new_text": {"type": "string", "description": "修改後的內容"},
                        "filename": {"type": "string", "description": "檔案名稱 (選填)"}
                    },
                    "required": ["old_text", "new_text"]
                }
            }
        ]

    def execute(self, tool_name, args):
        if tool_name == "generate_diff":
            old_text = args.get("old_text", "").splitlines()
            new_text = args.get("new_text", "").splitlines()
            filename = args.get("filename", "file")
            
            diff = difflib.unified_diff(
                old_text, new_text, 
                fromfile=f"a/{filename}", 
                tofile=f"b/{filename}", 
                lineterm=""
            )
            
            diff_text = "\n".join(list(diff))
            if not diff_text:
                return {"status": "success", "message": "內容完全一致，無差異。"}
            
            return {
                "status": "success",
                "diff": diff_text,
                "message": "已生成差異摘要。"
            }
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
