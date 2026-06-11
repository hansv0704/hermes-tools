"""
Alice Game Studio — 主體 Flask 應用
Phase 1: Shell (專案管理 + 階段追蹤 + Web UI)
Port: 5003
"""

import os
import sys
import json
import threading
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

# ── Game Studio Skills ──
from studios.skills.start_skill import (
    detect_project_state,
    ONBOARDING_QUESTION,
    get_path_A, get_path_B, get_path_C, get_path_D,
    REVIEW_MODE_QUESTION,
    get_session, reset_session
)
from studios.skills.brainstorm_skill import brainstorm_skill
from studios.skills.setup_engine_skill import (
    detect_godot, scaffold_project, get_engine_setup_summary,
    NAMING_CONVENTIONS, PERFORMANCE_BUDGET
)
from studios.skills.project_stage_detect_skill import (
    deep_scan_project, get_project_overview, PHASE_GATES as PD_PHASE_GATES
)
from studios.godot_bridge import get_bridge, detect_and_report, GodotBridge

# ── Phase 2 Skills ──
from studios.skills.map_systems_skill import map_systems_skill, MAP_PHASES
from studios.skills.design_system_skill import design_system_skill, GDD_SECTIONS
from studios.skills.design_review_skill import design_review_skill
from studios.skills.review_all_gdds_skill import review_all_gdds_skill
from studios.skills.consistency_check_skill import consistency_check_skill

# ── Phase 3 Skills ──
from studios.skills.create_architecture_skill import CreateArchitectureSkill
from studios.skills.architecture_decision_skill import ArchitectureDecisionSkill
from studios.skills.architecture_review_skill import ArchitectureReviewSkill
from studios.skills.create_control_manifest_skill import CreateControlManifestSkill
from studios.skills.art_bible_skill import ArtBibleSkill

# ── Phase 4 Skills ──
from studios.skills.asset_spec_skill import asset_spec_skill, ASSET_CATEGORIES
from studios.skills.ux_design_skill import ux_design_skill, UX_SECTIONS
from studios.skills.ux_review_skill import ux_review_skill, HEURISTICS, GAME_HEURISTICS
from studios.skills.prototype_skill import prototype_skill, PROTOTYPE_TYPES
from studios.skills.create_epics_skill import create_epics_skill
from studios.skills.create_stories_skill import create_stories_skill
from studios.skills.sprint_plan_skill import sprint_plan_skill
from studios.skills.gate_check_skill import gate_check_skill, GATE_CHECKS
from studios.skills.vertical_slice_skill import vertical_slice_skill, VERTICAL_SLICE_PHASES, SLICE_TYPES

# ── Phase 5 Skills ──
from studios.skills.code_review_skill import code_review_bp
from studios.skills.story_complete_skill import story_complete_bp
from studios.skills.sprint_retro_skill import sprint_retro_bp
from studios.skills.implement_skill import implement_bp
from studios.skills.test_design_skill import test_design_bp
from studios.skills.playtest_skill import playtest_bp
from studios.skills.issue_write_skill import issue_write_bp

# ── Phase 6 Skills ──
from studios.skills.profiling_skill import ProfilingSkill
from studios.skills.balance_tuning_skill import BalanceTuningSkill
from studios.skills.asset_audit_skill import AssetAuditSkill
from studios.skills.accessibility_review_skill import AccessibilityReviewSkill
from studios.skills.polish_pass_skill import PolishPassSkill

# ── Phase 7 Skills ──
from studios.skills.release_checklist_skill import release_checklist_bp
from studios.skills.changelog_skill import changelog_bp
from studios.skills.post_launch_monitor_skill import post_launch_monitor_bp

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'templates'),
    static_folder=str(BASE_DIR / 'static')
)

# ── 7 Phase 定義 ──
PHASES = {
    1: {"name": "Concept", "slug": "concept", "icon": "💡",
        "desc": "創意發想、遊戲概念確立、核心循環設計"},
    2: {"name": "Systems Design", "slug": "systems-design", "icon": "📐",
        "desc": "系統拆解、GDD 寫作、設計審查"},
    3: {"name": "Technical Setup", "slug": "technical-setup", "icon": "🔧",
        "desc": "技術架構、ADR、控制清單、美術聖經"},
    4: {"name": "Pre-Production", "slug": "pre-production", "icon": "🏗️",
        "desc": "資產規格、UX 設計、原型、Epic/Story、垂直切片"},
    5: {"name": "Production", "slug": "production", "icon": "⚙️",
        "desc": "Story 實現、程式碼審查、Sprint 管理"},
    6: {"name": "Polish", "slug": "polish", "icon": "✨",
        "desc": "效能分析、平衡調整、資產審計、試玩"},
    7: {"name": "Release", "slug": "release", "icon": "🚀",
        "desc": "發布清單、變更日誌、Day-1 Patch"},
}

# ── 專案狀態儲存 ──
PROJECTS_FILE = BASE_DIR / 'projects.json'

def load_projects():
    if PROJECTS_FILE.exists():
        return json.loads(PROJECTS_FILE.read_text(encoding='utf-8'))
    return {"projects": [], "active_project": None}

def save_projects(data):
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# ── CORS ──
@app.after_request
def _add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# ═══════════════ 頁面路由 ═══════════════

@app.route('/')
def index():
    return render_template('index.html', phases=PHASES)

# ═══════════════ API：系統 ═══════════════

@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "tool": "Alice Game Studio",
        "version": "1.5.0",
        "port": 5003,
        "phases": len(PHASES),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/phases')
def api_phases():
    return jsonify({"status": "success", "phases": [
        {"id": k, **v} for k, v in PHASES.items()
    ]})

# ═══════════════ API：專案管理 ═══════════════

@app.route('/api/projects', methods=['GET'])
def api_projects():
    data = load_projects()
    return jsonify({"status": "success", **data})

