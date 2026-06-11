"""
ux_design_skill.py — /ux-design (Phase 4.2)
CCGS 移植：UX 設計文件（10 段落互動式寫作）
"""

from datetime import datetime


UX_SECTIONS = [
    {"id": 0, "name": "Overview", "icon": "📋", "desc": "系統概述、UX 願景、目標受眾"},
    {"id": 1, "name": "User Personas", "icon": "👤", "desc": "1-3 個使用者角色（動機/痛點/目標）"},
    {"id": 2, "name": "User Flows", "icon": "🔄", "desc": "核心使用者流程（登入→大廳→遊戲→結算）"},
    {"id": 3, "name": "Screen Layouts", "icon": "📱", "desc": "主要畫面佈局（wireframe 文字描述）"},
    {"id": 4, "name": "Navigation", "icon": "🧭", "desc": "導航架構（選單層級/快捷鍵/手把支援）"},
    {"id": 5, "name": "Interaction Patterns", "icon": "👆", "desc": "互動模式（點擊/拖曳/手勢/快捷鍵）"},
    {"id": 6, "name": "Feedback & Affordance", "icon": "💬", "desc": "回饋機制（視覺/音效/觸覺回饋）"},
    {"id": 7, "name": "Accessibility", "icon": "♿", "desc": "無障礙設計（色盲/字體大小/控制器重新映射）"},
    {"id": 8, "name": "Edge Cases", "icon": "⚠️", "desc": "邊界情況（載入失敗/離線/儲存損壞）"},
    {"id": 9, "name": "Metrics & Success", "icon": "📊", "desc": "UX 成功指標（完成率/時間/錯誤率）"},
]


class UXDesignSession:
    def __init__(self, session_id, system_name=""):
        self.session_id = session_id
        self.system_name = system_name
        self.state = "writing"
        self.current_section = 0
        self.sections = {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "system_name": self.system_name,
            "current_section": self.current_section,
            "completed_sections": len(self.sections),
            "total_sections": len(UX_SECTIONS),
        }


SESSIONS = {}


def handle_init(session_id="default", system_name="", from_context=None):
    session = UXDesignSession(session_id, system_name)
    SESSIONS[session_id] = session

    section = UX_SECTIONS[0]
    return {
        "session_id": session_id,
        "section": section,
        "progress": "0/10",
        "prompt": f"📋 {section['icon']} **{section['name']}**：{section['desc']}\n\n請描述此系統的 UX 概觀。",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "writing":
        session.sections[str(session.current_section)] = value
        session.current_section += 1
        session.updated_at = datetime.now().isoformat()

        if session.current_section < len(UX_SECTIONS):
            section = UX_SECTIONS[session.current_section]
            return {
                "state": "writing",
                "section": section,
                "progress": f"{session.current_section}/{len(UX_SECTIONS)}",
                "prompt": f"{section['icon']} **{section['name']}**：{section['desc']}\n\n請提供內容：",
            }
        else:
            session.state = "complete"
            return {
                "state": "complete",
                "message": "✅ UX 設計文件完成！呼叫 /save 儲存。",
                "summary": {
                    "sections_completed": len(session.sections),
                    "system_name": session.system_name,
                },
            }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = [f"# UX Design: {session.system_name or 'System'}", f"建立時間：{session.created_at}", ""]

    for sec in UX_SECTIONS:
        content = session.sections.get(str(sec["id"]), "")
        if content:
            lines.append(f"## {sec['icon']} {sec['name']}")
            lines.append(content)
            lines.append("")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        name_slug = session.system_name.replace(" ", "_").lower() if session.system_name else "system"
        doc_path = out_path / f"ux-design-{name_slug}.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


ux_design_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'SECTIONS': UX_SECTIONS,
})()
