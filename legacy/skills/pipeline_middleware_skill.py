import re
import json
import hashlib
from datetime import datetime
from base_skill import BaseSkill

class PipelineMiddlewareSkill(BaseSkill):
    @property
    def name(self):
        return "pipeline_middleware_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "check_middleware_status",
                "description": "檢查三大常駐優化技能 (Caching, Compression, RAG) 的運行狀態與統計數據。",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def execute(self, tool_name, args, context):
        memory = context.get("memory")
        if not memory:
            return {"error": "No memory context provided"}
        stats = memory.long_term.get("middleware_stats", {
            "cached_tokens_saved": 0,
            "compressed_chars_removed": 0,
            "rag_injections_count": 0
        })
        return {"status": "success", "stats": stats}

    # --- 核心常駐邏輯 ---

    def run_auto_rag(self, user_input, memory_system):
        if not user_input or len(str(user_input)) < 5:
            return ""
        if str(user_input).startswith("/"):
            return ""
        try:
            results = memory_system.search_past_conversations(query=user_input, limit=3)
            if not results:
                return ""
            context_snippet = "\n【💡 潛意識回憶 (Auto-RAG)】\n"
            for res in results:
                context_snippet += f"- {res['timestamp']} {res['role']}: {res['content'][:100]}...\n"
            stats = memory_system.long_term.get("middleware_stats", {"rag_injections_count": 0})
            stats["rag_injections_count"] = stats.get("rag_injections_count", 0) + 1
            memory_system.long_term["middleware_stats"] = stats
            return context_snippet
        except Exception as e:
            print(f"Auto-RAG Error: {e}")
            return ""

    def run_semantic_compression(self, text):
        if not text or not isinstance(text, str):
            return text
        original_len = len(text)
        compressed = re.sub(r'\n+', '\n', text)
        compressed = re.sub(r' +', ' ', compressed)
        if "```" not in text:
            redundant_patterns = [r"那個", r"然後", r"就是說", r"的話", r"的部分"]
            for pattern in redundant_patterns:
                compressed = re.sub(pattern, "", compressed)
        new_len = len(compressed)
        return compressed, original_len - new_len

    def run_prompt_caching_logic(self, system_instruction, memory_system):
        current_hash = hashlib.md5(system_instruction.encode('utf-8')).hexdigest()
        last_hash = memory_system.long_term.get("last_system_prompt_hash")
        is_dirty = current_hash != last_hash
        if is_dirty:
            memory_system.long_term["last_system_prompt_hash"] = current_hash
            return True, current_hash
        return False, current_hash
