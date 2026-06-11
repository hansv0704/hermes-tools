"""
changelog_skill.py — CCGS Phase 7.2
/changelog：變更日誌生成

Phase 7 — Release 階段
"""

from flask import Blueprint, request, jsonify
import os
import json
from datetime import datetime

changelog_bp = Blueprint('changelog', __name__)

CHANGELOG_TYPES = {
    "added": "🚀 新增功能",
    "changed": "🔄 變更",
    "deprecated": "⚠️ 棄用",
    "removed": "🗑️ 移除",
    "fixed": "🐛 修復",
    "security": "🔒 安全性",
}

# In-memory changelog store
_changelogs = {}


def _get_project_dir(project_id: str) -> str:
    base = os.path.join(os.path.dirname(__file__), '..', 'projects', project_id)
    os.makedirs(base, exist_ok=True)
    return base


@changelog_bp.route('/api/changelog/types', methods=['GET'])
def get_types():
    """回傳 changelog 類型定義"""
    return jsonify({"status": "ok", "types": CHANGELOG_TYPES})


@changelog_bp.route('/api/changelog/init', methods=['POST'])
def init_changelog():
    """初始化一個新的 changelog"""
    data = request.get_json() or {}
    project_id = data.get("project_id", "default")
    version = data.get("version", "0.1.0")
    title = data.get("title", f"Version {version}")

    changelog_id = f"{project_id}_{version}"

    _changelogs[changelog_id] = {
        "project_id": project_id,
        "version": version,
        "title": title,
        "release_date": data.get("release_date", ""),
        "created_at": datetime.now().isoformat(),
        "entries": {key: [] for key in CHANGELOG_TYPES},
        "footer": "",
    }

    return jsonify({
        "status": "ok",
        "changelog_id": changelog_id,
        "version": version,
    })


@changelog_bp.route('/api/changelog/<changelog_id>/add', methods=['POST'])
def add_entry(changelog_id):
    """新增一條 changelog 條目"""
    if changelog_id not in _changelogs:
        return jsonify({"status": "error", "message": "找不到此 changelog"}), 404

    data = request.get_json() or {}
    entry_type = data.get("type", "added")
    text = data.get("text", "")

    if entry_type not in CHANGELOG_TYPES:
        return jsonify({"status": "error", "message": f"無效類型，可用：{list(CHANGELOG_TYPES.keys())}"}), 400

    if not text.strip():
        return jsonify({"status": "error", "message": "條目內容不可為空"}), 400

    _changelogs[changelog_id]["entries"][entry_type].append(text)

    return jsonify({
        "status": "ok",
        "type": entry_type,
        "entry": text,
        "total_entries": sum(len(v) for v in _changelogs[changelog_id]["entries"].values()),
    })


@changelog_bp.route('/api/changelog/<changelog_id>/generate', methods=['POST'])
def generate_changelog(changelog_id):
    """生成 Markdown 格式的 changelog"""
    if changelog_id not in _changelogs:
        return jsonify({"status": "error", "message": "找不到此 changelog"}), 404

    cl = _changelogs[changelog_id]
    data = request.get_json() or {}
    cl["release_date"] = data.get("release_date", datetime.now().strftime("%Y-%m-%d"))
    cl["footer"] = data.get("footer", "")

    lines = []
    lines.append(f"# {cl['title']}")
    lines.append("")
    lines.append(f"**發布日期：** {cl['release_date']}")
    lines.append("")

    for entry_type, label in CHANGELOG_TYPES.items():
        entries = cl["entries"].get(entry_type, [])
        if entries:
            lines.append(f"## {label}")
            lines.append("")
            for e in entries:
                lines.append(f"- {e}")
            lines.append("")

    if cl["footer"]:
        lines.append("---")
        lines.append("")
        lines.append(cl["footer"])
        lines.append("")

    markdown = "\n".join(lines)

    # Save to project directory
    project_dir = _get_project_dir(cl["project_id"])
    changelog_path = os.path.join(project_dir, f"CHANGELOG_{cl['version']}.md")
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return jsonify({
        "status": "ok",
        "markdown": markdown,
        "saved_to": changelog_path,
    })


@changelog_bp.route('/api/changelog/<changelog_id>/state', methods=['GET'])
def get_state(changelog_id):
    """查詢當前 changelog 狀態"""
    if changelog_id not in _changelogs:
        return jsonify({"status": "error", "message": "找不到此 changelog"}), 404

    cl = _changelogs[changelog_id]
    summary = {
        entry_type: len(entries)
        for entry_type, entries in cl["entries"].items()
    }

    return jsonify({
        "status": "ok",
        "changelog_id": changelog_id,
        "version": cl["version"],
        "release_date": cl["release_date"],
        "summary": summary,
        "total_entries": sum(summary.values()),
    })


def register(manager):
    """註冊此 skill 的 Blueprint"""
    manager.app.register_blueprint(changelog_bp)
    return ["/api/changelog/..."]
