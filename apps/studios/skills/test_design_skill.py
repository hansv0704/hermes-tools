"""
/test-design — 7 類別測試計畫
Phase 5.5 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

test_design_bp = Blueprint('test_design', __name__)
sessions = {}

TEST_CATEGORIES = [
    {
        "id": "unit",
        "title": "單元測試 Unit Tests",
        "description": "測試個別函式/方法的邏輯正確性",
        "target": "所有 public 方法、邊界條件",
        "tools": ["GUT (Godot Unit Testing)", "NUnit (C#)"],
        "example": "測試傷害計算函式在各種輸入下的輸出"
    },
    {
        "id": "integration",
        "title": "整合測試 Integration Tests",
        "description": "測試模組之間的互動與資料流",
        "target": "API 呼叫、訊號傳遞、場景切換",
        "tools": ["GUT Integration", "自訂測試場景"],
        "example": "測試物品系統與背包系統的互動"
    },
    {
        "id": "functional",
        "title": "功能測試 Functional Tests",
        "description": "測試完整功能是否符合規格",
        "target": "使用者故事 AC、UI 操作流程",
        "tools": ["手動測試劇本", "GUT E2E"],
        "example": "測試玩家從登入到進入遊戲的完整流程"
    },
    {
        "id": "performance",
        "title": "效能測試 Performance Tests",
        "description": "測試幀率、記憶體、載入時間",
        "target": "Performance Budget 定義的指標",
        "tools": ["Godot Profiler", "Memory Monitor"],
        "example": "場景中有 100 個敵人時的 FPS 是否 > 30"
    },
    {
        "id": "compatibility",
        "title": "相容性測試 Compatibility Tests",
        "description": "測試不同平台/裝置/解析度",
        "target": "目標平台清單（PC/Console/Mobile）",
        "tools": ["Godot Export Templates", "Device Farm"],
        "example": "測試 iOS 和 Android 上的 UI 縮放"
    },
    {
        "id": "regression",
        "title": "回歸測試 Regression Tests",
        "description": "確認新改動沒有破壞既有功能",
        "target": "所有已完成的 Story AC",
        "tools": ["CI/CD Pipeline", "Automated Test Suite"],
        "example": "重跑所有測試確認新功能沒破壞舊功能"
    },
    {
        "id": "playtest",
        "title": "試玩測試 Playtests",
        "description": "真人試玩，收集主觀體驗回饋",
        "target": "樂趣、難度、UX、節奏",
        "tools": ["試玩問卷", "觀察記錄表"],
        "example": "5 位測試者試玩第一章並填寫回饋表"
    }
]

TEST_PRIORITIES = ["P0 - 阻擋發佈", "P1 - 重要", "P2 - 一般", "P3 - 低優先"]


def _init_session(feature_name):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "feature_name": feature_name,
        "test_cases": {c["id"]: [] for c in TEST_CATEGORIES},
        "current_category": None,
        "created": datetime.now().isoformat()
    }
    return sid


@test_design_bp.route('/api/test-design/init', methods=['POST'])
def init_test_design():
    data = request.get_json() or {}
    feature_name = data.get('feature_name', '新功能')

    sid = _init_session(feature_name)

    return jsonify({
        "session_id": sid,
        "feature_name": feature_name,
        "categories": TEST_CATEGORIES,
        "priorities": TEST_PRIORITIES,
        "phase": 1,
        "next": "使用 /api/test-design/add/{session_id}/{category_id} 新增測試案例"
    })


@test_design_bp.route('/api/test-design/add/<sid>/<category_id>', methods=['POST'])
def add_test_case(sid, category_id):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    valid = [c["id"] for c in TEST_CATEGORIES]
    if category_id not in valid:
        return jsonify({"error": f"無效的測試類別: {category_id}", "valid": valid}), 400

    data = request.get_json() or {}
    test_case = {
        "id": f"TC-{uuid.uuid4().hex[:6].upper()}",
        "title": data.get('title', '未命名測試'),
        "description": data.get('description', ''),
        "steps": data.get('steps', ''),
        "expected_result": data.get('expected_result', ''),
        "priority": data.get('priority', 'P2 - 一般'),
        "status": "pending"
    }

    sessions[sid]["test_cases"][category_id].append(test_case)
    sessions[sid]["current_category"] = category_id

    total = sum(len(v) for v in sessions[sid]["test_cases"].values())

    return jsonify({
        "test_case": test_case,
        "total_test_cases": total
    })


@test_design_bp.route('/api/test-design/state/<sid>', methods=['GET'])
def test_design_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    summary = {}
    total = 0
    for c in TEST_CATEGORIES:
        count = len(sessions[sid]["test_cases"][c["id"]])
        summary[c["id"]] = {"title": c["title"], "case_count": count}
        total += count

    return jsonify({
        "session_id": sid,
        "feature_name": sessions[sid]["feature_name"],
        "total_test_cases": total,
        "categories": summary,
        "test_cases": sessions[sid]["test_cases"]
    })


@test_design_bp.route('/api/test-design/categories', methods=['GET'])
def list_categories():
    return jsonify({"categories": TEST_CATEGORIES, "priorities": TEST_PRIORITIES})


@test_design_bp.route('/api/test-design/export/<sid>', methods=['GET'])
def export_test_plan(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    plan = f"# 測試計畫：{sessions[sid]['feature_name']}\n\n"
    for c in TEST_CATEGORIES:
        cases = sessions[sid]["test_cases"][c["id"]]
        if cases:
            plan += f"## {c['title']}\n\n"
            for tc in cases:
                plan += f"### {tc['id']}: {tc['title']}\n"
                plan += f"- 優先級: {tc['priority']}\n"
                plan += f"- 描述: {tc['description']}\n"
                plan += f"- 步驟: {tc['steps']}\n"
                plan += f"- 預期結果: {tc['expected_result']}\n"
                plan += f"- 狀態: {tc['status']}\n\n"

    return jsonify({"test_plan_markdown": plan})
