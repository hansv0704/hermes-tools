"""
/code-review — 5 維度程式碼審查
Phase 5.1 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
import json
from datetime import datetime

code_review_bp = Blueprint('code_review', __name__)
sessions = {}

DIMENSIONS = {
    "correctness": "正確性 — 邏輯是否正確、邊界條件處理",
    "performance": "效能 — CPU/記憶體/GC 壓力、瓶頸分析",
    "maintainability": "可維護性 — 命名、模組化、重複程式碼",
    "security": "安全性 — 注入、權限、敏感資料暴露",
    "godot_best": "Godot 最佳實踐 — 訊號使用、節點結構、資源管理"
}

REVIEW_PROMPTS = {
    "correctness": "請審查以下程式碼的邏輯正確性，包含邊界條件、null 檢查、型別安全：",
    "performance": "請審查以下程式碼的效能，包含 CPU 使用、記憶體配置、GC 壓力、瓶頸熱點：",
    "maintainability": "請審查以下程式碼的可維護性，包含命名、模組化、重複程式碼、註解品質：",
    "security": "請審查以下程式碼的安全性，包含注入攻擊、權限檢查、敏感資料暴露：",
    "godot_best": "請審查以下 Godot GDScript 的最佳實踐，包含訊號使用、節點結構、資源管理："
}


def _init_session(code, language="gdscript"):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "code": code,
        "language": language,
        "results": {},
        "current_dimension": None,
        "created": datetime.now().isoformat()
    }
    return sid


def _review_dimension(code, dim, language):
    """模擬 LLM 審查回傳結構化結果"""
    lines = code.strip().split('\n')
    line_count = len(lines)

    # 啟發式分析
    findings = []
    score = 8

    if dim == "correctness":
        if "pass" in code.lower() and "return" not in code.lower():
            findings.append({"severity": "medium", "line": "N/A",
                           "message": "可能有未處理的 pass 陳述式"})
            score -= 1
        if "null" not in code.lower() and "if " in code.lower():
            findings.append({"severity": "low", "line": "N/A",
                           "message": "建議增加 null 檢查"})
    elif dim == "performance":
        if "for " in code.lower() and "for " in code.lower().count("for") > 3:
            findings.append({"severity": "medium", "line": "N/A",
                           "message": "多層巢狀迴圈可能造成效能瓶頸"})
            score -= 1
    elif dim == "maintainability":
        if line_count > 100:
            findings.append({"severity": "low", "line": "N/A",
                           "message": f"檔案過長 ({line_count} 行)，建議拆分模組"})
            score -= 1
    elif dim == "security":
        if "password" in code.lower() or "token" in code.lower():
            findings.append({"severity": "high", "line": "N/A",
                           "message": "偵測到敏感字串，確保使用環境變數"})
            score -= 2
    elif dim == "godot_best":
        if "get_node(" in code and "@onready" not in code:
            findings.append({"severity": "low", "line": "N/A",
                           "message": "建議使用 @onready var 快取 get_node()"})
            score -= 1

    if not findings:
        findings.append({"severity": "info", "line": "N/A",
                        "message": "此維度未發現明顯問題"})

    return {
        "dimension": dim,
        "score": max(1, min(10, score)),
        "findings": findings,
        "suggestion": DIMENSIONS[dim].split("—")[-1].strip()
    }


@code_review_bp.route('/api/code-review/init', methods=['POST'])
def init_review():
    data = request.get_json() or {}
    code = data.get('code', '')
    language = data.get('language', 'gdscript')

    if not code.strip():
        return jsonify({"error": "需要提供程式碼內容"}), 400

    sid = _init_session(code, language)
    return jsonify({
        "session_id": sid,
        "dimensions": list(DIMENSIONS.keys()),
        "dimension_descriptions": DIMENSIONS,
        "code_lines": len(code.strip().split('\n')),
        "phase": 1,
        "next": "使用 /api/code-review/review/{session_id}/{dimension} 逐維度審查"
    })


@code_review_bp.route('/api/code-review/review/<sid>/<dimension>', methods=['POST'])
def review_dimension(sid, dimension):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    if dimension not in DIMENSIONS:
        return jsonify({"error": f"無效的維度: {dimension}", "valid": list(DIMENSIONS.keys())}), 400

    result = _review_dimension(
        sessions[sid]["code"],
        dimension,
        sessions[sid]["language"]
    )
    sessions[sid]["results"][dimension] = result
    sessions[sid]["current_dimension"] = dimension

    reviewed = len(sessions[sid]["results"])
    total = len(DIMENSIONS)

    return jsonify({
        **result,
        "progress": f"{reviewed}/{total} 維度完成",
        "remaining": [d for d in DIMENSIONS if d not in sessions[sid]["results"]]
    })


@code_review_bp.route('/api/code-review/review-all/<sid>', methods=['POST'])
def review_all(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    for dim in DIMENSIONS:
        if dim not in sessions[sid]["results"]:
            sessions[sid]["results"][dim] = _review_dimension(
                sessions[sid]["code"], dim, sessions[sid]["language"]
            )

    avg_score = sum(r["score"] for r in sessions[sid]["results"].values()) / len(DIMENSIONS)

    return jsonify({
        "session_id": sid,
        "average_score": round(avg_score, 1),
        "verdict": "APPROVE" if avg_score >= 7 else "CONCERNS" if avg_score >= 5 else "MAJOR_REVISION",
        "results": sessions[sid]["results"],
        "total_findings": sum(len(r["findings"]) for r in sessions[sid]["results"].values())
    })


@code_review_bp.route('/api/code-review/state/<sid>', methods=['GET'])
def review_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    return jsonify({
        "session_id": sid,
        "language": sessions[sid]["language"],
        "code_lines": len(sessions[sid]["code"].strip().split('\n')),
        "reviewed_dimensions": list(sessions[sid]["results"].keys()),
        "pending_dimensions": [d for d in DIMENSIONS if d not in sessions[sid]["results"]],
        "results": sessions[sid]["results"]
    })


@code_review_bp.route('/api/code-review/dimensions', methods=['GET'])
def list_dimensions():
    return jsonify({"dimensions": DIMENSIONS})
