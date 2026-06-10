"""
/playtest — 9 段落試玩文件
Phase 5.6 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

playtest_bp = Blueprint('playtest', __name__)
sessions = {}

PLAYTEST_SECTIONS = [
    {
        "id": "objectives",
        "title": "🎯 試玩目標",
        "prompt": "這次試玩要驗證什麼？核心 loop？難度曲線？新功能？",
        "required": True
    },
    {
        "id": "build_info",
        "title": "📦 版本資訊",
        "prompt": "Build 版本號、平台、已知限制",
        "required": True
    },
    {
        "id": "testers",
        "title": "👥 測試者",
        "prompt": "測試者背景、遊戲經驗（新手/核心玩家/開發者）",
        "required": True
    },
    {
        "id": "setup",
        "title": "🔧 測試環境",
        "prompt": "設備規格、作業系統、螢幕解析度、控制器類型",
        "required": False
    },
    {
        "id": "script",
        "title": "📜 測試腳本",
        "prompt": "測試者要執行的具體任務清單（Task 1, 2, 3...）",
        "required": True
    },
    {
        "id": "observation",
        "title": "👁️ 觀察重點",
        "prompt": "要特別注意的行為：卡關點、困惑表情、口頭抱怨、驚喜反應",
        "required": False
    },
    {
        "id": "survey",
        "title": "📋 試玩問卷",
        "prompt": "試玩後要填寫的問卷題目（1-5 評分 + 開放式問題）",
        "required": True
    },
    {
        "id": "metrics",
        "title": "📊 量化指標",
        "prompt": "通關時間、死亡次數、使用的道具/技能、完成率",
        "required": False
    },
    {
        "id": "report",
        "title": "📝 試玩報告",
        "prompt": "彙整所有回饋、關鍵發現、優先改善項目",
        "required": True
    }
]

DEFAULT_SURVEY = [
    "整體樂趣度 (1-5)",
    "操作流暢度 (1-5)",
    "難度適中嗎？(太簡單 1-5 太難)",
    "最喜歡的部分？",
    "最困惑的部分？",
    "任何建議？"
]


def _init_session(game_name, build_version):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "game_name": game_name,
        "build_version": build_version,
        "sections": {s["id"]: "" for s in PLAYTEST_SECTIONS},
        "current_section": None,
        "observations": [],
        "survey_results": {},
        "created": datetime.now().isoformat()
    }
    return sid


@playtest_bp.route('/api/playtest/init', methods=['POST'])
def init_playtest():
    data = request.get_json() or {}
    game_name = data.get('game_name', '未命名遊戲')
    build_version = data.get('build_version', '0.1.0-alpha')

    sid = _init_session(game_name, build_version)

    return jsonify({
        "session_id": sid,
        "game_name": game_name,
        "build_version": build_version,
        "sections": PLAYTEST_SECTIONS,
        "default_survey": DEFAULT_SURVEY,
        "phase": 1,
        "next": "使用 /api/playtest/section/{session_id}/{section_id} 填寫各段落"
    })


@playtest_bp.route('/api/playtest/section/<sid>/<section_id>', methods=['POST'])
def write_section(sid, section_id):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    valid = [s["id"] for s in PLAYTEST_SECTIONS]
    if section_id not in valid:
        return jsonify({"error": f"無效的段落: {section_id}", "valid": valid}), 400

    data = request.get_json() or {}
    content = data.get('content', '')

    sessions[sid]["sections"][section_id] = content
    sessions[sid]["current_section"] = section_id

    filled = sum(1 for v in sessions[sid]["sections"].values() if v)
    total = len(PLAYTEST_SECTIONS)

    return jsonify({
        "section": section_id,
        "progress": f"{filled}/{total} 段落完成"
    })


@playtest_bp.route('/api/playtest/observation/<sid>', methods=['POST'])
def add_observation(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    data = request.get_json() or {}
    obs = {
        "timestamp": data.get('timestamp', datetime.now().isoformat()),
        "tester": data.get('tester', 'Anonymous'),
        "type": data.get('type', 'note'),  # positive / negative / confusion / bug / note
        "description": data.get('description', ''),
        "severity": data.get('severity', 'medium')  # low / medium / high / critical
    }

    sessions[sid]["observations"].append(obs)

    return jsonify({
        "observation": obs,
        "total_observations": len(sessions[sid]["observations"])
    })


@playtest_bp.route('/api/playtest/survey/<sid>', methods=['POST'])
def submit_survey(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    data = request.get_json() or {}
    tester = data.get('tester', 'Anonymous')
    responses = data.get('responses', {})

    sessions[sid]["survey_results"][tester] = responses

    return jsonify({
        "tester": tester,
        "responses": responses,
        "total_surveys": len(sessions[sid]["survey_results"])
    })


@playtest_bp.route('/api/playtest/state/<sid>', methods=['GET'])
def playtest_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    filled = sum(1 for v in sessions[sid]["sections"].values() if v)
    required_filled = sum(1 for s in PLAYTEST_SECTIONS
                         if s["required"] and sessions[sid]["sections"][s["id"]])

    return jsonify({
        "session_id": sid,
        "game_name": sessions[sid]["game_name"],
        "build_version": sessions[sid]["build_version"],
        "sections_completed": f"{filled}/{len(PLAYTEST_SECTIONS)}",
        "required_completed": f"{required_filled}/{sum(1 for s in PLAYTEST_SECTIONS if s['required'])}",
        "observations_count": len(sessions[sid]["observations"]),
        "survey_count": len(sessions[sid]["survey_results"]),
        "sections": sessions[sid]["sections"],
        "observations": sessions[sid]["observations"],
        "survey_results": sessions[sid]["survey_results"]
    })
