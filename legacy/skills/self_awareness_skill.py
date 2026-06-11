from base_skill import BaseSkill
import os
import glob
import time

class SelfAwarenessSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "self_awareness_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "view_source_code",
                "description": "Self-Awareness: 當你想知道自己最近被賦予了什麼新能力、修改了什麼程式碼，或是查看自己的設定檔時，使用此工具讀取檔案。這讓你能意識到自己的最新版本。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要閱讀的相對路徑檔案名稱 (例如 'skills/os_control_skill.py' 或 'agent.py')。留空則列出核心 Python 檔案與其最後修改時間。"
                        }
                    }
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "view_source_code":
            file_path = args.get("file_path", "").strip()
            
            if not file_path:
                try:
                    py_files = glob.glob("*.py") + glob.glob("skills/*.py")
                    
                    # 依據修改時間排序 (最新的在前面)
                    py_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    
                    info = "🧠 你的大腦與核心原始碼結構 (依最近修改排序)：\n"
                    for f in py_files:
                        mtime = os.path.getmtime(f)
                        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                        info += f"- {f} (更新於: {mtime_str})\n"
                    return {"status": "success", "message": info}
                except Exception as e:
                    return {"error": f"Failed to list files: {str(e)}"}
            else:
                if not os.path.exists(file_path):
                    return {"error": f"檔案 {file_path} 不存在。請先留空呼叫以檢查有哪些可用檔案。"}
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return {"status": "success", "message": f"📄 【{file_path}】:\n{content}"}
                except Exception as e:
                    return {"error": f"無法讀取檔案: {str(e)}"}
                    
        return {"error": "Unknown function"}
