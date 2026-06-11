"""
ux_review_skill.py — /ux-review (Phase 4.3)
CCGS 移植：UX 啟發式評估（10 項 Nielsen 啟發式 + 遊戲特定檢查）
"""

HEURISTICS = [
    {"id": 1, "name": "Visibility of System Status", "name_zh": "系統狀態可見性", "desc": "系統是否總是在合理時間內提供適當回饋"},
    {"id": 2, "name": "Match Between System and Real World", "name_zh": "系統與真實世界的匹配", "desc": "是否使用玩家熟悉的語言和概念"},
    {"id": 3, "name": "User Control and Freedom", "name_zh": "使用者控制與自由", "desc": "玩家是否能輕鬆撤銷/重做操作"},
    {"id": 4, "name": "Consistency and Standards", "name_zh": "一致性與標準", "desc": "UI/UX 模式是否保持一致"},
    {"id": 5, "name": "Error Prevention", "name_zh": "錯誤預防", "desc": "是否有防止玩家犯錯的設計"},
    {"id": 6, "name": "Recognition Rather Than Recall", "name_zh": "辨識而非回憶", "desc": "選項是否可見，不需要玩家記憶"},
    {"id": 7, "name": "Flexibility and Efficiency of Use", "name_zh": "使用彈性與效率", "desc": "是否支援快捷鍵/巨集等進階使用"},
    {"id": 8, "name": "Aesthetic and Minimalist Design", "name_zh": "美學與極簡設計", "desc": "UI 是否簡潔，不包含無關資訊"},
    {"id": 9, "name": "Help Users Recognize, Diagnose, and Recover", "name_zh": "錯誤識別與恢復", "desc": "錯誤訊息是否清晰且有解決方案"},
    {"id": 10, "name": "Help and Documentation", "name_zh": "說明與文件", "desc": "是否有適當的教學/幫助系統"},
]

GAME_HEURISTICS = [
    {"id": "g1", "name": "Onboarding Experience", "name_zh": "新手引導", "desc": "新玩家能否在 5 分鐘內理解核心玩法"},
    {"id": "g2", "name": "Flow State", "name_zh": "心流狀態", "desc": "難度曲線是否維持挑戰與技能的平衡"},
    {"id": "g3", "name": "Diegetic UI", "name_zh": "場景內 UI", "desc": "UI 元素是否融入遊戲世界"},
    {"id": "g4", "name": "Input Responsiveness", "name_zh": "輸入反應", "desc": "操作延遲是否 < 100ms"},
    {"id": "g5", "name": "Tutorial Pacing", "name_zh": "教學節奏", "desc": "教學是否分散在遊戲過程中而非一次性灌輸"},
]

VERDICTS = ["APPROVE", "CONCERNS", "MAJOR_REVISION"]


class UXReviewSession:
    def __init__(self, session_id, ux_doc=""):
        self.session_id = session_id
        self.ux_doc = ux_doc
        self.state = "init"
        self.current_index = 0
        self.scores = {}
        self.notes = {}
        self.verdict = ""

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "current_index": self.current_index,
            "scored": len(self.scores),
            "total_heuristics": len(HEURISTICS) + len(GAME_HEURISTICS),
            "verdict": self.verdict,
        }


SESSIONS = {}


def handle_init(session_id="default", ux_doc=""):
    session = UXReviewSession(session_id, ux_doc)
    SESSIONS[session_id] = session
    session.state = "reviewing"

    h = HEURISTICS[0]
    return {
        "session_id": session_id,
        "state": "reviewing",
        "current": h,
        "progress": "0/15",
        "prompt": f"🔍 [{h['id']}/10] **{h['name_zh']}** — {h['desc']}\n\n評分（1-5）：",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "reviewing":
        all_items = HEURISTICS + GAME_HEURISTICS
        current = all_items[session.current_index]

        if field == "score":
            session.scores[str(current["id"])] = int(value)
        elif field == "notes":
            session.notes[str(current["id"])] = value
        else:
            session.scores[str(current["id"])] = int(value) if value.isdigit() else 3
            session.notes[str(current["id"])] = ""

        session.current_index += 1
        if session.current_index < len(all_items):
            nxt = all_items[session.current_index]
            return {
                "state": "reviewing",
                "current": nxt,
                "progress": f"{session.current_index}/{len(all_items)}",
                "prompt": f"🔍 [{nxt['id']}] **{nxt['name_zh']}** — {nxt['desc']}\n\n評分（1-5）：",
            }
        else:
            session.state = "verdict"
            avg = sum(session.scores.values()) / len(session.scores) if session.scores else 0
            suggested = "APPROVE" if avg >= 4 else ("CONCERNS" if avg >= 2.5 else "MAJOR_REVISION")
            return {
                "state": "verdict",
                "average_score": round(avg, 1),
                "suggested_verdict": suggested,
                "available_verdicts": VERDICTS,
                "scores_detail": {
                    "nielsen": {k: v for k, v in session.scores.items() if k.isdigit()},
                    "game": {k: v for k, v in session.scores.items() if not k.isdigit()},
                },
                "prompt": f"📊 綜合評分：{avg:.1f}/5\n建議裁決：{suggested}\n\n請選擇最終裁決：{', '.join(VERDICTS)}",
            }

    elif session.state == "verdict":
        session.verdict = value
        session.state = "complete"
        avg = sum(session.scores.values()) / len(session.scores) if session.scores else 0
        return {
            "state": "complete",
            "verdict": session.verdict,
            "average_score": round(avg, 1),
            "message": "✅ UX 審查完成！",
        }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    lines = ["# UX Review Report", "", f"## 審查結果：{session.verdict}", ""]
    avg = sum(session.scores.values()) / len(session.scores) if session.scores else 0
    lines.append(f"平均分數：{avg:.1f}/5")
    lines.append("")

    lines.append("## Nielsen 啟發式評估")
    for h in HEURISTICS:
        score = session.scores.get(str(h["id"]), "N/A")
        note = session.notes.get(str(h["id"]), "")
        lines.append(f"- [{score}/5] **{h['name_zh']}** — {note}" if note else f"- [{score}/5] **{h['name_zh']}**")

    lines.append("")
    lines.append("## 遊戲特定評估")
    for h in GAME_HEURISTICS:
        score = session.scores.get(str(h["id"]), "N/A")
        note = session.notes.get(str(h["id"]), "")
        lines.append(f"- [{score}/5] **{h['name_zh']}** — {note}" if note else f"- [{score}/5] **{h['name_zh']}**")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "ux-review.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


ux_review_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'HEURISTICS': HEURISTICS,
    'GAME_HEURISTICS': GAME_HEURISTICS,
})()