@app.route('/api/projects', methods=['POST'])
def api_create_project():
    req = request.get_json() or {}
    name = req.get('name', '').strip()
    godot_path = req.get('godot_path', '').strip()
    genre = req.get('genre', '').strip()

    if not name:
        return jsonify({"status": "error", "message": "專案名稱不可為空"}), 400

    data = load_projects()
    project = {
        "id": datetime.now().strftime("proj_%Y%m%d_%H%M%S"),
        "name": name,
        "godot_path": godot_path,
        "genre": genre,
        "current_phase": 1,
        "phase_history": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    data["projects"].append(project)
    if len(data["projects"]) == 1:
        data["active_project"] = project["id"]
    save_projects(data)

    return jsonify({"status": "success", "project": project})

@app.route('/api/projects/<project_id>/activate', methods=['POST'])
def api_activate_project(project_id):
    data = load_projects()
    if project_id not in [p["id"] for p in data["projects"]]:
        return jsonify({"status": "error", "message": "專案不存在"}), 404
    data["active_project"] = project_id
    save_projects(data)
    return jsonify({"status": "success", "active_project": project_id})

@app.route('/api/projects/<project_id>/phase/<int:phase>', methods=['POST'])
def api_set_phase(project_id, phase):
    if phase not in PHASES:
        return jsonify({"status": "error", "message": f"Phase {phase} 不存在"}), 400

    data = load_projects()
    for p in data["projects"]:
        if p["id"] == project_id:
            p["phase_history"].append({
                "from": p["current_phase"],
                "to": phase,
                "timestamp": datetime.now().isoformat()
            })
            p["current_phase"] = phase
            p["updated_at"] = datetime.now().isoformat()
            save_projects(data)
            return jsonify({"status": "success", "project": p})

    return jsonify({"status": "error", "message": "專案不存在"}), 404

# ═══════════════ API：Godot 橋接 ═══════════════

@app.route('/api/godot/detect', methods=['GET'])
def api_godot_detect():
    """偵測系統中是否安裝 Godot"""
    import subprocess
    paths = []
    try:
        r = subprocess.run(["where", "godot"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.strip().split('\n'):
                if line.strip():
                    paths.append(line.strip())
    except:
        pass

    common = [
        "C:\\Program Files\\Godot\\Godot_v4.4-stable_win64.exe",
        "C:\\Godot\\Godot_v4.3-stable_win64.exe",
        "E:\\Godot_v4.5-stable_win64.exe",
        "E:\\Godot_v4.4-stable_win64.exe",
    ]
    for p in common:
        if os.path.exists(p) and p not in paths:
            paths.append(p)

    return jsonify({
        "status": "success",
        "found": len(paths) > 0,
        "paths": paths
    })

@app.route('/api/godot/version', methods=['POST'])
def api_godot_version():
    """查詢 Godot 版本"""
    req = request.get_json() or {}
    godot_path = req.get('path', 'godot')
    import subprocess
    try:
        r = subprocess.run([godot_path, "--version"], capture_output=True, text=True, timeout=10)
        return jsonify({"status": "success", "version": r.stdout.strip()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ═══════════════ API：Telegram 橋接 ═══════════════

@app.route('/api/telegram/webhook', methods=['POST'])
def api_telegram_webhook():
    """接收來自 Alice 的 Telegram 指令"""
    req = request.get_json() or {}
    command = req.get('command', '')
    args = req.get('args', {})
    return jsonify({
        "status": "received",
        "command": command,
        "note": "Telegram bridge active"
    })


# ═══════════════ API：/start 流程 (Phase 1.2) ═══════════════

@app.route('/api/start/init', methods=['POST'])
def api_start_init():
    """初始化 /start 流程。傳入 project_path 偵測階段，回傳 onboarding 問題"""
    req = request.get_json() or {}
    project_path = req.get('project_path', '')
    session_id = req.get('session_id', 'default')

    session = get_session(session_id)
    session.project_state = detect_project_state(project_path) if project_path else None
    session.state = "onboarding"
    session.updated_at = datetime.now().isoformat()

    return jsonify({
        "status": "success",
        "state": "onboarding",
        "project_state": session.project_state,
        "question": ONBOARDING_QUESTION
    })


@app.route('/api/start/respond', methods=['POST'])
def api_start_respond():
    """處理使用者對 /start 流程的回覆"""
    req = request.get_json() or {}
    session_id = req.get('session_id', 'default')
    answer = req.get('answer', '').upper()
    session = get_session(session_id)

    if session.state == "onboarding":
        if answer not in ['A', 'B', 'C', 'D']:
            return jsonify({"status": "error", "message": f"無效選項: {answer}。請選 A/B/C/D"}), 400

        session.onboarding_answer = answer
        path_map = {'A': get_path_A, 'B': get_path_B, 'C': get_path_C, 'D': get_path_D}
        session.selected_path = path_map[answer]()
        session.state = "path_selected"
        session.updated_at = datetime.now().isoformat()

        return jsonify({
            "status": "success",
            "state": "path_selected",
            "onboarding_answer": answer,
            "selected_path": session.selected_path,
            "next_question": REVIEW_MODE_QUESTION
        })

    elif session.state == "path_selected":
        if answer not in ['FULL', 'LEAN', 'SOLO']:
            return jsonify({"status": "error", "message": f"無效審查模式: {answer}。請選 full/lean/solo"}), 400

        session.review_mode = answer.lower()
        session.state = "complete"
        session.updated_at = datetime.now().isoformat()

        return jsonify({
            "status": "success",
            "state": "complete",
            "summary": {
                "onboarding_answer": session.onboarding_answer,
                "path": session.selected_path,
                "review_mode": session.review_mode,
                "project_state": session.project_state,
            },
            "message": f"✅ /start 完成！你選擇了 Path {session.onboarding_answer}，審查模式: {session.review_mode}。可以開始第一個 skill: {session.selected_path['steps'][0]['skill'] if session.selected_path['steps'] else '無'}"
        })

    else:
        return jsonify({"status": "error", "message": f"當前狀態 {session.state} 無法處理回覆"}), 400


@app.route('/api/start/state', methods=['GET'])
def api_start_state():
    """查詢當前 /start 流程狀態"""
    session_id = request.args.get('session_id', 'default')
    session = get_session(session_id)
    return jsonify({"status": "success", **session.to_dict()})


@app.route('/api/start/path/<path_id>', methods=['GET'])
def api_start_path(path_id):
    """取得指定路徑的詳細步驟"""
    path_map = {'A': get_path_A, 'B': get_path_B, 'C': get_path_C, 'D': get_path_D}
    if path_id.upper() not in path_map:
        return jsonify({"status": "error", "message": f"路徑 {path_id} 不存在"}), 404
    return jsonify({"status": "success", "path": path_map[path_id.upper()]()})


@app.route('/api/start/review-mode', methods=['POST'])
def api_start_review_mode():
    """單獨設定審查模式（可在流程外呼叫）"""
    req = request.get_json() or {}
    session_id = req.get('session_id', 'default')
    mode = req.get('mode', '').lower()
    if mode not in ['full', 'lean', 'solo']:
        return jsonify({"status": "error", "message": f"無效模式: {mode}"}), 400

    session = get_session(session_id)
    session.review_mode = mode
    session.updated_at = datetime.now().isoformat()
    return jsonify({"status": "success", "review_mode": mode})


# ═══════════════ API：/brainstorm 流程 (Phase 1.3) ═══════════════

BRAINSTORM_PHASES = {
    1: {"name": "Creative Discovery", "icon": "🎨", "desc": "情感錨點、品味輪廓、實用限制"},
    2: {"name": "Concept Generation", "icon": "💡", "desc": "三技法生成 3 個遊戲概念"},
    3: {"name": "Core Loop Design", "icon": "🔄", "desc": "30秒/5分/會話/進度 四層循環"},
    4: {"name": "Pillars & Boundaries", "icon": "🏛️", "desc": "3-5 遊戲支柱 + 反支柱"},
    5: {"name": "Player Type Validation", "icon": "👥", "desc": "Bartle 分類 + 市場參考"},
    6: {"name": "Scope & Feasibility", "icon": "📦", "desc": "MVP、風險、範圍層級"},
}


@app.route('/api/brainstorm/init', methods=['POST'])
def api_brainstorm_init():
    """初始化 /brainstorm 流程"""
    req = request.get_json() or {}
    genre_hint = req.get('genre_hint', None)
    result = brainstorm_skill.handle_init(genre_hint)
    return jsonify({"status": "success", "phases": BRAINSTORM_PHASES, **result})


@app.route('/api/brainstorm/respond', methods=['POST'])
def api_brainstorm_respond():
    """處理使用者對 brainstorm 的回覆"""
    req = request.get_json() or {}
    session_id = req.get('session_id', '')
    field = req.get('field', '')
    value = req.get('value', '')

    if not session_id:
        return jsonify({"status": "error", "message": "缺少 session_id"}), 400

    result = brainstorm_skill.handle_response(session_id, field, value)
    return jsonify({"status": "success", **result})


@app.route('/api/brainstorm/state/<session_id>', methods=['GET'])
def api_brainstorm_state(session_id):
    """查詢 brainstorm 會話狀態"""
    session = brainstorm_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})


@app.route('/api/brainstorm/phases', methods=['GET'])
def api_brainstorm_phases():
    """列出所有 6 個 Phase"""
    return jsonify({"status": "success", "phases": [
        {"id": k, **v} for k, v in BRAINSTORM_PHASES.items()
    ]})


@app.route('/api/brainstorm/save/<session_id>', methods=['POST'])
def api_brainstorm_save(session_id):
    """儲存 brainstorm 成果為 game-concept.md"""
    req = request.get_json() or {}
    output_dir = req.get('output_dir', '')

    session = brainstorm_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    if session.phase != "complete":
        return jsonify({
            "status": "error",
            "message": f"尚未完成所有階段（當前: {session.phase}）"
        }), 400

    result = brainstorm_skill.finalize(session)
    saved_path = None

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "game-concept.md"
        doc_path.write_text(result.get("document", ""), encoding='utf-8')
        saved_path = str(doc_path)

    return jsonify({
        "status": "success",
        "saved_path": saved_path,
        **result
    })


@app.route('/api/brainstorm/jump/<session_id>/<int:phase>', methods=['POST'])
def api_brainstorm_jump(session_id, phase):
    """跳轉到指定 Phase"""
    if phase not in BRAINSTORM_PHASES:
        return jsonify({"status": "error", "message": f"Phase {phase} 不存在"}), 400

    # 目前不支援跳轉，需要重新 init
    return jsonify({
        "status": "error",
        "message": "不支援跳轉。請用 /api/brainstorm/init 重新開始，可以快速跳過前面的階段。"
    }), 400


# ═══════════════ API：/setup-engine (Phase 1.4) ═══════════════

@app.route('/api/setup-engine/detect', methods=['GET'])
def api_setup_engine_detect():
    """偵測系統中的 Godot 安裝"""
    result = detect_godot()
    return jsonify({"status": "success", **result})


@app.route('/api/setup-engine/scaffold', methods=['POST'])
def api_setup_engine_scaffold():
    """建立 CCGS 標準 Godot 專案 scaffold"""
    req = request.get_json() or {}
    project_dir = req.get('project_dir', '').strip()
    project_name = req.get('project_name', '').strip()
    project_description = req.get('project_description', '').strip()

    if not project_dir:
        return jsonify({"status": "error", "message": "缺少 project_dir"}), 400
    if not project_name:
        return jsonify({"status": "error", "message": "缺少 project_name"}), 400

    result = scaffold_project(project_dir, project_name, project_description)
    return jsonify({"status": "success" if result["success"] else "partial", **result})


@app.route('/api/setup-engine/full', methods=['POST'])
def api_setup_engine_full():
    """完整 setup-engine：偵測 + scaffold + 摘要"""
    req = request.get_json() or {}
    project_dir = req.get('project_dir', '').strip()
    project_name = req.get('project_name', '').strip()
    project_description = req.get('project_description', '').strip()

    if not project_dir or not project_name:
        return jsonify({"status": "error", "message": "缺少 project_dir 或 project_name"}), 400

    godot_info = detect_godot()
    scaffold_result = scaffold_project(project_dir, project_name, project_description)
    summary = get_engine_setup_summary(godot_info, scaffold_result)

    return jsonify({"status": "success", **summary})


@app.route('/api/setup-engine/conventions', methods=['GET'])
def api_setup_engine_conventions():
    """取得 CCGS 命名規範"""
    return jsonify({"status": "success", "conventions": NAMING_CONVENTIONS})


@app.route('/api/setup-engine/performance-budget', methods=['GET'])
def api_setup_engine_performance_budget():
    """取得 CCGS 效能預算"""
    return jsonify({"status": "success", "performance_budget": PERFORMANCE_BUDGET})


# ═══════════════ API：/project-stage-detect (Phase 1.5) ═══════════════

@app.route('/api/stage-detect', methods=['POST'])
def api_stage_detect():
    """深層掃描專案，判定 Phase，產出差距報告"""
    req = request.get_json() or {}
    project_dir = req.get('project_dir', '').strip()

    if not project_dir:
        return jsonify({"status": "error", "message": "缺少 project_dir"}), 400

    result = deep_scan_project(project_dir)
    return jsonify(result)


@app.route('/api/stage-detect/report', methods=['POST'])
def api_stage_detect_report():
    """產生人類可讀的專案階段報告"""
    req = request.get_json() or {}
    project_dir = req.get('project_dir', '').strip()

    if not project_dir:
        return jsonify({"status": "error", "message": "缺少 project_dir"}), 400

    result = deep_scan_project(project_dir)
    if result.get("status") == "error":
        return jsonify(result), 404

    report = get_project_overview(result)
    return jsonify({"status": "success", "report": report, "raw": result})


@app.route('/api/stage-detect/gates', methods=['GET'])
def api_stage_detect_gates():
    """列出所有 7 個 Phase Gate 定義"""
    return jsonify({"status": "success", "gates": [
        {"id": k, **v} for k, v in PD_PHASE_GATES.items()
    ]})


# ═══════════════ API：godot_bridge (Phase 1.6) ═══════════════

@app.route('/api/godot/bridge/detect', methods=['GET'])
def api_godot_bridge_detect():
    """完整的 Godot 偵測報告 (godot_bridge 版)"""
    report = detect_and_report()
    return jsonify({"status": "success", **report})


@app.route('/api/godot/bridge/open-project', methods=['POST'])
def api_godot_bridge_open():
    """開啟 Godot 專案並讀取 project.godot"""
    req = request.get_json() or {}
    project_dir = req.get('project_dir', '').strip()
    godot_path = req.get('godot_path', None)

    if not project_dir:
        return jsonify({"status": "error", "message": "缺少 project_dir"}), 400

    bridge = get_bridge(godot_path)
    result = bridge.open_project(project_dir)
    return jsonify(result)


@app.route('/api/godot/bridge/run-script', methods=['POST'])
def api_godot_bridge_run():
    """在 headless 模式下執行 GDScript"""
    req = request.get_json() or {}
    script_path = req.get('script_path', '').strip()
    args = req.get('args', None)

    if not script_path:
        return jsonify({"status": "error", "message": "缺少 script_path"}), 400

    bridge = get_bridge()
    result = bridge.run_script(script_path, args)
    return jsonify(result)


@app.route('/api/godot/bridge/read-script', methods=['POST'])
def api_godot_bridge_read_script():
    """讀取並分析 GDScript"""
    req = request.get_json() or {}
    relative_path = req.get('path', '').strip()

    if not relative_path:
        return jsonify({"status": "error", "message": "缺少 path"}), 400

    bridge = get_bridge()
    result = bridge.read_gdscript(relative_path)
    return jsonify(result)


@app.route('/api/godot/bridge/read-scene', methods=['POST'])
def api_godot_bridge_read_scene():
    """讀取並分析 .tscn 場景"""
    req = request.get_json() or {}
    relative_path = req.get('path', '').strip()

    if not relative_path:
        return jsonify({"status": "error", "message": "缺少 path"}), 400

    bridge = get_bridge()
    result = bridge.read_scene(relative_path)
    return jsonify(result)


@app.route('/api/godot/bridge/write-script', methods=['POST'])
def api_godot_bridge_write_script():
    """寫入 GDScript 檔案"""
    req = request.get_json() or {}
    relative_path = req.get('path', '').strip()
    content = req.get('content', '')

    if not relative_path:
        return jsonify({"status": "error", "message": "缺少 path"}), 400

    bridge = get_bridge()
    result = bridge.write_gdscript(relative_path, content)
    return jsonify(result)


@app.route('/api/godot/bridge/structure', methods=['GET'])
def api_godot_bridge_structure():
    """取得專案結構（所有 .gd + .tscn）"""
    bridge = get_bridge()
    result = bridge.read_project_structure()
    return jsonify(result)


@app.route('/api/godot/bridge/exports', methods=['GET'])
def api_godot_bridge_exports():
    """列出所有匯出預設"""
    bridge = get_bridge()
    presets = bridge.list_export_presets()
    return jsonify({"status": "success", "presets": presets})


@app.route('/api/godot/bridge/export', methods=['POST'])
def api_godot_bridge_export():
    """匯出專案"""
    req = request.get_json() or {}
    preset = req.get('preset', '').strip()
    output_path = req.get('output_path', '').strip()

    if not preset:
        return jsonify({"status": "error", "message": "缺少 preset"}), 400
    if not output_path:
        return jsonify({"status": "error", "message": "缺少 output_path"}), 400

    bridge = get_bridge()
    result = bridge.export_project(preset, output_path)
    return jsonify(result)


@app.route('/api/godot/bridge/set-path', methods=['POST'])
def api_godot_bridge_set_path():
    """手動設定 Godot 執行檔路徑並驗證"""
    req = request.get_json() or {}
    godot_path = req.get('godot_path', '').strip()

    if not godot_path:
        return jsonify({"status": "error", "message": "缺少 godot_path"}), 400

    bridge = get_bridge()  # 重用現有實例
    result = bridge.set_path(godot_path)
    return jsonify(result)


@app.route('/api/godot/bridge/search', methods=['GET'])
def api_godot_bridge_search():
    """深度搜尋系統中所有 Godot 安裝"""
    paths = GodotBridge.search_disk()
    # 驗證每個路徑
    validated = []
    for p in paths:
        try:
            import subprocess
            r = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                validated.append({"path": p, "version": r.stdout.strip()})
        except Exception:
            pass
    return jsonify({
        "status": "success",
        "found": len(validated) > 0,
        "count": len(validated),
        "installations": validated,
    })


@app.route('/api/godot/bridge/file-dialog', methods=['POST'])
def api_godot_bridge_file_dialog():
    """開啟檔案選擇器讓主人點選 Godot 執行檔，自動驗證並回報結果"""
    path = GodotBridge.file_dialog()
    if not path:
        return jsonify({"status": "error", "message": "未選擇任何檔案"}), 400

    bridge = get_bridge()
    result = bridge.set_path(path)
    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code


# ── Godot 連線穩定性 (v1.6) ──

@app.route('/api/godot/bridge/heartbeat', methods=['GET'])
def api_godot_bridge_heartbeat():
    """檢查 Godot 連線狀態（每 30 秒輪詢）"""
    bridge = get_bridge()
    result = bridge.health_check()
    return jsonify(result)


@app.route('/api/godot/bridge/reconnect', methods=['POST'])
def api_godot_bridge_reconnect():
    """重新連接 Godot（保留已開啟的專案）"""
    req = request.get_json() or {}
    godot_path = req.get('godot_path', None)
    bridge = get_bridge(godot_path) if godot_path else get_bridge()
    result = bridge.reconnect(godot_path)
    return jsonify(result)


@app.route('/api/godot/bridge/project-info', methods=['GET'])
def api_godot_bridge_project_info():
    """取得當前 Godot 專案的完整資訊"""
    bridge = get_bridge()
    result = bridge.get_project_info()
    return jsonify(result)


@app.route('/api/godot/bridge/list-files', methods=['POST'])
def api_godot_bridge_list_files():
    """列出專案中指定子目錄的檔案"""
    req = request.get_json() or {}
    subdir = req.get('subdir', '')
    bridge = get_bridge()
    result = bridge.list_files(subdir)
    return jsonify(result)


# ═══════════════ Phase 2: Systems Design ═══════════════

# ── /map-systems (Phase 2.1) ──

@app.route('/api/map-systems/phases', methods=['GET'])
def api_map_systems_phases():
    return jsonify({"status": "success", "phases": [
        {"id": k, **v} for k, v in MAP_PHASES.items()
    ]})

@app.route('/api/map-systems/init', methods=['POST'])
def api_map_systems_init():
    req = request.get_json() or {}
    result = map_systems_skill.handle_init(
        concept_path=req.get('concept_path', ''),
        concept_text=req.get('concept_text', '')
    )
    return jsonify({"status": "success", "phases": MAP_PHASES, **result})

@app.route('/api/map-systems/respond', methods=['POST'])
def api_map_systems_respond():
    req = request.get_json() or {}
    result = map_systems_skill.handle_response(req.get('session_id', ''), req.get('field', ''), req.get('value', ''))
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/map-systems/state/<session_id>', methods=['GET'])
def api_map_systems_state(session_id):
    session = map_systems_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/map-systems/save/<session_id>', methods=['POST'])
def api_map_systems_save(session_id):
    req = request.get_json() or {}
    session = map_systems_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = map_systems_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /design-system (Phase 2.2) ──

@app.route('/api/design-system/sections', methods=['GET'])
def api_design_system_sections():
    return jsonify({"status": "success", "sections": [
        {"id": k, **v} for k, v in GDD_SECTIONS.items()
    ]})

@app.route('/api/design-system/init', methods=['POST'])
def api_design_system_init():
    req = request.get_json() or {}
    result = design_system_skill.handle_init(
        system_name=req.get('system_name', ''),
        from_map_systems=req.get('from_map_systems', '')
    )
    return jsonify({"status": "success", "sections": GDD_SECTIONS, **result})

@app.route('/api/design-system/respond', methods=['POST'])
def api_design_system_respond():
    req = request.get_json() or {}
    result = design_system_skill.handle_response(req.get('session_id', ''), req.get('field', ''), req.get('value', ''))
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/design-system/state/<session_id>', methods=['GET'])
def api_design_system_state(session_id):
    session = design_system_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/design-system/save/<session_id>', methods=['POST'])
def api_design_system_save(session_id):
    req = request.get_json() or {}
    session = design_system_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = design_system_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /design-review (Phase 2.3) ──

@app.route('/api/design-review/init', methods=['POST'])
def api_design_review_init():
    req = request.get_json() or {}
    result = design_review_skill.handle_init(
        gdd_path=req.get('gdd_path', ''),
        gdd_content=req.get('gdd_content', '')
    )
    return jsonify({"status": "success", **result})

@app.route('/api/design-review/respond', methods=['POST'])
def api_design_review_respond():
    req = request.get_json() or {}
    result = design_review_skill.handle_response(req.get('session_id', ''), req.get('field', ''), req.get('value', ''))
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/design-review/state/<session_id>', methods=['GET'])
def api_design_review_state(session_id):
    session = design_review_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})


# ── /review-all-gdds (Phase 2.4) ──

@app.route('/api/review-all-gdds/init', methods=['POST'])
def api_review_all_gdds_init():
    req = request.get_json() or {}
    result = review_all_gdds_skill.handle_init(
        gdd_paths=req.get('gdd_paths', None),
        concept_path=req.get('concept_path', '')
    )
    return jsonify({"status": "success", **result})

@app.route('/api/review-all-gdds/respond', methods=['POST'])
def api_review_all_gdds_respond():
    req = request.get_json() or {}
    result = review_all_gdds_skill.handle_response(req.get('session_id', ''), req.get('field', ''), req.get('value', ''))
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/review-all-gdds/state/<session_id>', methods=['GET'])
def api_review_all_gdds_state(session_id):
    session = review_all_gdds_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})


