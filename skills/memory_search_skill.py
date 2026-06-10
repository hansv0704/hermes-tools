from base_skill import BaseSkill

class MemorySearchSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "memory_search_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "search_past_conversations",
                "description": "當使用者問起以前討論過但現在已經不在短期記憶中的事情時，使用 FTS5 全文搜索來找出相關的歷史紀錄。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的關鍵字"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最多回傳幾筆資料 (預設 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        memory = context.get("memory")
        if not memory:
            return {"error": "無法存取記憶體 (Memory object not found in context)"}

        if function_name == "search_past_conversations":
            query = args.get("query", "")
            limit = args.get("limit", 5)
            
            if not query:
                return {"error": "缺少 query 參數"}
                
            results = memory.search_fts_memory(query, limit=limit)
            
            if not results:
                return {"status": "success", "message": f"搜尋 '{query}' 沒有找到任何歷史紀錄。"}
                
            formatted = f"針對 '{query}' 找到以下 {len(results)} 筆紀錄：\n\n"
            for r in results:
                summary_text = f" (摘要: {r['summary']})" if r.get('summary') else ""
                formatted += f"[{r['timestamp']}] {r['role']}: {r['content']}{summary_text}\n"
                
            return {"status": "success", "message": formatted}
            
        return {"error": "Unknown function"}
