"""
/sprint-retro — 5 段落 Sprint 回顧
Phase 5.3 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

sprint_retro_bp = Blueprint('sprint_retro', __name__)
sessions = {}

RETRO_SECTIONS = [
    {
        "id": "what_went_well",
        "title": "🙂 做得好 — What Went Well",
        "prompt": "這個 Sprint 有哪些做得好的地方？技術突破、團隊協作、流程改善...",
        "examples": ["成功引入 CI/CD", "Code Review 品質提升", "Bug 數量下降 30%"]
    },
    {
        "id": "what_went_wrong",
        "title": "🙁 待改善 — What Went Wrong",
        "prompt": "遇到了哪些困難或挫折？技術債、溝通問題、時程延誤...",
        "examples": ["估算不準導致加班", "API 文件未同步更新", "Code Review 積壓"]
    },
    {
        "id": "learned",
        "title": "📚 學到什麼 — Lessons Learned",
        "prompt": "從這次 Sprint 學到了什麼技術或流程上的教訓？",
        "examples": ["使用新框架的心得", "更準確的 Story Point 估算方法"]
    },
    {
        "id": "action_items",
        "title": "✅ 行動項目 — Action Items",
        "prompt": "下個 Sprint 要執行的改善行動，需具體、可衡量、有負責人",
        "examples": ["每週三進行 Tech Debt 清理 2hr", "引入自動化測試覆蓋率報告"]
    },
    {
        "id": "kudos",
        "title": "🌟 讚美牆 — Kudos",
        "prompt": "特別感謝團隊成員的貢獻或互相讚美",
        "examples": ["感謝 @Alice 自動化部署讓發佈時間減半"]
    }
]

RETRO_ACTIONS = [
    {"id": "start", "title": "開始做 — Start Doing", "description": "下個 Sprint 要開始的新實踐"},
    {"id": "stop", "title": "停止做 — Stop Doing", "description": "沒有效果、該停止的習慣"},
    {"id": "continue", "title": "繼續做 — Continue Doing", "description": "有效果、應該保持的好習慣"},
    {"id": "more", "title": "多做 — Do More", "description": "效果很好，應該投入更多"},
    {"id": "less", "title": "少做 — Do Less", "description": "效果有限，應該減少投入"}
]


def _init_session(sprint_name, team_size):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "sprint_name": sprint_name,
        "team_size": team_size,
        "sections": {s["id"]: "" for s in RETRO_SECTIONS},
        "actions": {a["id"]: [] for a in RETRO_ACTIONS},
        "current_section": None,
        "mood_score": None,
        "velocity": None,
        "completed_stories": 0,
        "total_stories": 0,
        "created": datetime.now().isoformat()
    }
    return sid


@sprint_retro_bp.route('/api/sprint-retro/init', methods=['POST'])
def init_retro():
    data = request.get_json() or {}
    sprint_name = data.get('sprint_name', f'Sprint-{datetime.now().strftime("%Y%m%d")}')
    team_size = data.get('team_size', 1)

    sid = _init_session(sprint_name, team_size)

    return jsonify({
        "session_id": sid,
        "sprint_name": sprint_name,
        "sections": RETRO_SECTIONS,
        "action_categories": RETRO_ACTIONS,
        "phase": 1,
        "next": "使用 /api/sprint-retro/section/{session_id}/{section_id} 填寫各段落"
    })


@sprint_retro_bp.route('/api/sprint-retro/section/<sid>/<section_id>', methods=['POST'])
def write_section(sid, section_id):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    valid_sections = [s["id"] for s in RETRO_SECTIONS]
    if section_id not in valid_sections:
        return jsonify({"error": f"無效的段落: {section_id}", "valid": valid_sections}), 400

    data = request.get_json() or {}
    content = data.get('content', '')

    sessions[sid]["sections"][section_id] = content
    sessions[sid]["current_section"] = section_id

    filled = sum(1 for v in sessions[sid]["sections"].values() if v)
    total = len(RETRO_SECTIONS)

    return jsonify({
        "section": section_id,
        "content_length": len(content),
        "progress": f"{filled}/{total} 段落完成"
    })


@sprint_retro_bp.route('/api/sprint-retro/action/<sid>/<action_id>', methods=['POST'])
def add_action(sid, action_id):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    valid = [a["id"] for a in RETRO_ACTIONS]
    if action_id not in valid:
        return jsonify({"error": f"無效的行動類別: {action_id}", "valid": valid}), 400

    data = request.get_json() or {}
    item = data.get('item', '')

    if item:
        sessions[sid]["actions"][action_id].append(item)

    return jsonify({
        "action_category": action_id,
        "items": sessions[sid]["actions"][action_id]
    })


@sprint_retro_bp.route('/api/sprint-retro/complete/<sid>', methods=['POST'])
def complete_retro(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    data = request.get_json() or {}
    sessions[sid]["mood_score"] = data.get('mood_score', 7)
    sessions[sid]["velocity"] = data.get('velocity', 0)
    sessions[sid]["completed_stories"] = data.get('completed_stories', 0)
    sessions[sid]["total_stories"] = data.get('total_stories', 0)

    return jsonify({
        "session_id": sid,
        "sprint_name": sessions[sid]["sprint_name"],
        "sections": sessions[sid]["sections"],
        "actions": sessions[sid]["actions"],
        "mood_score": sessions[sid]["mood_score"],
        "velocity": sessions[sid]["velocity"],
        "completion_rate": f"{sessions[sid]['completed_stories']}/{sessions[sid]['total_stories']}",
        "summary": "Sprint Retro 完成，已儲存"
    })


@sprint_retro_bp.route('/api/sprint-retro/state/<sid>', methods=['GET'])
def retro_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    filled = sum(1 for v in sessions[sid]["sections"].values() if v)
    return jsonify({
        "session_id": sid,
        "sprint_name": sessions[sid]["sprint_name"],
        "mood_score": sessions[sid]["mood_score"],
        "velocity": sessions[sid]["velocity"],
        "sections_completed": f"{filled}/{len(RETRO_SECTIONS)}",
        "sections": sessions[sid]["sections"],
        "actions": sessions[sid]["actions"]
    })