# ── /consistency-check (Phase 2.5) ──

@app.route('/api/consistency-check/init', methods=['POST'])
def api_consistency_check_init():
    req = request.get_json() or {}
    result = consistency_check_skill.handle_init(
        gdd_path=req.get('gdd_path', ''),
        gdd_content=req.get('gdd_content', ''),
        reference_path=req.get('reference_path', '')
    )
    return jsonify({"status": "success", **result})

@app.route('/api/consistency-check/respond', methods=['POST'])
def api_consistency_check_respond():
    req = request.get_json() or {}
    result = consistency_check_skill.handle_response(req.get('session_id', ''), req.get('field', ''), req.get('value', ''))
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/consistency-check/state/<session_id>', methods=['GET'])
def api_consistency_check_state(session_id):
    session = consistency_check_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})


# ═══════════════ Phase 3: Technical Setup ═══════════════

# ── /create-architecture (Phase 3.1) ──

ARCH_SESSIONS = {}

@app.route('/api/create-architecture/init', methods=['POST'])
def api_create_architecture_init():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    project_path = req.get('project_path', '')
    game_concept = req.get('game_concept', {})
    systems_map = req.get('systems_map', {})

    session = CreateArchitectureSkill.init_session(
        project_id, project_path, game_concept, systems_map
    )
    ARCH_SESSIONS[project_id] = session

    return jsonify({
        "status": "success",
        "selected_adrs": [
            {"id": a["id"], "title": a["title"], "category": a["category"]}
            for a in session["selected_adrs"]
        ],
        "total_sections": len(CreateArchitectureSkill.ARCH_SECTIONS),
        "sections": [{"index": i, "title": t} for i, t in enumerate(CreateArchitectureSkill.ARCH_SECTIONS)],
    })

