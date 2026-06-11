"""
Alice Game Studio — /design-system Skill
Phase 2.2: 章節式 GDD 寫作
移植自 CCGS design-system：8 必要段落，每次一個系統，逐步引導
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

_sessions: Dict[str, 'DesignSystemSession'] = {}

# ── GDD 8 段落定義 ──
GDD_SECTIONS = {
    1: {
        "id": "overview",
        "name": "Overview & Purpose",
        "icon": "📋",
        "desc": "系統概述與目的 — 這個系統是什麼？為什麼需要？",
        "prompts": [
            "這個系統的一句話描述是什麼？",
            "它為玩家解決什麼問題或提供什麼體驗？",
            "在整體遊戲中扮演什麼角色？",
        ],
        "template": """## 📋 Overview & Purpose

### 系統定義
{一句話定義}

### 設計目的
{為什麼需要這個系統}

### 在遊戲中的角色
{在整體遊戲中的地位}
"""
    },
    2: {
        "id": "core_mechanics",
        "name": "Core Mechanics",
        "icon": "⚙️",
        "desc": "核心機制 — 系統如何運作？",
        "prompts": [
            "玩家與這個系統互動的主要方式是什麼？",
            "系統的核心規則和公式是什麼？",
            "有哪些輸入和輸出？",
        ],
        "template": """## ⚙️ Core Mechanics

### 互動方式
{玩家如何互動}

### 核心規則
{規則與公式}

### 輸入/輸出
- 輸入：{輸入}
- 輸出：{輸出}
"""
    },
    3: {
        "id": "user_flow",
        "name": "User Flow / Player Journey",
        "icon": "🔄",
        "desc": "使用者流程 — 玩家從接觸到精通的旅程",
        "prompts": [
            "玩家第一次使用這個系統的體驗是什麼？",
            "熟練玩家如何使用這個系統？",
            "使用頻率如何？（每次會話、每小時、每日...）",
        ],
        "template": """## 🔄 User Flow / Player Journey

### 首次體驗
{新手體驗}

### 熟練使用
{進階使用}

### 使用頻率
{頻率}
"""
    },
    4: {
        "id": "states_transitions",
        "name": "States & Transitions",
        "icon": "📊",
        "desc": "狀態與轉換 — 系統的狀態機模型",
        "prompts": [
            "系統有哪些狀態？（最少 3 個）",
            "什麼事件觸發狀態轉換？",
            "有哪些過渡動畫或回饋？",
        ],
        "template": """## 📊 States & Transitions

### 狀態清單
{狀態清單}

### 轉換條件
{狀態轉換事件}

### 視覺回饋
{過渡動畫/回饋}
"""
    },
    5: {
        "id": "data_model",
        "name": "Data Model",
        "icon": "🗃️",
        "desc": "資料模型 — 系統需要什麼資料？",
        "prompts": [
            "系統需要追蹤哪些資料？",
            "資料如何儲存和載入？",
            "有哪些數值平衡考量？",
        ],
        "template": """## 🗃️ Data Model

### 資料欄位
{資料欄位定義}

### 儲存方式
{儲存/載入策略}

### 數值平衡
{平衡考量}
"""
    },
    6: {
        "id": "edge_cases",
        "name": "Edge Cases & Error States",
        "icon": "⚠️",
        "desc": "邊界情況與錯誤處理",
        "prompts": [
            "當玩家做出非預期行為時會發生什麼？",
            "極限值是什麼？（零、最大、空）",
            "載入失敗或網路中斷時如何處理？",
        ],
        "template": """## ⚠️ Edge Cases & Error States

### 非預期行為
{異常處理}

### 極限值
{邊界條件}

### 錯誤恢復
{錯誤恢復策略}
"""
    },
    7: {
        "id": "dependencies",
        "name": "Dependencies",
        "icon": "🔗",
        "desc": "依賴關係 — 與其他系統的關聯",
        "prompts": [
            "這個系統依賴哪些其他系統？",
            "哪些系統依賴這個系統？",
            "與其他系統之間的資料交換是什麼？",
        ],
        "template": """## 🔗 Dependencies

### 上游依賴
{依賴的系統}

### 下游依賴
{被哪些系統依賴}

### 資料交換
{交換的資料}
"""
    },
    8: {
        "id": "metrics",
        "name": "Metrics & Success Criteria",
        "icon": "📈",
        "desc": "指標與成功標準",
        "prompts": [
            "如何衡量這個系統成功與否？",
            "有哪些 KPI 可以追蹤？",
            "玩家滿意度的指標是什麼？",
        ],
        "template": """## 📈 Metrics & Success Criteria

### KPI
{關鍵指標}

### 成功標準
{成功定義}

