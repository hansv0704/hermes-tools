"""
create_epics_skill.py — /create-epics (Phase 4.5)
CCGS 移植：Epic 分解 — 從系統地圖生成 Epic 並分解為 Story
"""

from datetime import datetime


EPIC_TEMPLATE = {
    "title": "",
    "goal": "",
    "user_value": "",
    "scope": "",
    "stories": [],
    "dependencies": [],
    "acceptance_criteria": [],
}


class EpicSession:
    def __init__(self, session_id, systems_map=None):
        self.session_id = session_id
        self.systems_map = systems_map or {}
        self.state = "init"
        self.epics = []  # list of EPIC_TEMPLATE
        self.current_epic_index = 0
        self.field_index = 0
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "epics_count": len(self.epics),
            "current_epic": self.current_epic_index,
        }


EPIC_FIELDS = ["title", "goal", "user_value", "scope", "stories", "dependencies", "acceptance_criteria"]
EPIC_FIELD_PROMPTS = {
    "title": "📌 Epic 標題（例如：Player Combat System）",
    "goal": "🎯 Epic 目標（這個 Epic 要達成什麼？）",
    "user_value": "👤 使用者價值（玩家能得到什麼？）",
    "scope": "📋 範圍（In/Out of scope）",
    "stories": "📝 User Stories（每行一個，格式：As a [role], I want [feature], so that [benefit]）",
    "dependencies": "🔗 依賴（這個 Epic 依賴哪些其他系統/Epic？）",
    "acceptance_criteria": "✅ 驗收標準（每行一個可測試的條件）",
}

SESSIONS = {}


def handle_init(session_id="default", systems_map=None):
    session = EpicSession(session_id, systems_map)
    SESSIONS[session_id] = session
    session.state = "collecting"

    # 建立第一個 epic 模板
    session.epics.append(dict(EPIC_TEMPLATE))
    prompt = EPIC_FIELD_PROMPTS["title"]

    system_names = list(systems_map.keys()) if systems_map else []
    hint = f"\n\n系統清單：{', '.join(system_names)}" if system_names else ""

    return {
        "session_id": session_id,
        "state": "collecting",
        "epic_index": 0,
        "field": "title",
        "prompt": prompt + hint,
        "available_systems": system_names,
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "collecting":
        epic = session.epics[session.current_epic_index]
        current_field = EPIC_FIELDS[session.field_index]

        if current_field in ["stories", "dependencies", "acceptance_criteria"]:
            epic[current_field] = [line.strip() for line in value.split('\n') if line.strip()]
        else:
            epic[current_field] = value

        session.field_index += 1

        if session.field_index < len(EPIC_FIELDS):
            next_field = EPIC_FIELDS[session.field_index]
            return {
                "state": "collecting",
                "epic_index": session.current_epic_index,
                "field": next_field,
                "progress": f"Epic {session.current_epic_index + 1} | {session.field_index}/{len(EPIC_FIELDS)}",
                "prompt": EPIC_FIELD_PROMPTS[next_field],
            }
        else:
            # 當前 epic 完成
            session.field_index = 0
            return {
                "state": "epic_complete",
                "epic_index": session.current_epic_index,
                "completed_epic": {k: v for k, v in epic.items() if v},
                "prompt": "✅ 此 Epic 完成！\n\n➡️ 輸入 'next' 建立下一個 Epic，或輸入 'done' 完成。",
            }

    elif session.state == "epic_complete":
        if value.lower() == 'done':
            session.state = "complete"
            return {
                "state": "complete",
                "total_epics": len(session.epics),
                "message": "✅ 所有 Epic 建立完成！呼叫 /save 儲存。",
            }
        elif value.lower() == 'next':
            session.epics.append(dict(EPIC_TEMPLATE))
            session.current_epic_index += 1
            session.state = "collecting"
            return {
                "state": "collecting",
                "epic_index": session.current_epic_index,
                "field": "title",
                "prompt": EPIC_FIELD_PROMPTS["title"] + f"\n\nEpic #{session.current_epic_index + 1}",
            }
        else:
            return {"error": "請輸入 'next' 或 'done'"}

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# Epic Breakdown", f"建立時間：{session.created_at}", "", f"共 {len(session.epics)} 個 Epic", ""]

    for i, epic in enumerate(session.epics):
        lines.append(f"## Epic {i + 1}: {epic.get('title', 'Untitled')}")
        lines.append(f"**目標**: {epic.get('goal', '')}")
        lines.append(f"**使用者價值**: {epic.get('user_value', '')}")
        lines.append(f"**範圍**: {epic.get('scope', '')}")
        lines.append("")
        if epic.get('stories'):
            lines.append("### User Stories")
            for s in epic['stories']:
                lines.append(f"- {s}")
        lines.append("")
        if epic.get('dependencies'):
            lines.append("### 依賴")
            for d in epic['dependencies']:
                lines.append(f"- {d}")
        lines.append("")
        if epic.get('acceptance_criteria'):
            lines.append("### 驗收標準")
            for c in epic['acceptance_criteria']:
                lines.append(f"- [ ] {c}")
        lines.append("\n---\n")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "epics.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


create_epics_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'FIELDS': EPIC_FIELDS,
})()