@app.route('/api/create-architecture/respond', methods=['POST'])
def api_create_architecture_respond():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    section_index = req.get('section_index', 0)
    content = req.get('content', '')

    session = ARCH_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found. Call /init first."}), 404

    session["sections_content"][str(section_index)] = content
    session["current_section"] = section_index

    next_section = section_index + 1
    if next_section < len(CreateArchitectureSkill.ARCH_SECTIONS):
        prompt = CreateArchitectureSkill.get_section_prompt(
            next_section, session.get("game_concept", {}), session.get("systems_map", {})
        )
        return jsonify({
            "status": "success",
            "current_section": section_index,
            "section_title": CreateArchitectureSkill.ARCH_SECTIONS[section_index],
            "next_section": next_section,
            "next_title": CreateArchitectureSkill.ARCH_SECTIONS[next_section],
            "next_prompt": prompt,
            "progress": f"{next_section}/{len(CreateArchitectureSkill.ARCH_SECTIONS)}",
        })
    else:
        return jsonify({
            "status": "success",
            "current_section": section_index,
            "section_title": CreateArchitectureSkill.ARCH_SECTIONS[section_index],
            "complete": True,
            "message": "所有段落完成！呼叫 /save 生成完整架構文件。",
        })

@app.route('/api/create-architecture/state/<project_id>', methods=['GET'])
def api_create_architecture_state(project_id):
    session = ARCH_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "current_section": session.get("current_section", 0),
        "sections_count": len(session.get("sections_content", {})),
        "total_sections": len(CreateArchitectureSkill.ARCH_SECTIONS),
        "adr_count": len(session.get("selected_adrs", [])),
    })

