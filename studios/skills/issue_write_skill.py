"""
/issue-write — 9 欄位 Issue 建立
Phase 5.7 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

issue_write_bp = Blueprint('issue_write', __name__)
sessions = {}

ISSUE_TYPES = ["bug", "feature", "enhancement", "task", "documentation", "technical_debt"]

ISSUE_PRIORITIES = [
    "P0 - Critical (阻擋發佈)",
    "P1 - High (必須修復)",
    "P2 - Medium (建議修復)",
    "P3 - Low (Nice to have)"
]

ISSUE_FIELDS = [
    {"id": "title", "name": "標題 Title", "required": True,
     "prompt": "簡潔描述問題（50 字內）"},
    {"id": "type", "name": "類型 Type", "required": True,
     "prompt": f"類型：{' / '.join(ISSUE_TYPES)}"},
    {"id": "priority", "name": "優先級 Priority", "required": True,
     "prompt": "P0 / P1 / P2 / P3"},
    {"id": "description", "name": "描述 Description", "required": True,
     "prompt": "詳細描述問題或需求"},
    {"id": "steps", "name": "重現步驟 Steps to Reproduce", "required": False,
     "prompt": "Bug 重現步驟（僅 bug 類型需要）"},
    {"id": "expected", "name": "預期行為 Expected Behavior", "required": False,
     "prompt": "應該發生什麼？"},
    {"id": "actual", "name": "實際行為 Actual Behavior", "required": False,
     "prompt": "實際發生了什麼？"},
    {"id": "environment", "name": "環境 Environment", "required": False,
     "prompt": "OS / Godot 版本 / 硬體規格"},
    {"id": "assignee", "name": "指派 Assignee", "required": False,
     "prompt": "負責人"}
]

STATUS_FLOW = ["open", "triaged", "in_progress", "in_review", "resolved", "closed"]


def _init_session():
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "issue": {f["id"]: None for f in ISSUE_FIELDS},
        "current_field": None,
        "status": "open",
        "created": datetime.now().isoformat()
    }
    return sid


@issue_write_bp.route('/api/issue-write/init', methods=['POST'])
def init_issue():
    data = request.get_json() or {}

    sid = _init_session()

    # 預填
    if data.get('title'):
        sessions[sid]["issue"]["title"] = data['title']
    if data.get('type'):
        sessions[sid]["issue"]["type"] = data['type']
    if data.get('priority'):
        sessions[sid]["issue"]["priority"] = data['priority']
    if data.get('description'):
        sessions[sid]["issue"]["description"] = data['description']

    return jsonify({
        "session_id": sid,
        "fields": ISSUE_FIELDS,
        "types": ISSUE_TYPES,
        "priorities": ISSUE_PRIORITIES,
        "status_flow": STATUS_FLOW,
        "current_issue": sessions[sid]["issue"],
        "phase": 1,
        "next": "使用 /api/issue-write/field/{session_id}/{field_id} 填寫欄位"
    })


@issue_write_bp.route('/api/issue-write/field/<sid>/<field_id>', methods=['POST'])
def set_field(sid, field_id):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    field = next((f for f in ISSUE_FIELDS if f["id"] == field_id), None)
    if not field:
        return jsonify({"error": f"無效的欄位: {field_id}",
                       "valid": [f["id"] for f in ISSUE_FIELDS]}), 400

    data = request.get_json() or {}
    value = data.get('value', '')

    # 驗證
    if field_id == "type" and value not in ISSUE_TYPES:
        return jsonify({"error": f"無效的類型: {value}", "valid": ISSUE_TYPES}), 400

    sessions[sid]["issue"][field_id] = value
    sessions[sid]["current_field"] = field_id

    filled = sum(1 for v in sessions[sid]["issue"].values() if v is not None)
    required_filled = sum(1 for f in ISSUE_FIELDS
                         if f["required"] and sessions[sid]["issue"][f["id"]])

    return jsonify({
        "field": field_id,
        "value": value,
        "progress": f"{filled}/{len(ISSUE_FIELDS)} 欄位",
        "required_complete": required_filled == sum(1 for f in ISSUE_FIELDS if f["required"])
    })


@issue_write_bp.route('/api/issue-write/submit/<sid>', methods=['POST'])
def submit_issue(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    # 檢查必要欄位
    missing = [f["name"] for f in ISSUE_FIELDS
               if f["required"] and not sessions[sid]["issue"][f["id"]]]

    if missing:
        return jsonify({
            "error": f"缺少必要欄位: {', '.join(missing)}",
            "missing_fields": missing
        }), 400

    issue_id = f"ISSUE-{uuid.uuid4().hex[:6].upper()}"
    sessions[sid]["status"] = "triaged"

    return jsonify({
        "issue_id": issue_id,
        "status": "triaged",
        "issue": sessions[sid]["issue"],
        "created": sessions[sid]["created"]
    })


@issue_write_bp.route('/api/issue-write/state/<sid>', methods=['GET'])
def issue_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    return jsonify({
        "session_id": sid,
        "status": sessions[sid]["status"],
        "issue": sessions[sid]["issue"],
        "current_field": sessions[sid]["current_field"]
    })


@issue_write_bp.route('/api/issue-write/fields', methods=['GET'])
def list_fields():
    return jsonify({
        "fields": ISSUE_FIELDS,
        "types": ISSUE_TYPES,
        "priorities": ISSUE_PRIORITIES,
        "status_flow": STATUS_FLOW
    })
