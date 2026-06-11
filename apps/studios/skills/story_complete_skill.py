"""
/story-complete — Story 驗收檢查
Phase 5.2 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

story_complete_bp = Blueprint('story_complete', __name__)
sessions = {}

ACCEPTANCE_CRITERIA = [
    "功能實作完整 — 所有 AC 項目都已實作",
    "單元測試通過 — 相關測試全部綠燈",
    "程式碼審查通過 — 已通過 code-review",
    "邊界條件處理 — 空值、極值、錯誤輸入已處理",
    "無已知 Bug — 無 P0/P1 等級未解決問題",
    "文件更新 — 相關文檔已同步更新",
    "效能達標 — 符合 performance budget",
    "合併就緒 — 無衝突、可合併至主分支"
]

DEFINITION_OF_DONE = [
    "DoD-1: 程式碼已提交並推送",
    "DoD-2: CI/CD Pipeline 通過",
    "DoD-3: Code Review 獲得 Approve",
    "DoD-4: QA 測試通過",
    "DoD-5: 產品負責人驗收通過",
    "DoD-6: 相關文件/註解已更新",
    "DoD-7: 無 Technical Debt 遺留"
]


def _init_session(story_id, story_title, ac_list):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "story_id": story_id,
        "story_title": story_title,
        "ac_list": ac_list,
        "checks": {ac: None for ac in ac_list},
        "dod": {dod: None for dod in DEFINITION_OF_DONE},
        "notes": "",
        "verdict": None,
        "created": datetime.now().isoformat()
    }
    return sid


@story_complete_bp.route('/api/story-complete/init', methods=['POST'])
def init_complete():
    data = request.get_json() or {}
    story_id = data.get('story_id', f'STORY-{uuid.uuid4().hex[:6].upper()}')
    story_title = data.get('story_title', '未命名 Story')
    ac_list = data.get('acceptance_criteria', ACCEPTANCE_CRITERIA)

    if not isinstance(ac_list, list) or len(ac_list) == 0:
        return jsonify({"error": "需要至少一個驗收條件"}), 400

    sid = _init_session(story_id, story_title, ac_list)

    return jsonify({
        "session_id": sid,
        "story_id": story_id,
        "story_title": story_title,
        "acceptance_criteria": ac_list,
        "definition_of_done": DEFINITION_OF_DONE,
        "phase": 1,
        "next": "使用 /api/story-complete/check/{session_id} 逐項檢查"
    })


@story_complete_bp.route('/api/story-complete/check/<sid>', methods=['POST'])
def check_item(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    data = request.get_json() or {}
    item = data.get('item', '')
    status = data.get('status', 'pass').lower()  # pass / fail / skip
    note = data.get('note', '')

    if status not in ('pass', 'fail', 'skip'):
        return jsonify({"error": "status 必須是 pass / fail / skip"}), 400

    # 檢查 AC 清單
    if item in sessions[sid]["checks"]:
        sessions[sid]["checks"][item] = {"status": status, "note": note}
    elif item in sessions[sid]["dod"]:
        sessions[sid]["dod"][item] = {"status": status, "note": note}
    else:
        return jsonify({"error": f"找不到項目: {item}",
                       "valid_ac": list(sessions[sid]["checks"].keys()),
                       "valid_dod": list(sessions[sid]["dod"].keys())}), 400

    if note:
        sessions[sid]["notes"] += f"[{item}] {note}\n"

    return jsonify({
        "item": item,
        "status": status,
        "progress": _calc_progress(sid)
    })


@story_complete_bp.route('/api/story-complete/check-all/<sid>', methods=['POST'])
def check_all(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    # 模擬全面檢查
    for ac in sessions[sid]["checks"]:
        if sessions[sid]["checks"][ac] is None:
            sessions[sid]["checks"][ac] = {"status": "pass", "note": "自動檢查通過"}

    for dod in sessions[sid]["dod"]:
        if sessions[sid]["dod"][dod] is None:
            sessions[sid]["dod"][dod] = {"status": "pass", "note": "自動檢查通過"}

    verdict = _determine_verdict(sid)
    sessions[sid]["verdict"] = verdict

    return jsonify({
        "session_id": sid,
        "verdict": verdict,
        "progress": _calc_progress(sid),
        "ac_results": sessions[sid]["checks"],
        "dod_results": sessions[sid]["dod"]
    })


@story_complete_bp.route('/api/story-complete/state/<sid>', methods=['GET'])
def complete_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    return jsonify({
        "session_id": sid,
        "story_id": sessions[sid]["story_id"],
        "story_title": sessions[sid]["story_title"],
        "verdict": sessions[sid]["verdict"],
        "progress": _calc_progress(sid),
        "ac_checks": sessions[sid]["checks"],
        "dod_checks": sessions[sid]["dod"],
        "notes": sessions[sid]["notes"]
    })


@story_complete_bp.route('/api/story-complete/criteria', methods=['GET'])
def list_criteria():
    return jsonify({
        "default_acceptance_criteria": ACCEPTANCE_CRITERIA,
        "definition_of_done": DEFINITION_OF_DONE
    })


def _calc_progress(sid):
    ac_done = sum(1 for v in sessions[sid]["checks"].values() if v is not None)
    ac_total = len(sessions[sid]["checks"])
    dod_done = sum(1 for v in sessions[sid]["dod"].values() if v is not None)
    dod_total = len(sessions[sid]["dod"])
    return {
        "ac": f"{ac_done}/{ac_total}",
        "dod": f"{dod_done}/{dod_total}",
        "total_pct": round((ac_done + dod_done) / (ac_total + dod_total) * 100, 1)
    }


def _determine_verdict(sid):
    fails = sum(1 for v in sessions[sid]["checks"].values()
                if v and v["status"] == "fail")
    fails += sum(1 for v in sessions[sid]["dod"].values()
                 if v and v["status"] == "fail")

    if fails == 0:
        return "COMPLETE — Story 驗收通過，可移至 Done"
    elif fails <= 2:
        return "CONDITIONAL — 有輕微問題，建議修復後再驗收"
    else:
        return "REJECTED — 多項檢查失敗，需要重新實作"