@app.route('/api/create-architecture/section/<int:index>', methods=['GET'])
def api_create_architecture_section(index):
    prompt = CreateArchitectureSkill.get_section_prompt(index, {}, {})
    return jsonify({
        "status": "success",
        "index": index,
        "title": CreateArchitectureSkill.ARCH_SECTIONS[index] if 0 <= index < len(CreateArchitectureSkill.ARCH_SECTIONS) else "Unknown",
        "prompt": prompt,
    })

@app.route('/api/create-architecture/save/<project_id>', methods=['POST'])
def api_create_architecture_save(project_id):
    req = request.get_json() or {}
    session = ARCH_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    doc = CreateArchitectureSkill.generate_architecture_doc(
        session.get("sections_content", {}),
        session.get("game_concept", {}),
        session.get("selected_adrs", [])
    )

    output_dir = req.get('output_dir', '')
    saved_path = None
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "architecture.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return jsonify({
        "status": "success",
        "document": doc,
        "saved_path": saved_path,
        "adr_status": CreateArchitectureSkill.get_adr_status(session),
    })


# ── /architecture-decision (Phase 3.2) ──

ADR_SESSIONS = {}

@app.route('/api/architecture-decision/init', methods=['POST'])
def api_architecture_decision_init():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    adr_id = req.get('adr_id', 'ADR-001')
    adr_info = req.get('adr_info', None)

    session = ArchitectureDecisionSkill.init_session(project_id, adr_id, adr_info)
    ADR_SESSIONS[f"{project_id}:{adr_id}"] = session

    next_q = ArchitectureDecisionSkill.get_next_question(session)

    return jsonify({
        "status": "success",
        "adr_id": adr_id,
        "current_field": session.get("current_field"),
        "next_question": next_q,
    })

