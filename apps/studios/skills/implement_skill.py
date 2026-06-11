"""
/implement — 實作任務導引
Phase 5.4 — Production
"""
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

implement_bp = Blueprint('implement', __name__)
sessions = {}

IMPLEMENT_STEPS = [
    {
        "id": "understand",
        "title": "🧠 理解需求",
        "checklist": [
            "閱讀 Story / Task 描述",
            "確認 Acceptance Criteria",
            "理解與其他系統的依賴關係",
            "確認設計文件 / GDD 已就緒"
        ]
    },
    {
        "id": "setup",
        "title": "🔧 環境設定",
        "checklist": [
            "建立功能分支 (feature/XXX-###)",
            "確認開發環境版本一致",
            "拉取最新主分支程式碼",
            "安裝/更新依賴套件"
        ]
    },
    {
        "id": "implement",
        "title": "💻 實作",
        "checklist": [
            "遵循 Control Manifest 編碼規範",
            "先寫測試 (TDD)，再寫實作",
            "保持 commit 小而頻繁",
            "處理邊界條件與錯誤狀態",
            "加入適當的日誌/註解"
        ]
    },
    {
        "id": "self_review",
        "title": "🔍 自我審查",
        "checklist": [
            "所有 AC 都已實作",
            "無 console.log / print 殘留",
            "無 hard-coded 字串（使用常數/i18n）",
            "執行 linter 檢查",
            "執行全部測試並確認通過"
        ]
    },
    {
        "id": "submit",
        "title": "📤 提交審查",
        "checklist": [
            "建立 Pull Request / Merge Request",
            "填寫 PR 描述（What/Why/How）",
            "連結相關 Issue/Story",
            "指定 Code Reviewer",
            "確認 CI/CD Pipeline 通過"
        ]
    }
]

CODE_TEMPLATES = {
    "gdscript": """extends Node

## {class_description}
class_name {class_name}

# 訊號
signal {signal_name}

# 屬性
@export var speed: float = 100.0

func _ready():
\tpass

func _process(delta: float):
\tpass
""",
    "csharp": """using Godot;

public partial class {class_name} : Node
{{
    [Export]
    public float Speed {{ get; set; }} = 100.0f;

    public override void _Ready()
    {{
    }}

    public override void _Process(double delta)
    {{
    }}
}}
""",
}


def _init_session(story_id, language="gdscript"):
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "story_id": story_id,
        "language": language,
        "current_step": 0,
        "checklist": {s["id"]: {c: False for c in s["checklist"]} for s in IMPLEMENT_STEPS},
        "code_snippets": [],
        "notes": "",
        "created": datetime.now().isoformat()
    }
    return sid


@implement_bp.route('/api/implement/init', methods=['POST'])
def init_implement():
    data = request.get_json() or {}
    story_id = data.get('story_id', f'STORY-{uuid.uuid4().hex[:6].upper()}')
    language = data.get('language', 'gdscript')

    sid = _init_session(story_id, language)

    return jsonify({
        "session_id": sid,
        "story_id": story_id,
        "language": language,
        "steps": IMPLEMENT_STEPS,
        "current_step": IMPLEMENT_STEPS[0],
        "code_template": CODE_TEMPLATES.get(language, CODE_TEMPLATES["gdscript"]),
        "next": "使用 /api/implement/check/{session_id}/{step_id}/{item_index} 標記完成"
    })


@implement_bp.route('/api/implement/check/<sid>/<step_id>/<int:item_index>', methods=['POST'])
def check_item(sid, step_id, item_index):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    step = next((s for s in IMPLEMENT_STEPS if s["id"] == step_id), None)
    if not step:
        return jsonify({"error": f"無效的步驟: {step_id}",
                       "valid": [s["id"] for s in IMPLEMENT_STEPS]}), 400

    if item_index < 0 or item_index >= len(step["checklist"]):
        return jsonify({"error": f"無效的項目索引: {item_index}",
                       "max": len(step["checklist"]) - 1}), 400

    item_text = step["checklist"][item_index]
    sessions[sid]["checklist"][step_id][item_text] = True

    done = sum(1 for v in sessions[sid]["checklist"][step_id].values() if v)
    total = len(step["checklist"])

    return jsonify({
        "step": step["title"],
        "item": item_text,
        "progress": f"{done}/{total}",
        "step_complete": done == total
    })


@implement_bp.route('/api/implement/code/<sid>', methods=['POST'])
def add_code_snippet(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    data = request.get_json() or {}
    snippet = data.get('snippet', '')
    filename = data.get('filename', '')

    if snippet:
        sessions[sid]["code_snippets"].append({
            "filename": filename,
            "code": snippet,
            "timestamp": datetime.now().isoformat()
        })

    return jsonify({
        "total_snippets": len(sessions[sid]["code_snippets"]),
        "latest": sessions[sid]["code_snippets"][-1] if sessions[sid]["code_snippets"] else None
    })


@implement_bp.route('/api/implement/state/<sid>', methods=['GET'])
def implement_state(sid):
    if sid not in sessions:
        return jsonify({"error": "無效的 session ID"}), 404

    progress = {}
    for s in IMPLEMENT_STEPS:
        done = sum(1 for v in sessions[sid]["checklist"][s["id"]].values() if v)
        total = len(s["checklist"])
        progress[s["id"]] = {"title": s["title"], "done": done, "total": total, "complete": done == total}

    return jsonify({
        "session_id": sid,
        "story_id": sessions[sid]["story_id"],
        "language": sessions[sid]["language"],
        "current_step": IMPLEMENT_STEPS[sessions[sid]["current_step"]]["title"],
        "progress": progress,
        "code_snippet_count": len(sessions[sid]["code_snippets"])
    })


@implement_bp.route('/api/implement/steps', methods=['GET'])
def list_steps():
    return jsonify({"steps": IMPLEMENT_STEPS, "languages": list(CODE_TEMPLATES.keys())})
