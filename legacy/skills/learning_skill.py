from skills.base_skill import BaseSkill

class LearningSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "learning_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "add_core_directive",
                "description": "學習與修正機制！當使用者指出你的錯誤、教導你新規則，或要求你「以後都要這樣做」時，【必須立即使用此工具】。這會將該規則寫入系統鐵律中，以修正你未來的行為模式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directive_text": {
                            "type": "string",
                            "description": "要永遠記住的核心鐵律/教訓。請描述得清晰明確。例如：『當使用者要求打字時，必須直接覆寫或使用正確的輸入法。』或『除非使用者明確要求，不可主動使用 Markdown。』"
                        },
                        "level": {
                            "type": "string",
                            "enum": ["L1", "L2", "L3"],
                            "description": "鐵律層級：L1=系統鐵律(最高權威), L2=經驗教訓(預設), L3=偏好記錄"
                        }
                    },
                    "required": ["directive_text"]
                }
            },
            {
                "name": "view_core_directives",
                "description": "檢視你目前已經記住的所有系統鐵律與過往教訓。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "replace_core_directives",
                "description": "【批量編輯】一次性替換所有核心鐵律。用於合併重複、清理過時條目。接受完整的新鐵律陣列。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_directives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "完整的新鐵律陣列，會直接覆蓋所有現有鐵律"
                        }
                    },
                    "required": ["new_directives"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        memory = context.get("memory")
        if not memory:
            return {"error": "No memory context provided"}

        if function_name == "add_core_directive":
            rule = args.get("directive_text")
            if not rule:
                return {"error": "Missing directive_text"}
            
            level = args.get("level", "L2")  # 預設 L2 經驗教訓
            
            if not isinstance(memory.long_term.get("core_directives"), list):
                memory.long_term["core_directives"] = []
            
            # 新格式：{level, text} 字典
            memory.long_term["core_directives"].append({"level": level, "text": rule})
            memory.unsaved_changes = True
            
            # 因為這是重要鐵律，最好直接存檔
            memory.save_all_force()
            
            level_label = {"L1": "系統鐵律", "L2": "經驗教訓", "L3": "偏好記錄"}.get(level, level)
            return {
                "status": "success", 
                "message": f"✅ 已將「{rule}」寫入大腦深層記憶的 [{level_label}] 中！我之後絕對不會再犯/忘記了。"
            }
            
        elif function_name == "view_core_directives":
            rules = memory.long_term.get("core_directives", [])
            if not rules:
                return {"status": "success", "message": "目前沒有任何核心鐵律。"}
            
            # 分級整理
            by_level = {"L1": [], "L2": [], "L3": []}
            for i, r in enumerate(rules):
                if isinstance(r, dict):
                    lv = r.get("level", "L2")
                    by_level.setdefault(lv, []).append((i+1, r["text"]))
                else:
                    # 向後相容：舊格式純文字 → L2
                    by_level["L2"].append((i+1, r))
            
            level_labels = {"L1": "🔴 系統鐵律（最高權威）", "L2": "🟡 經驗教訓", "L3": "🟢 偏好記錄"}
            resp = "🧠 當前的核心鐵律/教訓：\n"
            resp += "⚠️ 衝突裁決：L1 > L2 > L3\n\n"
            for lv in ["L1", "L2", "L3"]:
                items = by_level.get(lv, [])
                if items:
                    resp += f"{level_labels.get(lv, lv)}：\n"
                    for num, text in items:
                        resp += f"  {num}. {text}\n"
                    resp += "\n"
            return {"status": "success", "message": resp}

        elif function_name == "replace_core_directives":
            new_rules = args.get("new_directives")
            if not isinstance(new_rules, list):
                return {"error": "new_directives 必須是陣列"}
            
            old_count = len(memory.long_term.get("core_directives", []))
            memory.long_term["core_directives"] = new_rules
            memory.unsaved_changes = True
            memory.save_all_force()
            
            return {
                "status": "success",
                "message": f"✅ 已將核心鐵律從 {old_count} 條替換為 {len(new_rules)} 條。已強制存檔。"
            }
            
        return {"error": "Unknown function"}