@app.route('/api/architecture-decision/respond', methods=['POST'])
def api_architecture_decision_respond():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    adr_id = req.get('adr_id', 'ADR-001')
    value = req.get('value', '')

    session = ADR_SESSIONS.get(f"{project_id}:{adr_id}")
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    current_field = session.get("current_field")
    if current_field:
        ArchitectureDecisionSkill.set_field(session, current_field, value)

    next_q = ArchitectureDecisionSkill.get_next_question(session)

    if next_q:
        return jsonify({
            "status": "success",
            "current_field": current_field,
            "next_question": next_q,
        })
    else:
        validation = ArchitectureDecisionSkill.validate_adr(session)
        return jsonify({
            "status": "success",
            "complete": True,
            "validation": validation,
            "message": "ADR 完成！可呼叫 /render 取得完整內容。",
        })

@app.route('/api/architecture-decision/state/<project_id>/<adr_id>', methods=['GET'])
def api_architecture_decision_state(project_id, adr_id):
    session = ADR_SESSIONS.get(f"{project_id}:{adr_id}")
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "adr_id": adr_id,
        "current_field": session.get("current_field"),
        "filled_fields": [f for f, v in session.get("fields", {}).items() if v],
    })

@app.route('/api/architecture-decision/validate/<project_id>/<adr_id>', methods=['GET'])
def api_architecture_decision_validate(project_id, adr_id):
    session = ADR_SESSIONS.get(f"{project_id}:{adr_id}")
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "validation": ArchitectureDecisionSkill.validate_adr(session),
    })

@app.route('/api/architecture-decision/render/<project_id>/<adr_id>', methods=['POST'])
def api_architecture_decision_render(project_id, adr_id):
    session = ADR_SESSIONS.get(f"{project_id}:{adr_id}")
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    rendered = ArchitectureDecisionSkill.render_adr(session)

    req = request.get_json() or {}
    output_dir = req.get('output_dir', '')
    saved_path = None
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / f"{adr_id}.md"
        doc_path.write_text(rendered, encoding='utf-8')
        saved_path = str(doc_path)

    return jsonify({
        "status": "success",
        "document": rendered,
        "saved_path": saved_path,
    })


# ── /architecture-review (Phase 3.3) ──

REVIEW_SESSIONS = {}

@app.route('/api/architecture-review/init', methods=['POST'])
def api_architecture_review_init():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    architecture_doc = req.get('architecture_doc', '')
    adrs = req.get('adrs', [])
    game_concept = req.get('game_concept', {})
    systems_map = req.get('systems_map', {})

    session = ArchitectureReviewSkill.init_session(
        project_id, architecture_doc, adrs, game_concept, systems_map
    )
    REVIEW_SESSIONS[project_id] = session

    return jsonify({
        "status": "success",
        "dimensions": [
            {"id": d["id"], "name": d["name"], "weight": d["weight"]}
            for d in ArchitectureReviewSkill.REVIEW_DIMENSIONS
        ],
        "requirements_count": len(session.get("requirements", [])),
        "tr_summary": ArchitectureReviewSkill.get_tr_matrix_summary(session),
    })

@app.route('/api/architecture-review/review/<project_id>', methods=['POST'])
def api_architecture_review_run(project_id):
    session = REVIEW_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    results = ArchitectureReviewSkill.run_review(session)
    return jsonify({
        "status": "success",
        "review": results,
    })

@app.route('/api/architecture-review/state/<project_id>', methods=['GET'])
def api_architecture_review_state(project_id):
    session = REVIEW_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "has_review": bool(session.get("review_results")),
        "verdict": session.get("review_results", {}).get("verdict"),
    })

@app.route('/api/architecture-review/tr-matrix/<project_id>', methods=['GET'])
def api_architecture_review_tr_matrix(project_id):
    session = REVIEW_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "tr_summary": ArchitectureReviewSkill.get_tr_matrix_summary(session),
        "matrix": session.get("tr_matrix", {}),
    })

@app.route('/api/architecture-review/dimensions', methods=['GET'])
def api_architecture_review_dimensions():
    return jsonify({
        "status": "success",
        "dimensions": ArchitectureReviewSkill.REVIEW_DIMENSIONS,
    })


# ── /create-control-manifest (Phase 3.4) ──

MANIFEST_SESSIONS = {}

@app.route('/api/control-manifest/init', methods=['POST'])
def api_control_manifest_init():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    architecture_doc = req.get('architecture_doc', '')
    adrs = req.get('adrs', [])

    session = CreateControlManifestSkill.init_session(project_id, architecture_doc, adrs)
    MANIFEST_SESSIONS[project_id] = session

    return jsonify({
        "status": "success",
        "categories": [
            {"id": c["id"], "name": c["name"], "icon": c["icon"], "rule_count": len(c["default_rules"])}
            for c in session.get("categories", [])
        ],
    })

@app.route('/api/control-manifest/respond', methods=['POST'])
def api_control_manifest_respond():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    action = req.get('action', '')
    category_index = req.get('category_index', 0)
    rule = req.get('rule', '')
    rule_index = req.get('rule_index', 0)
    is_custom = req.get('is_custom', False)

    session = MANIFEST_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    if action == 'add_rule':
        CreateControlManifestSkill.add_custom_rule(session, category_index, rule)
    elif action == 'remove_rule':
        CreateControlManifestSkill.remove_rule(session, category_index, rule_index, is_custom)
    elif action == 'toggle':
        CreateControlManifestSkill.toggle_category(session, category_index)

    return jsonify({
        "status": "success",
        "category": CreateControlManifestSkill.get_category(session, category_index),
    })

@app.route('/api/control-manifest/state/<project_id>', methods=['GET'])
def api_control_manifest_state(project_id):
    session = MANIFEST_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "categories": [
            {"id": c["id"], "name": c["name"], "enabled": c.get("enabled", True),
             "default_rules": len(c["default_rules"]), "custom_rules": len(c["custom_rules"])}
            for c in session.get("categories", [])
        ],
    })

@app.route('/api/control-manifest/save/<project_id>', methods=['POST'])
def api_control_manifest_save(project_id):
    req = request.get_json() or {}
    session = MANIFEST_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    doc = CreateControlManifestSkill.generate_manifest(session)
    validation = CreateControlManifestSkill.validate_against_adrs(session)

    output_dir = req.get('output_dir', '')
    saved_path = None
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "CONTROL_MANIFEST.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return jsonify({
        "status": "success",
        "document": doc,
        "saved_path": saved_path,
        "validation": validation,
    })

@app.route('/api/control-manifest/categories', methods=['GET'])
def api_control_manifest_categories():
    return jsonify({
        "status": "success",
        "categories": [
            {"id": c["id"], "name": c["name"], "icon": c["icon"], "description": c["description"]}
            for c in CreateControlManifestSkill.MANIFEST_CATEGORIES
        ],
    })


# ── /art-bible (Phase 3.5) ──

ART_BIBLE_SESSIONS = {}

@app.route('/api/art-bible/init', methods=['POST'])
def api_art_bible_init():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    game_concept = req.get('game_concept', {})

    session = ArtBibleSkill.init_session(project_id, game_concept)
    ART_BIBLE_SESSIONS[project_id] = session

    section = ArtBibleSkill.get_section(0)
    return jsonify({
        "status": "success",
        "current_section": 0,
        "section": section,
        "progress": ArtBibleSkill.get_progress(session),
    })