### 玩家回饋
{滿意度指標}
"""
    },
}


class DesignSystemSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "init"
        self.phase = 0
        self.total_sections = 8
        self.system_name: str = ""
        self.system_description: str = ""
        self.current_section: int = 1
        self.section_answers: Dict[int, Dict[str, str]] = {}  # {section_num: {prompt_index: answer}}
        self.completed_sections: List[int] = []
        self.final_document: str = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "phase": self.phase,
            "system_name": self.system_name,
            "current_section": self.current_section,
            "completed_sections": self.completed_sections,
            "total_sections": self.total_sections,
        }


class DesignSystemSkill:
    """/design-system 核心邏輯"""

    def handle_init(self, system_name: str = "", from_map_systems: str = "") -> dict:
        """初始化 GDD 寫作"""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session = DesignSystemSession(session_id)
        session.state = "naming"
        session.phase = 0

        if system_name:
            session.system_name = system_name
            session.state = "writing"
            session.phase = 1
            session.current_section = 1

        _sessions[session_id] = session

        if session.state == "naming":
            return {
                "session_id": session_id,
                "phase": 0,
                "phase_name": "系統命名",
                "question": {
                    "id": "system_name",
                    "text": "你要為哪個系統撰寫 GDD？請輸入系統名稱（例如：戰鬥系統、道具系統）",
                    "hint": from_map_systems if from_map_systems else "",
                }
            }
        else:
            return self._section_prompt(session)

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        """處理回應"""
        session = _sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Phase 0: 命名
        if session.phase == 0:
            session.system_name = value
            session.phase = 1
            session.state = "writing"
            session.current_section = 1
            session.updated_at = datetime.now().isoformat()
            return self._section_prompt(session)

        # Phase 1-N: 撰寫段落
        if session.state == "writing":
            if value == "next":
                session.completed_sections.append(session.current_section)
                session.current_section += 1
                session.updated_at = datetime.now().isoformat()

                if session.current_section > 8:
                    session.state = "complete"
                    session.final_document = self._generate_document(session)
                    return self._completion_response(session)
                return self._section_prompt(session)

            elif value == "skip":
                session.current_section += 1
                session.updated_at = datetime.now().isoformat()
                if session.current_section > 8:
                    session.state = "complete"
                    session.final_document = self._generate_document(session)
                    return self._completion_response(session)
                return self._section_prompt(session)

            elif value == "back":
                if session.current_section > 1:
                    session.current_section -= 1
                session.updated_at = datetime.now().isoformat()
                return self._section_prompt(session)

            elif value == "jump":
                return {
                    "session_id": session_id,
                    "phase": session.phase,
                    "state": "jump_select",
                    "current_section": session.current_section,
                    "completed_sections": session.completed_sections,
                    "question": {
                        "id": "jump_target",
                        "text": f"跳轉到哪個段落？1-8\n{chr(10).join([f'{k}. {v['name']}' for k,v in GDD_SECTIONS.items()])}",
                        "type": "number"
                    }
                }

            elif value.isdigit() and session.state == "jump_select":
                target = int(value)
                if 1 <= target <= 8:
                    session.current_section = target
                    session.state = "writing"
                    session.updated_at = datetime.now().isoformat()
                    return self._section_prompt(session)

            else:
                # 儲存答案
                section = session.current_section
                if section not in session.section_answers:
                    session.section_answers[section] = {}
                session.section_answers[section][field] = value
                session.updated_at = datetime.now().isoformat()

                # 檢查是否所有 prompt 都回答了
                prompts = GDD_SECTIONS[section]["prompts"]
                answered = len(session.section_answers.get(section, {}))
                if answered >= len(prompts):
                    return {
                        "session_id": session_id,
                        "phase": session.phase,
                        "state": "section_review",
                        "current_section": section,
                        "section_name": GDD_SECTIONS[section]["name"],
                        "all_answered": True,
                        "answers": session.section_answers[section],
                        "preview": self._preview_section(session, section),
                        "question": {
                            "id": "section_action",
                            "text": f"段落 {section}: {GDD_SECTIONS[section]['name']} 已填寫完成。輸入 'next' 繼續下一段，或 'back' 回去修改",
                            "options": [
                                {"value": "next", "label": "➡️ 下一段落"},
                                {"value": "back", "label": "⬅️ 上一段落"},
                                {"value": "jump", "label": "🔀 跳轉段落"},
                            ]
                        }
                    }
                else:
                    # 還有 prompt 要回答
                    next_prompt_index = answered
                    return {
                        "session_id": session_id,
                        "phase": session.phase,
                        "state": "answering",
                        "current_section": section,
                        "section_name": GDD_SECTIONS[section]["name"],
                        "answered_count": answered,
                        "total_prompts": len(prompts),
                        "question": {
                            "id": f"prompt_{section}_{next_prompt_index}",
                            "text": f"📝 [{section}/8] {GDD_SECTIONS[section]['name']}\n\n{GDD_SECTIONS[section]['prompts'][next_prompt_index]}",
                            "type": "textarea"
                        }
                    }

        # Complete
        if session.state == "complete":
            if value == "save":
                return self.finalize(session)
            return self._completion_response(session)

        return {"error": "Unknown state"}

    def _section_prompt(self, session: DesignSystemSession) -> dict:
        section = GDD_SECTIONS[session.current_section]
        return {
            "session_id": session.session_id,
            "phase": session.phase,
            "state": "answering",
            "current_section": session.current_section,
            "total_sections": 8,
            "section_name": section["name"],
            "section_icon": section["icon"],
            "section_desc": section["desc"],
            "completed_sections": session.completed_sections,
            "progress": f"{len(session.completed_sections)}/8",
            "question": {
                "id": f"prompt_{session.current_section}_0",
                "text": f"📝 [{session.current_section}/8] {section['icon']} {section['name']}\n\n{section['desc']}\n\n{section['prompts'][0]}",
                "type": "textarea"
            }
        }

    def _preview_section(self, session: DesignSystemSession, section_num: int) -> str:
        section = GDD_SECTIONS[section_num]
        answers = session.section_answers.get(section_num, {})
        template = section["template"]
        for i, prompt in enumerate(section["prompts"]):
            answer_key = f"prompt_{section_num}_{i}"
            answer = answers.get(answer_key, answers.get(str(i), "（未填寫）"))
            placeholder = "{" + prompt + "}"
            # 找模板中的佔位符並替換
            for key, val in {
                "一句話定義": answers.get(f"prompt_{section_num}_0", ""),
                "為什麼需要這個系統": answers.get(f"prompt_{section_num}_1", ""),
                "在整體遊戲中的地位": answers.get(f"prompt_{section_num}_2", ""),
                "玩家如何互動": answers.get(f"prompt_{section_num}_0", ""),
                "規則與公式": answers.get(f"prompt_{section_num}_1", ""),
                "輸入": answers.get(f"prompt_{section_num}_2", "").split("，")[0] if answers.get(f"prompt_{section_num}_2") else "",
                "輸出": answers.get(f"prompt_{section_num}_2", "").split("，")[-1] if answers.get(f"prompt_{section_num}_2") else "",
                "新手體驗": answers.get(f"prompt_{section_num}_0", ""),
                "進階使用": answers.get(f"prompt_{section_num}_1", ""),
                "頻率": answers.get(f"prompt_{section_num}_2", ""),
                "狀態清單": answers.get(f"prompt_{section_num}_0", ""),
                "狀態轉換事件": answers.get(f"prompt_{section_num}_1", ""),
                "過渡動畫/回饋": answers.get(f"prompt_{section_num}_2", ""),
                "資料欄位定義": answers.get(f"prompt_{section_num}_0", ""),
                "儲存/載入策略": answers.get(f"prompt_{section_num}_1", ""),
                "平衡考量": answers.get(f"prompt_{section_num}_2", ""),
                "異常處理": answers.get(f"prompt_{section_num}_0", ""),
                "邊界條件": answers.get(f"prompt_{section_num}_1", ""),
                "錯誤恢復策略": answers.get(f"prompt_{section_num}_2", ""),
                "依賴的系統": answers.get(f"prompt_{section_num}_0", ""),
                "被哪些系統依賴": answers.get(f"prompt_{section_num}_1", ""),
                "交換的資料": answers.get(f"prompt_{section_num}_2", ""),
                "關鍵指標": answers.get(f"prompt_{section_num}_0", ""),
                "成功定義": answers.get(f"prompt_{section_num}_1", ""),
                "滿意度指標": answers.get(f"prompt_{section_num}_2", ""),
            }.items():
                template = template.replace("{" + key + "}", val)

        return template

    def _generate_document(self, session: DesignSystemSession) -> str:
        lines = []
        lines.append(f"# 🎮 {session.system_name} — Game Design Document\n")
        lines.append(f"**產生時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        for i in range(1, 9):
            section = GDD_SECTIONS[i]
            if i in session.section_answers:
                preview = self._preview_section(session, i)
                lines.append(preview)
                lines.append("")
            else:
                lines.append(section["template"])
                lines.append("")

        return "\n".join(lines)

    def _completion_response(self, session: DesignSystemSession) -> dict:
        return {
            "session_id": session.session_id,
            "phase": session.phase,
            "state": "complete",
            "system_name": session.system_name,
            "completed_sections": session.completed_sections,
            "progress": f"{len(session.completed_sections)}/8",
            "document": session.final_document,
            "question": {
                "id": "save_or_done",
                "text": f"🎉 {session.system_name} GDD 完成！輸入 'save' 儲存文件",
                "options": [
                    {"value": "save", "label": "💾 儲存 GDD"},
                    {"value": "done", "label": "✅ 完成"},
                ]
            }
        }

    def get_session(self, session_id: str) -> Optional[DesignSystemSession]:
        return _sessions.get(session_id)

    def finalize(self, session: DesignSystemSession, output_dir: str = "") -> dict:
        if not session.final_document:
            session.final_document = self._generate_document(session)

        saved_path = None
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            safe_name = session.system_name.replace(" ", "_").replace("/", "_")
            doc_path = out_path / f"GDD_{safe_name}.md"
            doc_path.write_text(session.final_document, encoding='utf-8')
            saved_path = str(doc_path)

        return {
            "session_id": session.session_id,
            "state": "complete",
            "system_name": session.system_name,
            "saved_path": saved_path,
            "document": session.final_document,
        }


design_system_skill = DesignSystemSkill()
