"""
sprint_plan_skill.py — /sprint-plan (Phase 4.7)
CCGS 移植：Sprint 規劃 — 建立 Sprint 待辦清單與容量規劃
"""

from datetime import datetime


class SprintPlanSession:
    def __init__(self, session_id, stories=None):
        self.session_id = session_id
        self.stories = stories or []
        self.state = "init"
        self.sprint_duration_days = 14
        self.team_capacity = 0
        self.sprints = []  # list of {name, stories, goal}
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "sprints_count": len(self.sprints),
            "total_stories": len(self.stories),
        }


SESSIONS = {}


def handle_init(session_id="default", stories=None, story_count=0):
    session = SprintPlanSession(session_id, stories)
    SESSIONS[session_id] = session
    session.state = "capacity"

    return {
        "session_id": session_id,
        "state": "capacity",
        "prompt": f"📊 **Sprint 規劃開始**\n\n現有 {story_count or len(stories or [])} 個 Stories。\n\n請設定：\n1. Sprint 長度（天，預設 14）\n2. 團隊每 Sprint 容量（Story Points，例如 30）\n\n格式：天數, 容量（例如：14, 30）",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "capacity":
        parts = value.replace(' ', '').split(',')
        if len(parts) >= 2:
            try:
                session.sprint_duration_days = int(parts[0])
                session.team_capacity = int(parts[1])
            except ValueError:
                return {"error": "格式錯誤。請使用：天數, 容量（例如：14, 30）"}
        else:
            return {"error": "格式錯誤。請使用：天數, 容量"}

        session.state = "sprint_goal"
        return {
            "state": "sprint_goal",
            "sprint_index": 1,
            "sprint_duration": session.sprint_duration_days,
            "capacity": session.team_capacity,
            "prompt": f"🎯 Sprint 1 目標（Sprint 長度: {session.sprint_duration_days}天, 容量: {session.team_capacity} SP）\n\n請描述 Sprint 1 的目標：",
        }

    elif session.state == "sprint_goal":
        goal = value
        session.sprints.append({
            "name": f"Sprint {len(session.sprints) + 1}",
            "goal": goal,
            "stories": [],
        })

        session.state = "sprint_stories"
        return {
            "state": "sprint_stories",
            "sprint_index": len(session.sprints),
            "prompt": "📝 請列出此 Sprint 要包含的 Stories（每行一個 Story 標題）：",
        }

    elif session.state == "sprint_stories":
        story_list = [line.strip() for line in value.split('\n') if line.strip()]
        session.sprints[-1]["stories"] = story_list

        return {
            "state": "sprint_done",
            "sprint_index": len(session.sprints),
            "goal": session.sprints[-1]["goal"],
            "stories": story_list,
            "prompt": f"✅ Sprint {len(session.sprints)} 完成！\n\n➡️ 輸入 'next' 建立下一個 Sprint，或輸入 'done' 完成所有 Sprint 規劃。",
        }

    elif session.state == "sprint_done":
        if value.lower() == 'done':
            session.state = "complete"
            return {
                "state": "complete",
                "total_sprints": len(session.sprints),
                "message": "✅ Sprint 規劃完成！呼叫 /save 儲存。",
            }
        elif value.lower() == 'next':
            session.state = "sprint_goal"
            return {
                "state": "sprint_goal",
                "sprint_index": len(session.sprints) + 1,
                "prompt": f"🎯 Sprint {len(session.sprints) + 1} 目標：",
            }
        else:
            return {"error": "請輸入 'next' 或 'done'"}

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# Sprint Plan", f"建立時間：{session.created_at}", ""]
    lines.append(f"- Sprint 長度：{session.sprint_duration_days} 天")
    lines.append(f"- 團隊容量：{session.team_capacity} SP/Sprint")
    lines.append(f"- 總 Sprint 數：{len(session.sprints)}")

    for i, sprint in enumerate(session.sprints):
        lines.append(f"\n## {sprint['name']}")
        lines.append(f"**目標**: {sprint['goal']}")
        lines.append(f"**Stories** ({len(sprint['stories'])}):")
        for s in sprint['stories']:
            lines.append(f"- [ ] {s}")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "sprint-plan.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


sprint_plan_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
})()