@app.route('/api/art-bible/respond', methods=['POST'])
def api_art_bible_respond():
    req = request.get_json() or {}
    project_id = req.get('project_id', 'default')
    section_index = req.get('section_index', 0)
    content = req.get('content', '')

    session = ART_BIBLE_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    ArtBibleSkill.set_section_content(session, section_index, content)
    progress = ArtBibleSkill.get_progress(session)

    next_index = progress.get("next_section")
    if next_index is not None:
        next_section = ArtBibleSkill.get_section(next_index)
        return jsonify({
            "status": "success",
            "current_section": section_index,
            "next_section": next_section,
            "progress": progress,
        })
    else:
        return jsonify({
            "status": "success",
            "complete": True,
            "progress": progress,
            "message": "所有 9 段落完成！呼叫 /save 生成完整 Art Bible。",
        })

@app.route('/api/art-bible/state/<project_id>', methods=['GET'])
def api_art_bible_state(project_id):
    session = ART_BIBLE_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({
        "status": "success",
        "progress": ArtBibleSkill.get_progress(session),
        "completed": session.get("completed_sections", []),
    })

@app.route('/api/art-bible/save/<project_id>', methods=['POST'])
def api_art_bible_save(project_id):
    req = request.get_json() or {}
    session = ART_BIBLE_SESSIONS.get(project_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    doc = ArtBibleSkill.generate_art_bible(session)
    validation = ArtBibleSkill.validate_bible(session)

    output_dir = req.get('output_dir', '')
    saved_path = None
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "ART_BIBLE.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return jsonify({
        "status": "success",
        "document": doc,
        "saved_path": saved_path,
        "validation": validation,
    })

@app.route('/api/art-bible/sections', methods=['GET'])
def api_art_bible_sections():
    return jsonify({
        "status": "success",
        "sections": ArtBibleSkill.SECTIONS,
    })


# ═══════════════ Phase 4: Pre-Production ═══════════════

# ── /asset-spec (Phase 4.1) ──

@app.route('/api/asset-spec/init', methods=['POST'])
def api_asset_spec_init():
    req = request.get_json() or {}
    result = asset_spec_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        project_info=req.get('project_info')
    )
    return jsonify({"status": "success", "categories": ASSET_CATEGORIES, **result})

@app.route('/api/asset-spec/respond', methods=['POST'])
def api_asset_spec_respond():
    req = request.get_json() or {}
    result = asset_spec_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/asset-spec/state/<session_id>', methods=['GET'])
def api_asset_spec_state(session_id):
    session = asset_spec_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/asset-spec/categories', methods=['GET'])
def api_asset_spec_categories():
    return jsonify({"status": "success", "categories": ASSET_CATEGORIES})

@app.route('/api/asset-spec/save/<session_id>', methods=['POST'])
def api_asset_spec_save(session_id):
    req = request.get_json() or {}
    session = asset_spec_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = asset_spec_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /ux-design (Phase 4.2) ──

@app.route('/api/ux-design/sections', methods=['GET'])
def api_ux_design_sections():
    return jsonify({"status": "success", "sections": UX_SECTIONS})

@app.route('/api/ux-design/init', methods=['POST'])
def api_ux_design_init():
    req = request.get_json() or {}
    result = ux_design_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        system_name=req.get('system_name', ''),
        from_context=req.get('from_context')
    )
    return jsonify({"status": "success", "sections": UX_SECTIONS, **result})

@app.route('/api/ux-design/respond', methods=['POST'])
def api_ux_design_respond():
    req = request.get_json() or {}
    result = ux_design_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/ux-design/state/<session_id>', methods=['GET'])
def api_ux_design_state(session_id):
    session = ux_design_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/ux-design/save/<session_id>', methods=['POST'])
def api_ux_design_save(session_id):
    req = request.get_json() or {}
    session = ux_design_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = ux_design_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /ux-review (Phase 4.3) ──

@app.route('/api/ux-review/init', methods=['POST'])
def api_ux_review_init():
    req = request.get_json() or {}
    result = ux_review_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        ux_doc=req.get('ux_doc', '')
    )
    return jsonify({"status": "success", "heuristics": HEURISTICS, "game_heuristics": GAME_HEURISTICS, **result})

@app.route('/api/ux-review/respond', methods=['POST'])
def api_ux_review_respond():
    req = request.get_json() or {}
    result = ux_review_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/ux-review/state/<session_id>', methods=['GET'])
def api_ux_review_state(session_id):
    session = ux_review_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/ux-review/heuristics', methods=['GET'])
def api_ux_review_heuristics():
    return jsonify({"status": "success", "heuristics": HEURISTICS, "game_heuristics": GAME_HEURISTICS})

@app.route('/api/ux-review/save/<session_id>', methods=['POST'])
def api_ux_review_save(session_id):
    req = request.get_json() or {}
    session = ux_review_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = ux_review_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /prototype (Phase 4.4) ──

@app.route('/api/prototype/init', methods=['POST'])
def api_prototype_init():
    req = request.get_json() or {}
    result = prototype_skill.handle_init(session_id=req.get('session_id', 'default'))
    return jsonify({"status": "success", "types": PROTOTYPE_TYPES, **result})

@app.route('/api/prototype/respond', methods=['POST'])
def api_prototype_respond():
    req = request.get_json() or {}
    result = prototype_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/prototype/state/<session_id>', methods=['GET'])
def api_prototype_state(session_id):
    session = prototype_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/prototype/types', methods=['GET'])
def api_prototype_types():
    return jsonify({"status": "success", "types": PROTOTYPE_TYPES})

@app.route('/api/prototype/save/<session_id>', methods=['POST'])
def api_prototype_save(session_id):
    req = request.get_json() or {}
    session = prototype_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = prototype_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /create-epics (Phase 4.5) ──

@app.route('/api/create-epics/init', methods=['POST'])
def api_create_epics_init():
    req = request.get_json() or {}
    result = create_epics_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        systems_map=req.get('systems_map')
    )
    return jsonify({"status": "success", **result})

@app.route('/api/create-epics/respond', methods=['POST'])
def api_create_epics_respond():
    req = request.get_json() or {}
    result = create_epics_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/create-epics/state/<session_id>', methods=['GET'])
def api_create_epics_state(session_id):
    session = create_epics_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/create-epics/fields', methods=['GET'])
def api_create_epics_fields():
    return jsonify({"status": "success", "fields": create_epics_skill.FIELDS})

@app.route('/api/create-epics/save/<session_id>', methods=['POST'])
def api_create_epics_save(session_id):
    req = request.get_json() or {}
    session = create_epics_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = create_epics_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /create-stories (Phase 4.6) ──

@app.route('/api/create-stories/init', methods=['POST'])
def api_create_stories_init():
    req = request.get_json() or {}
    result = create_stories_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        epic_context=req.get('epic_context')
    )
    return jsonify({"status": "success", "priorities": create_stories_skill.PRIORITIES, "points": create_stories_skill.POINTS, **result})

