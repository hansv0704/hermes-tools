"""
asset_spec_skill.py — /asset-spec (Phase 4.1)
CCGS 移植：美術資產規格書
定義遊戲所需的所有美術資產清單與規格（角色/環境/道具/UI/VFX/音訊）
"""

import json
from datetime import datetime


ASSET_CATEGORIES = [
    {"id": "characters", "name": "角色", "icon": "🧑", "subtypes": ["主角", "NPC", "敵人", "Boss", "動物"]},
    {"id": "environments", "name": "環境", "icon": "🏞️", "subtypes": ["地形", "建築", "植被", "天空盒", "水體"]},
    {"id": "props", "name": "道具", "icon": "🗡️", "subtypes": ["武器", "防具", "消耗品", "任務物品", "可互動物件"]},
    {"id": "ui", "name": "UI", "icon": "🖥️", "subtypes": ["HUD", "選單", "圖示", "字體", "對話框"]},
    {"id": "vfx", "name": "VFX", "icon": "✨", "subtypes": ["粒子系統", "Shader", "後製", "動畫", "光影"]},
    {"id": "audio", "name": "音訊", "icon": "🔊", "subtypes": ["BGM", "SFX", "環境音", "UI音效", "語音"]},
    {"id": "animations", "name": "動畫", "icon": "🎬", "subtypes": ["待機", "移動", "攻擊", "死亡", "過場"]},
]

SPEC_PHASES = [
    {"id": 1, "name": "資產清單", "desc": "列出所有需要的資產"},
    {"id": 2, "name": "技術規格", "desc": "每個資產的解析度/格式/面數限制"},
    {"id": 3, "name": "風格指南", "desc": "每個資產的風格參考與描述"},
    {"id": 4, "name": "優先級排序", "desc": "MVP / Core / Polish 三層分級"},
    {"id": 5, "name": "產出規格書", "desc": "生成 asset-spec.md"},
]


class AssetSpecSession:
    def __init__(self, session_id, project_info=None):
        self.session_id = session_id
        self.project_info = project_info or {}
        self.state = "init"
        self.category_index = 0
        self.phase = 1
        self.assets = {cat["id"]: [] for cat in ASSET_CATEGORIES}
        self.style_notes = {}
        self.priorities = {}
        self.timeline = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "category_index": self.category_index,
            "phase": self.phase,
            "asset_count": sum(len(v) for v in self.assets.values()),
            "completed_categories": sum(1 for v in self.assets.values() if v),
            "total_categories": len(ASSET_CATEGORIES),
            "created_at": self.created_at,
        }


SESSIONS = {}


def handle_init(session_id="default", project_info=None):
    session = AssetSpecSession(session_id, project_info)
    SESSIONS[session_id] = session
    session.state = "category_select"

    category = ASSET_CATEGORIES[0]
    return {
        "session_id": session_id,
        "state": "category_select",
        "current_category": category,
        "categories": [{"id": c["id"], "name": c["name"], "icon": c["icon"]} for c in ASSET_CATEGORIES],
        "phases": SPEC_PHASES,
        "prompt": f"📋 開始建立資產規格書！目前類別：{category['icon']} {category['name']}\n請列出此類別需要的資產（每行一個，格式：資產名稱 | 簡短描述）",
    }


