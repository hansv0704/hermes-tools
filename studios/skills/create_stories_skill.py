"""
create_stories_skill.py — /create-stories (Phase 4.6)
CCGS 移植：User Story 寫作 — 從 Epic 生成可執行的使用者故事
"""

from datetime import datetime


STORY_PRIORITIES = ["P0 - Critical", "P1 - High", "P2 - Medium", "P3 - Low"]
STORY_POINTS = ["1", "2", "3", "5", "8", "13", "21"]
STORY_FIELDS = ["title", "as_a", "want", "so_that", "priority", "points", "acceptance_criteria", "notes"]


class StorySession:
    def __init__(self, session_id, epic_context=None):
        self.session_id = session_id
        self.epic_context = epic_context or {}
        self.state = "init"
        self.stories = []
        self.current_field = 0
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "stories_count": len(self.stories),
        }


FIELD_PROMPTS = {
    "title": "📌 Story 標題（簡潔描述）",
    "as_a": "👤 As a...（角色，例如：玩家、系統管理員）",
    "want": "🎯 I want...（想要的功能）",
    "so_that": "💡 So that...（帶來的價值）",
    "priority": f"⚡ 優先級：{' / '.join(STORY_PRIORITIES)}",
    "points": f"📏 Story Points：{' / '.join(STORY_POINTS)}",
    "acceptance_criteria": "✅ 驗收標準（每行一個，Given/When/Then 格式）",
    "notes": "📝 備註（技術注意事項/設計參考）",
}

SESSIONS = {}


def handle_init(session_id="default", epic_context=None):
    session = StorySession(session_id, epic_context)
    SESSIONS[session_id] = session
    session.state = "collecting"
    session.stories.append({f: "" for f in STORY_FIELDS})

    epic_name = epic_context.get("title", "") if epic_context else ""
    hint = f"\nEpic: {epic_name}" if epic_name else ""

    return {
        "session_id": session_id,
        "state": "collecting",
        "story_index": 0,
        "field": STORY_FIELDS[0],
        "prompt": FIELD_PROMPTS["title"] + hint,
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "collecting":
        story = session.stories[-1]
        current = STORY_FIELDS[session.current_field]

        if current == "acceptance_criteria":
            story[current] = [line.strip() for line in value.split('\n') if line.strip()]
        else:
            story[current] = value

        session.current_field += 1

        if session.current_field < len(STORY_FIELDS):
            nxt = STORY_FIELDS[session.current_field]
            return {
                "state": "collecting",
                "story_index": len(session.stories) - 1,
                "field": nxt,
                "progress": f"{session.current_field}/{len(STORY_FIELDS)}",
                "prompt": FIELD_PROMPTS[nxt],
            }
        else:
            session.current_field = 0
            session.state = "story_complete"
            return {
                "state": "story_complete",
                "completed_story": f"{story['title']} ({story.get('priority', 'N/A')})",
                "prompt": "✅ Story 完成！\n\n➡️ 輸入 'next' 建立下一個 Story，或輸入 'done' 完成。",
            }

    elif session.state == "story_complete":
        if value.lower() == 'done':
            session.state = "complete"
            return {
                "state": "complete",
                "total_stories": len(session.stories),
                "summary": "\n".join([f"- {s['title']} ({s.get('priority', 'N/A')})" for s in session.stories]),
                "message": "✅ 所有 Story 建立完成！",
            }
        elif value.lower() == 'next':
            session.stories.append({f: "" for f in STORY_FIELDS})
            session.state = "collecting"
            return {
                "state": "collecting",
                "story_index": len(session.stories) - 1,
                "field": STORY_FIELDS[0],
                "prompt": FIELD_PROMPTS["title"],
            }
        else:
            return {"error": "請輸入 'next' 或 'done'"}

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# User Stories", f"建立時間：{session.created_at}", "", f"共 {len(session.stories)} 個 Story", ""]

    for i, s in enumerate(session.stories):
        lines.append(f"## Story {i + 1}: {s.get('title', 'Untitled')}")
        lines.append(f"- **As a**: {s.get('as_a', '')}")
        lines.append(f"- **I want**: {s.get('want', '')}")
        lines.append(f"- **So that**: {s.get('so_that', '')}")
        lines.append(f"- **Priority**: {s.get('priority', '')}")
        lines.append(f"- **Points**: {s.get('points', '')}")
        if s.get('acceptance_criteria'):
            lines.append("- **Acceptance Criteria**:")
            for ac in s['acceptance_criteria']:
                lines.append(f"  - [ ] {ac}")
        if s.get('notes'):
            lines.append(f"- **Notes**: {s['notes']}")
        lines.append("")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "user-stories.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


create_stories_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'FIELDS': STORY_FIELDS,
    'PRIORITIES': STORY_PRIORITIES,
    'POINTS': STORY_POINTS,
})()