@app.route('/api/create-stories/respond', methods=['POST'])
def api_create_stories_respond():
    req = request.get_json() or {}
    result = create_stories_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/create-stories/state/<session_id>', methods=['GET'])
def api_create_stories_state(session_id):
    session = create_stories_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/create-stories/meta', methods=['GET'])
def api_create_stories_meta():
    return jsonify({"status": "success", "priorities": create_stories_skill.PRIORITIES, "points": create_stories_skill.POINTS, "fields": create_stories_skill.FIELDS})

@app.route('/api/create-stories/save/<session_id>', methods=['POST'])
def api_create_stories_save(session_id):
    req = request.get_json() or {}
    session = create_stories_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = create_stories_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /sprint-plan (Phase 4.7) ──

@app.route('/api/sprint-plan/init', methods=['POST'])
def api_sprint_plan_init():
    req = request.get_json() or {}
    result = sprint_plan_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        stories=req.get('stories'),
        story_count=req.get('story_count', 0)
    )
    return jsonify({"status": "success", **result})

@app.route('/api/sprint-plan/respond', methods=['POST'])
def api_sprint_plan_respond():
    req = request.get_json() or {}
    result = sprint_plan_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/sprint-plan/state/<session_id>', methods=['GET'])
def api_sprint_plan_state(session_id):
    session = sprint_plan_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/sprint-plan/save/<session_id>', methods=['POST'])
def api_sprint_plan_save(session_id):
    req = request.get_json() or {}
    session = sprint_plan_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = sprint_plan_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /gate-check (Phase 4.8) ──

@app.route('/api/gate-check/init', methods=['POST'])
def api_gate_check_init():
    req = request.get_json() or {}
    result = gate_check_skill.handle_init(
        session_id=req.get('session_id', 'default'),
        from_phase=req.get('from_phase', 1),
        to_phase=req.get('to_phase', 2)
    )
    return jsonify({"status": "success", "gates": {str(k): v for k, v in GATE_CHECKS.items()}, **result})

@app.route('/api/gate-check/respond', methods=['POST'])
def api_gate_check_respond():
    req = request.get_json() or {}
    result = gate_check_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/gate-check/state/<session_id>', methods=['GET'])
def api_gate_check_state(session_id):
    session = gate_check_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/gate-check/gates', methods=['GET'])
def api_gate_check_gates():
    return jsonify({"status": "success", "gates": {str(k): v for k, v in GATE_CHECKS.items()}})

@app.route('/api/gate-check/save/<session_id>', methods=['POST'])
def api_gate_check_save(session_id):
    req = request.get_json() or {}
    session = gate_check_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = gate_check_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ── /vertical-slice (Phase 4.9) ──

@app.route('/api/vertical-slice/init', methods=['POST'])
def api_vertical_slice_init():
    req = request.get_json() or {}
    result = vertical_slice_skill.handle_init(session_id=req.get('session_id', 'default'))
    return jsonify({"status": "success", "phases": VERTICAL_SLICE_PHASES, "types": SLICE_TYPES, **result})

@app.route('/api/vertical-slice/respond', methods=['POST'])
def api_vertical_slice_respond():
    req = request.get_json() or {}
    result = vertical_slice_skill.handle_response(
        req.get('session_id', ''), req.get('field', ''), req.get('value', '')
    )
    if "error" in result:
        return jsonify({"status": "error", **result}), 400
    return jsonify({"status": "success", **result})

@app.route('/api/vertical-slice/state/<session_id>', methods=['GET'])
def api_vertical_slice_state(session_id):
    session = vertical_slice_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session.to_dict()})

@app.route('/api/vertical-slice/phases', methods=['GET'])
def api_vertical_slice_phases():
    return jsonify({"status": "success", "phases": VERTICAL_SLICE_PHASES, "types": SLICE_TYPES})

@app.route('/api/vertical-slice/save/<session_id>', methods=['POST'])
def api_vertical_slice_save(session_id):
    req = request.get_json() or {}
    session = vertical_slice_skill.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    result = vertical_slice_skill.finalize(session, output_dir=req.get('output_dir', ''))
    return jsonify({"status": "success", **result})


# ═══════════════ Phase 5: Production ═══════════════

# 註冊 Phase 5 Blueprints
app.register_blueprint(code_review_bp)
app.register_blueprint(story_complete_bp)
app.register_blueprint(sprint_retro_bp)
app.register_blueprint(implement_bp)
app.register_blueprint(test_design_bp)
app.register_blueprint(playtest_bp)
app.register_blueprint(issue_write_bp)


# ═══════════════ Phase 6: Polish ═══════════════

# 實例化 Phase 6 Skills 並註冊路由
profiling_skill = ProfilingSkill(manager=None)
profiling_skill.register_routes(app)

balance_tuning_skill = BalanceTuningSkill(manager=None)
balance_tuning_skill.register_routes(app)

asset_audit_skill = AssetAuditSkill(manager=None)
asset_audit_skill.register_routes(app)

accessibility_review_skill = AccessibilityReviewSkill(manager=None)
accessibility_review_skill.register_routes(app)

polish_pass_skill = PolishPassSkill(manager=None)
polish_pass_skill.register_routes(app)


# ═══════════════ Phase 7: Release ═══════════════

# 註冊 Phase 7 Blueprints
app.register_blueprint(release_checklist_bp)
app.register_blueprint(changelog_bp)
app.register_blueprint(post_launch_monitor_bp)

# ── 開發進度 API ──

@app.route('/api/progress', methods=['GET'])
def api_progress():
    """回傳當前 Game Studio 開發進度（Phase 1-7 狀態、skills、API 端點）"""
    phase_skills = {
        1: 6,
        2: 5,
        3: 5,
        4: 9,
        5: 7,
        6: 5,
        7: 3,
    }
    current_phase = 7

    phases_status = []
    for pid in range(1, 8):
        skills_done = phase_skills.get(pid, 0)
        phases_status.append({
            "id": pid,
            "name": PHASES[pid]["name"],
            "slug": PHASES[pid]["slug"],
            "icon": PHASES[pid]["icon"],
            "desc": PHASES[pid]["desc"],
            "skills": skills_done,
            "status": "complete" if pid <= current_phase else "pending",
        })

    total_skills = sum(phase_skills.values())

    return jsonify({
        "status": "ok",
        "version": "1.5.0",
        "current_phase": current_phase,
        "phase_name": PHASES[current_phase]["name"],
        "progress_pct": 100.0,
        "total_skills": total_skills,
        "total_phases": 7,
        "phases": phases_status,
    })


# ═══════════════ 啟動函數 ═══════════════

def start_game_studio(port=5003, open_browser=True):
    """啟動 Game Studio 伺服器"""
    import socket, webbrowser

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    port_occupied = sock.connect_ex(('127.0.0.1', port)) == 0
    sock.close()

    if port_occupied:
        if open_browser:
            webbrowser.open(f"http://localhost:{port}")
        return False, f"Port {port} occupied"

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    return True, f"http://localhost:{port}"