def handle_response(session_id, field, value):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Session not found"}

    if session.state == "category_select":
        if field == "category_assets":
            entries = [line.strip() for line in value.split('\n') if line.strip()]
            cat_id = ASSET_CATEGORIES[session.category_index]["id"]
            for entry in entries:
                parts = entry.split('|', 1)
                name = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else ""
                session.assets[cat_id].append({"name": name, "description": desc, "category": cat_id})

            session.category_index += 1
            if session.category_index < len(ASSET_CATEGORIES):
                cat = ASSET_CATEGORIES[session.category_index]
                return {
                    "state": "category_select",
                    "current_category": cat,
                    "progress": f"{session.category_index}/{len(ASSET_CATEGORIES)}",
                    "prompt": f"📋 下一個類別：{cat['icon']} {cat['name']}\n請列出此類別需要的資產",
                }
            else:
                session.state = "tech_specs"
                session.phase = 2
                count = sum(len(v) for v in session.assets.values())
                return {
                    "state": "tech_specs",
                    "total_assets": count,
                    "prompt": f"✅ 資產清單完成！共 {count} 項資產。\n🔧 Phase 2：請描述技術規格（格式範例：角色模型 / FBX / 1024x1024 貼圖 / <15K 三角面 / 2 LOD 等級）",
                }

    elif session.state == "tech_specs":
        session.tech_specs = value
        session.state = "style_guide"
        session.phase = 3
        return {
            "state": "style_guide",
            "prompt": "🎨 Phase 3：請描述美術風格指南（色盤/風格參考/情緒板/關鍵視覺描述）",
        }

    elif session.state == "style_guide":
        session.style_notes = {"content": value}
        session.state = "priorities"
        session.phase = 4
        return {
            "state": "priorities",
            "prompt": "📊 Phase 4：請將資產分三層優先級：\n- MVP（必須有才能玩）\n- Core（完整體驗）\n- Polish（加分項）\n\n格式：MVP: 資產名1, 資產名2\nCore: ...\nPolish: ...",
        }

    elif session.state == "priorities":
        session.priorities = {"content": value}
        session.state = "timeline"
        return {
            "state": "timeline",
            "prompt": "📅 最後一步：請提供預估時程（例如：MVP 2週 / Core 4週 / Polish 2週）",
        }

    elif session.state == "timeline":
        session.timeline = value
        session.state = "complete"
        session.phase = 5
        return {
            "state": "complete",
            "summary": get_summary(session),
            "message": "✅ 資產規格書完成！呼叫 /save 儲存。",
        }

    return {"error": f"Unknown state: {session.state}"}


def get_session(session_id):
    return SESSIONS.get(session_id)


def get_summary(session):
    return {
        "total_assets": sum(len(v) for v in session.assets.values()),
        "categories_completed": sum(1 for v in session.assets.values() if v),
        "assets_by_category": {k: len(v) for k, v in session.assets.items() if v},
    }


def finalize(session, output_dir=""):
    lines = ["# Asset Specification", "", f"## 資產規格書", f"建立時間：{session.created_at}", ""]

    lines.append("## 資產清單")
    for cat in ASSET_CATEGORIES:
        items = session.assets.get(cat["id"], [])
        if items:
            lines.append(f"### {cat['icon']} {cat['name']}")
            for item in items:
                lines.append(f"- **{item['name']}** — {item['description']}")
            lines.append("")

    if hasattr(session, 'tech_specs'):
        lines.append("## 技術規格")
        lines.append(session.tech_specs)
        lines.append("")

    if session.style_notes:
        lines.append("## 風格指南")
        lines.append(session.style_notes.get("content", ""))
        lines.append("")

    if session.priorities:
        lines.append("## 優先級排序")
        lines.append(session.priorities.get("content", ""))
        lines.append("")

    if session.timeline:
        lines.append("## 時程規劃")
        lines.append(session.timeline)
        lines.append("")

    doc = "\n".join(lines)

    saved_path = None
    if output_dir:
        from pathlib import Path
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        doc_path = out_path / "asset-spec.md"
        doc_path.write_text(doc, encoding='utf-8')
        saved_path = str(doc_path)

    return {"document": doc, "saved_path": saved_path, "summary": get_summary(session)}


asset_spec_skill = type('obj', (object,), {
    'handle_init': staticmethod(handle_init),
    'handle_response': staticmethod(handle_response),
    'get_session': staticmethod(get_session),
    'finalize': staticmethod(finalize),
    'CATEGORIES': ASSET_CATEGORIES,
    'PHASES': SPEC_PHASES,
})()
