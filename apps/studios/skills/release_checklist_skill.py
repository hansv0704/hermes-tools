"""
release_checklist_skill.py — CCGS Phase 7.1
/release-checklist：8 類別發布清單

Phase 7 — Release 階段
"""

from flask import Blueprint, request, jsonify
import json
import os
import uuid
from datetime import datetime

release_checklist_bp = Blueprint('release_checklist', __name__)

CATEGORIES = {
    "build": {
        "name": "📦 建置與匯出",
        "items": [
            {"id": "b1", "text": "所有場景匯出無錯誤", "required": True},
            {"id": "b2", "text": "目標平台建置成功 (Windows/macOS/Linux/Web/Mobile)", "required": True},
            {"id": "b3", "text": "建置版本號已更新", "required": True},
            {"id": "b4", "text": "圖示與啟動畫面已設定", "required": False},
            {"id": "b5", "text": "壓縮與最佳化設定已確認", "required": False},
            {"id": "b6", "text": "數位簽章已套用 (如適用)", "required": False},
        ]
    },
    "qa": {
        "name": "🧪 品質保證",
        "items": [
            {"id": "q1", "text": "所有自動化測試通過", "required": True},
            {"id": "q2", "text": "完整試玩通關至少一次", "required": True},
            {"id": "q3", "text": "P0 與 P1 的 Bug 全部修復", "required": True},
            {"id": "q4", "text": "效能達到目標規格 (FPS/載入時間)", "required": True},
            {"id": "q5", "text": "邊界情況測試完成 (存檔損壞/斷線/Alt+Tab)", "required": False},
            {"id": "q6", "text": "相容性測試完成 (最低規格硬體)", "required": False},
        ]
    },
    "content": {
        "name": "📝 內容與文案",
        "items": [
            {"id": "c1", "text": "所有文字已校對 (無錯字/語法錯誤)", "required": True},
            {"id": "c2", "text": "在地化完成 (如有多語言)", "required": False},
            {"id": "c3", "text": "教學/說明文字完整", "required": True},
            {"id": "c4", "text": "遊戲內所有文字可讀性確認", "required": True},
            {"id": "c5", "text": "法律文字/隱私權政策/服務條款就位", "required": False},
        ]
    },
    "assets": {
        "name": "🎨 資產確認",
        "items": [
            {"id": "a1", "text": "所有美術資產已匯入且無遺失", "required": True},
            {"id": "a2", "text": "音訊檔案格式正確且正常播放", "required": True},
            {"id": "a3", "text": "授權檢查：所有第三方資產有合法授權", "required": True},
            {"id": "a4", "text": "暫時/開發用資產已移除", "required": True},
            {"id": "a5", "text": "資產命名規範一致", "required": False},
        ]
    },
    "store": {
        "name": "🏪 商店頁面",
        "items": [
            {"id": "s1", "text": "商店頁面文案完成", "required": True},
            {"id": "s2", "text": "宣傳截圖/預告片就緒", "required": True},
            {"id": "s3", "text": "定價策略已確認", "required": True},
            {"id": "s4", "text": "系統需求標示正確", "required": True},
            {"id": "s5", "text": "發售日期已設定", "required": False},
            {"id": "s6", "text": "標籤與分類設定完成", "required": False},
        ]
    },
    "infra": {
        "name": "🖥️ 基礎設施",
        "items": [
            {"id": "i1", "text": "伺服器容量已擴充至預估玩家數", "required": False},
            {"id": "i2", "text": "備份/災難復原方案就緒", "required": False},
            {"id": "i3", "text": "監控與警報系統已設定", "required": False},
            {"id": "i4", "text": "CDN 資產分發已設定", "required": False},
            {"id": "i5", "text": "資料庫遷移/初始化腳本已準備", "required": False},
        ]
    },
    "legal": {
        "name": "⚖️ 法務與合規",
        "items": [
            {"id": "l1", "text": "商標與版權登記完成", "required": False},
            {"id": "l2", "text": "GDPR/CCPA 等隱私合規確認", "required": False},
            {"id": "l3", "text": "年齡分級審核提交 (ESRB/PEGI/CERO)", "required": False},
            {"id": "l4", "text": "EULA/服務條款完稿", "required": False},
        ]
    },
    "marketing": {
        "name": "📣 行銷與社群",
        "items": [
            {"id": "m1", "text": "新聞稿/媒體包已發送", "required": False},
            {"id": "m2", "text": "社群媒體公告排程已設定", "required": False},
            {"id": "m3", "text": "實況主/評論者 Key 已分發", "required": False},
            {"id": "m4", "text": "發售活動/AMA 排程已確認", "required": False},
        ]
    },
}

