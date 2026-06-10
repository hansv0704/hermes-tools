"""
prototype_skill.py — /prototype (Phase 4.4)
CCGS 移植：原型規劃（目標/範圍/工具/時程/驗收標準）
"""

from datetime import datetime


PROTOTYPE_TYPES = [
    {"id": "paper", "name": "紙本原型", "icon": "📄", "desc": "紙筆素描、桌遊模擬核心機制"},
    {"id": "graybox", "name": "灰盒原型", "icon": "📦", "desc": "無美術的基礎幾何體遊戲流程"},
    {"id": "vertical", "name": "垂直切片", "icon": "🎯", "desc": "單一功能點完整實現"},
    {"id": "horizontal", "name": "水平切片", "icon": "📐", "desc": "完整系統但功能較淺"},
    {"id": "tech", "name": "技術驗證", "icon": "🔬", "desc": "驗證特定技術可行性"},
    {"id": "experience", "name": "體驗原型", "icon": "🎮", "desc": "驗證核心感受與 fun factor"},
]

PROTOTYPE_PHASES = [
    {"id": 1, "name": "目標定義", "desc": "這個原型要驗證什麼假設？"},
    {"id": 2, "name": "範圍界定", "desc": "明確的 in/out scope"},
    {"id": 3, "name": "工具選擇", "desc": "使用什麼工具？Godot/紙筆/其他？"},
    {"id": 4, "name": "時程規劃", "desc": "預估時間與里程碑"},
    {"id": 5, "name": "驗收標準", "desc": "如何判斷原型成功？"},
]


class PrototypeSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = "init"
        self.phase = 1
        self.goal = ""
        self.scope = ""
        self.tools = ""
        self.timeline = ""
        self.success_criteria = ""
        self.prototype_type = ""
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "phase": self.phase,
            "goal": self.goal[:80] if self.goal else "",
        }


SESSIONS = {}


def handle_init(session_id="default"):
    session = PrototypeSession(session_id)
    SESSIONS[session_id] = session
    session.state = "goal"

    return {
        "session_id": session_id,
        "state": "goal",
        "prototype_types": PROTOTYPE_TYPES,
        "prompt": "🎯 Phase 1：**目標定義**\n這個原型要驗證什麼假設？（例如：「驗證核心戰鬥循環是否在 3 分鐘內讓玩家感到滿足」）",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "goal":
        session.goal = value
        session.state = "scope"
        session.phase = 2
        return {
            "state": "scope",
            "prompt": "📋 Phase 2：**範圍界定**\n\nIn Scope（要做）：\nOut of Scope（不做）：\n\n請分別列出：",
        }

    elif session.state == "scope":
        session.scope = value
        session.state = "tools"
        session.phase = 3
        return {
            "state": "tools",
            "prototype_types": PROTOTYPE_TYPES,
            "prompt": "🔧 Phase 3：**工具選擇**\n\n請選擇原型類型 + 工具：\n" + "\n".join(
                [f"- {t['icon']} **{t['name']}** — {t['desc']}" for t in PROTOTYPE_TYPES]
            ),
        }

    elif session.state == "tools":
        session.tools = value
        session.state = "timeline"
        session.phase = 4
        return {
            "state": "timeline",
            "prompt": "📅 Phase 4：**時程規劃**\n\n預估時間？里程碑？（例如：Day 1-2 灰盒搭建 / Day 3 核心機制 / Day 4-5 測試迭代）",
        }

    elif session.state == "timeline":
        session.timeline = value
        session.state = "criteria"
        session.phase = 5
        return {
            "state": "criteria",
            "prompt": "✅ Phase 5：**驗收標準**\n\n如何判斷原型成功？（例如：「10 位測試者中 7 位表示想繼續玩」）",
        }

    elif session.state == "criteria":
        session.success_criteria = value
        session.state = "complete"
        return {
            "state": "complete",
            "summary": {
                "goal": session.goal[:100],
                "tools": session.tools[:100],
                "timeline": session.timeline[:100],
            },
            "message": "✅ 原型規劃完成！呼叫 /save 儲存 prototype-plan.md",
        }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# Prototype Plan", f"建立時間：{session.created_at}", ""]
    lines.append(f"## 目標")
    lines.append(session.goal)
    lines.append("")
    lines.append(f"## 範圍")
    lines.append(session.scope)
    lines.append("")
    lines.append(f"## 工具")
    lines.append(session.tools)
    lines.append("")
    lines.append(f"## 時程")
    lines.append(session.timeline)
    lines.append("")
    lines.append(f"## 驗收標準")
    lines.append(session.success_criteria)

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "prototype-plan.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


prototype_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'TYPES': PROTOTYPE_TYPES,
})()
