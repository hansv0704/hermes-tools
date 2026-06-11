import os
import re
from skills.base_skill import BaseSkill

class CodeSearchSkill(BaseSkill):
    """
    全域代碼搜尋技能 (CodeSearchSkill) v1.0
    提供類似 grep 的功能，讓 Alice 能在整個專案目錄中快速定位特定字串或邏輯。
    """

    @property
    def name(self) -> str:
        return "code_search_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "search_code_content",
                "description": "【全域代碼搜尋】在指定目錄下的所有檔案中搜尋特定關鍵字或正則表達式。自動排除備份與快取目錄。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜尋的關鍵字或正則表達式"
                        },
                        "root_dir": {
                            "type": "string",
                            "description": "搜尋起點目錄，預設為當前目錄 '.'",
                            "default": "."
                        },
                        "extension_filter": {
                            "type": "string",
                            "description": "副檔名過濾 (例如 '.py', '.json')，多個請用逗號分隔",
                            "default": ".py,.json,.txt"
                        },
                        "use_regex": {
                            "type": "boolean",
                            "description": "是否使用正則表達式搜尋",
                            "default": False
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大回傳結果筆數，預設 50",
                            "default": 50
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "search_code_content":
            query = args.get("query")
            root_dir = args.get("root_dir", ".")
            ext_filter = args.get("extension_filter", ".py,.json,.txt").split(",")
            use_regex = args.get("use_regex", False)
            max_results = args.get("max_results", 50)
            
            return self._perform_search(query, root_dir, ext_filter, use_regex, max_results)
        return {"error": f"Unknown function: {function_name}"}

    def _perform_search(self, query, root_dir, ext_filter, use_regex, max_results):
        results = []
        exclude_dirs = {".git", "__pycache__", "backups", "node_modules", ".venv", "logs"}
        
        try:
            pattern = re.compile(query) if use_regex else None
            
            for root, dirs, files in os.walk(root_dir):
                # 排除不需要的目錄
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if not any(file.endswith(ext.strip()) for ext in ext_filter):
                        continue
                    
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                match = False
                                if use_regex:
                                    if pattern.search(line):
                                        match = True
                                if not use_regex:
                                    if query in line:
                                        match = True
                                        
                                if match:
                                    results.append({
                                        "file": file_path,
                                        "line": line_num,
                                        "content": line.strip()
                                    })
                                    if len(results) >= max_results:
                                        return {
                                            "status": "partial_success",
                                            "message": f"已達到最大結果限制 ({max_results})",
                                            "results": results
                                        }
                    except Exception as e:
                        continue # 略過無法讀取的檔案
            
            return {
                "status": "success",
                "count": len(results),
                "results": results
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