# In-memory checklist states
_checklists = {}


def _get_project_dir(project_id: str) -> str:
    base = os.path.join(os.path.dirname(__file__), '..', 'projects', project_id)
    os.makedirs(base, exist_ok=True)
    return base


@release_checklist_bp.route('/api/release-checklist/categories', methods=['GET'])
def get_categories():
    """回傳所有 8 個類別及其檢查項目"""
    result = {}
    for key, cat in CATEGORIES.items():
        result[key] = {
            "name": cat["name"],
            "items": cat["items"],
            "required_count": sum(1 for i in cat["items"] if i["required"]),
            "total_count": len(cat["items"]),
        }
    return jsonify({"status": "ok", "categories": result})


@release_checklist_bp.route('/api/release-checklist/init', methods=['POST'])
def init_checklist():
    """為專案初始化發佈清單"""
    data = request.get_json() or {}
    project_id = data.get("project_id", "default")
    checklist_id = str(uuid.uuid4())[:8]

    items = []
    for cat_key, cat in CATEGORIES.items():
        for item in cat["items"]:
            items.append({
                "id": item["id"],
                "category": cat_key,
                "category_name": cat["name"],
                "text": item["text"],
                "required": item["required"],
                "status": "pending",
                "note": "",
            })

    _checklists[checklist_id] = {
        "project_id": project_id,
        "created_at": datetime.now().isoformat(),
        "items": items,
        "overall": "pending",
    }

    return jsonify({
        "status": "ok",
        "checklist_id": checklist_id,
        "total_items": len(items),
        "required_items": sum(1 for i in items if i["required"]),
    })


@release_checklist_bp.route('/api/release-checklist/<checklist_id>/update', methods=['POST'])
def update_item(checklist_id):
    """更新特定檢查項目的狀態"""
    if checklist_id not in _checklists:
        return jsonify({"status": "error", "message": "找不到此清單"}), 404

    data = request.get_json() or {}
    item_id = data.get("item_id")
    new_status = data.get("status", "pending")  # pending / passed / failed / skipped
    note = data.get("note", "")

    if new_status not in ("pending", "passed", "failed", "skipped"):
        return jsonify({"status": "error", "message": "無效狀態"}), 400

    cl = _checklists[checklist_id]
    for item in cl["items"]:
        if item["id"] == item_id:
            item["status"] = new_status
            item["note"] = note
            break

    # Recalculate overall
    required_items = [i for i in cl["items"] if i["required"]]
    if all(i["status"] == "passed" for i in required_items):
        cl["overall"] = "ready"
    elif any(i["status"] == "failed" for i in required_items):
        cl["overall"] = "blocked"
    else:
        cl["overall"] = "pending"

    return jsonify({
        "status": "ok",
        "item_status": new_status,
        "overall": cl["overall"],
    })


@release_checklist_bp.route('/api/release-checklist/<checklist_id>/report', methods=['GET'])
def get_report(checklist_id):
    """產出發佈清單完整報告"""
    if checklist_id not in _checklists:
        return jsonify({"status": "error", "message": "找不到此清單"}), 404

    cl = _checklists[checklist_id]

    # Group by category
    by_category = {}
    for item in cl["items"]:
        cat = item["category"]
        if cat not in by_category:
            by_category[cat] = {
                "name": item["category_name"],
                "items": [],
                "passed": 0,
                "failed": 0,
                "pending": 0,
                "skipped": 0,
            }
        by_category[cat]["items"].append(item)
        by_category[cat][item["status"]] += 1

    total = len(cl["items"])
    passed = sum(1 for i in cl["items"] if i["status"] == "passed")
    failed = sum(1 for i in cl["items"] if i["status"] == "failed")
    pending = sum(1 for i in cl["items"] if i["status"] == "pending")
    skipped = sum(1 for i in cl["items"] if i["status"] == "skipped")

    required_passed = sum(1 for i in cl["items"] if i["required"] and i["status"] == "passed")
    required_total = sum(1 for i in cl["items"] if i["required"])

    readiness = 0
    if required_total > 0:
        readiness = round(required_passed / required_total * 100, 1)

    return jsonify({
        "status": "ok",
        "checklist_id": checklist_id,
        "project_id": cl["project_id"],
        "created_at": cl["created_at"],
        "overall": cl["overall"],
        "summary": {
            "total": total, "passed": passed, "failed": failed,
            "pending": pending, "skipped": skipped,
            "required_passed": required_passed, "required_total": required_total,
            "readiness_pct": readiness,
        },
        "by_category": by_category,
    })


def register(manager):
    """註冊此 skill 的 Blueprint"""
    manager.app.register_blueprint(release_checklist_bp)
    return ["/api/release-checklist/..."]
