"""
gate_check_skill.py — /gate-check (Phase 4.8)
CCGS 移植：階段閘門審查 — 在進入下一個 Phase 前檢查所有交付物
"""

from datetime import datetime


GATE_CHECKS = {
    1: {  # Concept → Systems Design
        "name": "Concept Gate",
        "required": ["game-concept.md", "核心循環定義", "目標受眾"],
        "optional": ["靈感 moodboard", "市場分析"],
        "reviewer": "Creative Director",
    },
    2: {  # Systems Design → Technical Setup
        "name": "Design Gate",
        "required": ["GDD 文件", "系統地圖", "設計審查報告"],
        "optional": ["prototype 結果", "玩家測試回饋"],
        "reviewer": "Lead Designer",
    },
    3: {  # Technical Setup → Pre-Production
        "name": "Architecture Gate",
        "required": ["architecture.md", "所有 ADR", "CONTROL_MANIFEST.md", "ART_BIBLE.md"],
        "optional": ["技術原型", "效能基準"],
        "reviewer": "Tech Lead",
    },
    4: {  # Pre-Production → Production
        "name": "Pre-Production Gate",
        "required": ["asset-spec.md", "UX design docs", "prototype-plan.md", "epics.md", "vertical-slice.md"],
        "optional": ["sprint-plan.md"],
        "reviewer": "Producer",
    },
    5: {  # Production → Polish
        "name": "Production Gate",
        "required": ["所有 Stories 完成", "程式碼審查通過", "整合測試"],
        "optional": ["性能基準測試"],
        "reviewer": "QA Lead",
    },
    6: {  # Polish → Release
        "name": "Polish Gate",
        "required": ["性能達標", "平衡報告", "資產審計", "試玩回饋"],
        "optional": ["在地化完成"],
        "reviewer": "Director",
    },
    7: {  # Release
        "name": "Release Gate",
        "required": ["發布清單", "變更日誌", "Day-1 Patch 準備"],
        "optional": ["行銷素材"],
        "reviewer": "Publisher",
    },
}


class GateCheckSession:
    def __init__(self, session_id, from_phase=1, to_phase=2):
        self.session_id = session_id
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.state = "init"
        self.checks = {}  # item → pass/fail/na
        self.notes = {}
        self.verdict = ""
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "state": self.state,
            "verdict": self.verdict,
        }


SESSIONS = {}


def handle_init(session_id="default", from_phase=1, to_phase=2):
    session = GateCheckSession(session_id, from_phase, to_phase)
    SESSIONS[session_id] = session

    gate = GATE_CHECKS.get(from_phase, GATE_CHECKS[1])
    all_items = gate["required"] + gate["optional"]
    session.state = "checking"
    session.current_index = 0

    return {
        "session_id": session_id,
        "gate_name": gate["name"],
        "reviewer": gate["reviewer"],
        "from_phase": from_phase,
        "to_phase": to_phase,
        "items": all_items,
        "current_item": all_items[0] if all_items else "N/A",
        "prompt": f"🚪 **{gate['name']}** — Phase {from_phase} → {to_phase}\n審查者：{gate['reviewer']}\n\n檢查項目：{all_items[0]}\n\n狀態？(pass/fail/na)",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "checking":
        gate = GATE_CHECKS.get(session.from_phase, GATE_CHECKS[1])
        all_items = gate["required"] + gate["optional"]
        item = all_items[session.current_index]

        result = value.strip().lower()
        if result in ['pass', 'fail', 'na']:
            session.checks[item] = result
        else:
            session.checks[item] = 'fail'
            session.notes[item] = value

        session.current_index += 1

        if session.current_index < len(all_items):
            nxt = all_items[session.current_index]
            is_required = nxt in gate["required"]
            label = "🔴 必要" if is_required else "🟡 選用"
            return {
                "state": "checking",
                "current_item": nxt,
                "required": is_required,
                "progress": f"{session.current_index}/{len(all_items)}",
                "prompt": f"{label}：{nxt}\n\n狀態？(pass/fail/na)",
            }
        else:
            session.state = "verdict"
            required_fails = [k for k, v in session.checks.items() if v == 'fail' and k in gate["required"]]
            can_pass = len(required_fails) == 0
            suggested = "APPROVE" if can_pass else "REJECT"

            return {
                "state": "verdict",
                "checks": session.checks,
                "required_fails": required_fails,
                "required_pass": can_pass,
                "suggested_verdict": suggested,
                "prompt": f"📋 檢查完成。必要項目{'全數通過 ✅' if can_pass else '有未通過 ❌'}。\n建議裁決：{suggested}\n\n請確認最終裁決（APPROVE / CONDITIONAL / REJECT）：",
            }

    elif session.state == "verdict":
        session.verdict = value.upper()
        session.state = "complete"

        return {
            "state": "complete",
            "verdict": session.verdict,
            "message": "✅ 閘門審查完成！",
        }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def finalize(session, output_dir=""):
    gate = GATE_CHECKS.get(session.from_phase, GATE_CHECKS[1])

    lines = ["# Gate Check Report", f"建立時間：{session.created_at}", ""]
    lines.append(f"## {gate['name']}")
    lines.append(f"- Phase {session.from_phase} → {session.to_phase}")
    lines.append(f"- 審查者：{gate['reviewer']}")
    lines.append(f"- 裁決：**{session.verdict}**")
    lines.append("")

    lines.append("## 必要項目")
    for item in gate["required"]:
        status = session.checks.get(item, "N/A")
        icon = "✅" if status == "pass" else ("❌" if status == "fail" else "⬜")
        lines.append(f"- {icon} {item}")

    lines.append("")
    lines.append("## 選用項目")
    for item in gate.get("optional", []):
        status = session.checks.get(item, "N/A")
        icon = "✅" if status == "pass" else ("❌" if status == "fail" else "⬜")
        lines.append(f"- {icon} {item}")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / f"gate-check-phase{session.from_phase}.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path}


gate_check_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'GATES': GATE_CHECKS,
})()
