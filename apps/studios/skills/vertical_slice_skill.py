"""
vertical_slice_skill.py — /vertical-slice (Phase 4.9)
CCGS 移植：垂直切片規劃 — 定義並規劃一個可展示的垂直切片
"""

from datetime import datetime


VERTICAL_SLICE_PHASES = [
    {"id": 1, "name": "目標定義", "desc": "這個垂直切片要展示什麼？"},
    {"id": 2, "name": "範圍界定", "desc": "明確的內容範圍（時長/系統/資產）"},
    {"id": 3, "name": "系統清單", "desc": "垂直切片涉及的所有系統"},
    {"id": 4, "name": "資產需求", "desc": "需要的所有資產（美術/音訊/VFX）"},
    {"id": 5, "name": "時程規劃", "desc": "開發里程碑與截止日期"},
    {"id": 6, "name": "展示腳本", "desc": "Demo 的具體流程與腳本"},
    {"id": 7, "name": "驗收標準", "desc": "如何判斷垂直切片成功？"},
]

SLICE_TYPES = [
    {"id": "gameplay", "name": "核心玩法垂直切片", "icon": "🎮", "desc": "展示核心遊戲循環的完整片段（5-15 分鐘）"},
    {"id": "narrative", "name": "敘事垂直切片", "icon": "📖", "desc": "展示故事/對話系統的完整場景"},
    {"id": "technical", "name": "技術垂直切片", "icon": "⚡", "desc": "展示特定技術亮點（如破壞系統、物理引擎）"},
    {"id": "polish", "name": "拋光垂直切片", "icon": "✨", "desc": "接近最終品質的展示片段（用於發行商 Demo）"},
]


class VerticalSliceSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = "init"
        self.phase = 1
        self.goal = ""
        self.slice_type = ""
        self.scope = ""
        self.systems = []
        self.assets = []
        self.timeline = ""
        self.script = ""
        self.success_criteria = ""
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
    session = VerticalSliceSession(session_id)
    SESSIONS[session_id] = session
    session.state = "goal"

    return {
        "session_id": session_id,
        "slice_types": SLICE_TYPES,
        "phases": VERTICAL_SLICE_PHASES,
        "prompt": f"🎯 Phase 1：**目標定義**\n\n垂直切片類型：\n" + "\n".join(
            [f"- {t['icon']} **{t['name']}** — {t['desc']}" for t in SLICE_TYPES]
        ) + "\n\n請選擇類型並描述目標（例如：gameplay | 展示從探索→戰鬥→獎勵的完整 10 分鐘循環）",
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
            "prompt": "📋 Phase 2：**範圍界定**\n\n- 垂直切片時長？（例如：10 分鐘）\n- 包含哪些內容？\n- 明確排除哪些內容？",
        }

    elif session.state == "scope":
        session.scope = value
        session.state = "systems"
        session.phase = 3
        return {
            "state": "systems",
            "prompt": "⚙️ Phase 3：**系統清單**\n\n這個垂直切片涉及哪些系統？（每行一個）",
        }

    elif session.state == "systems":
        session.systems = [line.strip() for line in value.split('\n') if line.strip()]
        session.state = "assets"
        session.phase = 4
        return {
            "state": "assets",
            "prompt": "🎨 Phase 4：**資產需求**\n\n需要的資產清單（美術/音訊/VFX，每行一個）：",
        }

    elif session.state == "assets":
        session.assets = [line.strip() for line in value.split('\n') if line.strip()]
        session.state = "timeline"
        session.phase = 5
        return {
            "state": "timeline",
            "prompt": "📅 Phase 5：**時程規劃**\n\n開發里程碑與截止日期（例如：\nWeek 1: 灰盒搭建\nWeek 2: 系統整合\nWeek 3: 美術導入\nWeek 4: 測試與打磨）",
        }

    elif session.state == "timeline":
        session.timeline = value
        session.state = "script"
        session.phase = 6
        return {
            "state": "script",
            "prompt": "📜 Phase 6：**展示腳本**\n\nDemo 的具體流程。從觀眾看到的第一個畫面開始描述，逐步到結束。\n\n提示：包含玩家操作、劇情觸發、UI 引導、高潮時刻。",
        }

    elif session.state == "script":
        session.script = value
        session.state = "criteria"
        session.phase = 7
        return {
            "state": "criteria",
            "prompt": "✅ Phase 7：**驗收標準**\n\n如何判斷垂直切片成功？（例如：\n- Demo 全程無崩潰\n- 幀率穩定 >30fps\n- 測試觀眾理解核心玩法\n- 關鍵時刻有情感反應）",
        }

    elif session.state == "criteria":
        session.success_criteria = value
        session.state = "complete"
        return {
            "state": "complete",
            "summary": {
                "goal": session.goal[:100],
                "systems_count": len(session.systems),
                "assets_count": len(session.assets),
                "phases_completed": 7,
            },
            "message": "✅ 垂直切片規劃完成！呼叫 /save 儲存 vertical-slice.md",
        }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# Vertical Slice Plan", f"建立時間：{session.created_at}", ""]
    lines.append(f"## 目標")
    lines.append(session.goal)
    lines.append("")
    lines.append(f"## 範圍")
    lines.append(session.scope)
    lines.append("")
    lines.append(f"## 系統清單 ({len(session.systems)})")
    for s in session.systems:
        lines.append(f"- {s}")
    lines.append("")
    lines.append(f"## 資產需求 ({len(session.assets)})")
    for a in session.assets:
        lines.append(f"- {a}")
    lines.append("")
    lines.append(f"## 時程規劃")
    lines.append(session.timeline)
    lines.append("")
    lines.append(f"## 展示腳本")
    lines.append(session.script)
    lines.append("")
    lines.append(f"## 驗收標準")
    lines.append(session.success_criteria)

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "vertical-slice.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


vertical_slice_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'PHASES': VERTICAL_SLICE_PHASES,
    'TYPES': SLICE_TYPES,
})()
