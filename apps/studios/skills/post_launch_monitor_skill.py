"""
post_launch_monitor_skill.py — CCGS Phase 7.3
/post-launch-monitor：上線後監控

Phase 7 — Release 階段
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

post_launch_monitor_bp = Blueprint('post_launch_monitor', __name__)

# 7 類別監控定義
MONITOR_CATEGORIES = {
    "crashes": {
        "name": "💥 崩潰與錯誤",
        "metrics": [
            "crash_rate", "anr_rate", "fatal_error_count",
            "top_crash_stack", "crash_free_sessions_pct",
        ],
        "thresholds": {
            "crash_rate": {"good": 1.0, "warning": 3.0},  # %
            "crash_free_sessions_pct": {"good": 99.5, "warning": 97.0},
        }
    },
    "performance": {
        "name": "⚡ 效能",
        "metrics": [
            "avg_fps", "fps_below_30_pct", "avg_load_time_ms",
            "peak_memory_mb", "thermal_throttle_pct",
        ],
        "thresholds": {
            "avg_fps": {"good": 55, "warning": 30},
            "avg_load_time_ms": {"good": 3000, "warning": 8000},
            "fps_below_30_pct": {"good": 5, "warning": 15},
        }
    },
    "engagement": {
        "name": "📊 玩家參與度",
        "metrics": [
            "dau", "mau", "d1_retention", "d7_retention",
            "d30_retention", "avg_session_min", "avg_sessions_per_day",
        ],
        "thresholds": {
            "d1_retention": {"good": 40, "warning": 25},  # %
            "d7_retention": {"good": 20, "warning": 10},
        }
    },
    "economy": {
        "name": "💰 經濟與營收",
        "metrics": [
            "daily_revenue", "arpu", "arpdau",
            "conversion_rate", "ltv_d30", "refund_rate",
        ],
        "thresholds": {
            "conversion_rate": {"good": 3, "warning": 1},  # %
            "refund_rate": {"good": 2, "warning": 5},
        }
    },
    "community": {
        "name": "💬 社群與評價",
        "metrics": [
            "store_rating", "recent_rating", "review_count",
            "positive_review_pct", "social_sentiment_score",
        ],
        "thresholds": {
            "store_rating": {"good": 4.0, "warning": 3.0},
            "positive_review_pct": {"good": 80, "warning": 60},
        }
    },
    "technical": {
        "name": "🔧 技術健康",
        "metrics": [
            "server_uptime_pct", "api_latency_p95_ms",
            "cdn_availability", "login_success_rate",
            "matchmaking_wait_sec",
        ],
        "thresholds": {
            "server_uptime_pct": {"good": 99.9, "warning": 99.0},
            "login_success_rate": {"good": 99.0, "warning": 95.0},
            "api_latency_p95_ms": {"good": 200, "warning": 500},
        }
    },
    "alerts": {
        "name": "🚨 即時警報",
        "metrics": [
            "active_alerts", "critical_alerts",
            "recent_incidents_24h", "mttr_minutes",
        ],
        "thresholds": {
            "active_alerts": {"good": 0, "warning": 3},
            "critical_alerts": {"good": 0, "warning": 1},
        }
    },
}

_monitors = {}


@post_launch_monitor_bp.route('/api/post-launch-monitor/categories', methods=['GET'])
def get_categories():
    """回傳 7 類別監控定義"""
    result = {}
    for key, cat in MONITOR_CATEGORIES.items():
        result[key] = {
            "name": cat["name"],
            "metrics": cat["metrics"],
            "thresholds": cat.get("thresholds", {}),
        }
    return jsonify({"status": "ok", "categories": result})


@post_launch_monitor_bp.route('/api/post-launch-monitor/init', methods=['POST'])
def init_monitor():
    """為專案初始化上線後監控面板"""
    data = request.get_json() or {}
    project_id = data.get("project_id", "default")
    launch_date = data.get("launch_date", datetime.now().strftime("%Y-%m-%d"))

    monitor_id = str(uuid.uuid4())[:8]
    snapshot_time = datetime.now().isoformat()

    _monitors[monitor_id] = {
        "project_id": project_id,
        "launch_date": launch_date,
        "created_at": snapshot_time,
        "snapshots": [],
        "categories": {},
    }

    # Initialize all categories
    for cat_key, cat_def in MONITOR_CATEGORIES.items():
        _monitors[monitor_id]["categories"][cat_key] = {
            "name": cat_def["name"],
            "metrics": {},
        }
        for metric in cat_def["metrics"]:
            _monitors[monitor_id]["categories"][cat_key]["metrics"][metric] = {
                "current": None,
                "status": "unknown",
                "trend": "stable",
            }

    return jsonify({
        "status": "ok",
        "monitor_id": monitor_id,
        "project_id": project_id,
        "launch_date": launch_date,
    })


@post_launch_monitor_bp.route('/api/post-launch-monitor/<monitor_id>/snapshot', methods=['POST'])
def add_snapshot(monitor_id):
    """提交一個監控快照"""
    if monitor_id not in _monitors:
        return jsonify({"status": "error", "message": "找不到此監控"}), 404

    data = request.get_json() or {}
    cat_key = data.get("category")
    metrics_data = data.get("metrics", {})

    if cat_key not in MONITOR_CATEGORIES:
        return jsonify({"status": "error", "message": f"無效類別，可用：{list(MONITOR_CATEGORIES.keys())}"}), 400

    mon = _monitors[monitor_id]
    cat = mon["categories"][cat_key]
    thresholds = MONITOR_CATEGORIES[cat_key].get("thresholds", {})

    for metric, value in metrics_data.items():
        if metric in cat["metrics"]:
            old = cat["metrics"][metric]["current"]
            cat["metrics"][metric]["current"] = value

            # Trend
            if old is not None and value is not None:
                if value > old * 1.05:
                    cat["metrics"][metric]["trend"] = "up"
                elif value < old * 0.95:
                    cat["metrics"][metric]["trend"] = "down"
                else:
                    cat["metrics"][metric]["trend"] = "stable"

            # Status check against thresholds
            if metric in thresholds and value is not None:
                t = thresholds[metric]
                if value <= t["good"] if "crash_rate" in metric or "refund" in metric or "api_latency" in metric or "fps_below" in metric or "load_time" in metric or "active_alert" in metric or "critical_alert" in metric or "matchmaking" in metric else value >= t["good"]:
                    cat["metrics"][metric]["status"] = "healthy"
                elif "warning" in t:
                    if "crash_rate" in metric or "refund" in metric or "api_latency" in metric or "fps_below" in metric or "load_time" in metric or "active_alert" in metric or "critical_alert" in metric or "matchmaking" in metric:
                        if value <= t["warning"]:
                            cat["metrics"][metric]["status"] = "warning"
                        else:
                            cat["metrics"][metric]["status"] = "critical"
                    else:
                        if value >= t["warning"]:
                            cat["metrics"][metric]["status"] = "warning"
                        else:
                            cat["metrics"][metric]["status"] = "critical"

    snapshot = {
        "time": datetime.now().isoformat(),
        "category": cat_key,
        "metrics": metrics_data,
    }
    mon["snapshots"].append(snapshot)

    return jsonify({
        "status": "ok",
        "snapshot_count": len(mon["snapshots"]),
    })


@post_launch_monitor_bp.route('/api/post-launch-monitor/<monitor_id>/report', methods=['GET'])
def get_monitor_report(monitor_id):
    """產出監控報告"""
    if monitor_id not in _monitors:
        return jsonify({"status": "error", "message": "找不到此監控"}), 404

    mon = _monitors[monitor_id]

    health_summary = {}
    criticals = []
    warnings = []

    for cat_key, cat in mon["categories"].items():
        h = 0
        w = 0
        c = 0
        for metric, mdata in cat["metrics"].items():
            if mdata["status"] == "healthy":
                h += 1
            elif mdata["status"] == "warning":
                w += 1
                warnings.append({
                    "category": cat_key,
                    "category_name": cat["name"],
                    "metric": metric,
                    "value": mdata["current"],
                    "trend": mdata["trend"],
                })
            elif mdata["status"] == "critical":
                c += 1
                criticals.append({
                    "category": cat_key,
                    "category_name": cat["name"],
                    "metric": metric,
                    "value": mdata["current"],
                    "trend": mdata["trend"],
                })

        health_summary[cat_key] = {
            "name": cat["name"],
            "healthy": h, "warning": w, "critical": c,
            "total": h + w + c,
        }

    overall = "healthy"
    if criticals:
        overall = "critical"
    elif warnings:
        overall = "warning"

    return jsonify({
        "status": "ok",
        "monitor_id": monitor_id,
        "project_id": mon["project_id"],
        "launch_date": mon["launch_date"],
        "snapshot_count": len(mon["snapshots"]),
        "overall": overall,
        "health_summary": health_summary,
        "critical_alerts": criticals,
        "warnings": warnings,
    })


@post_launch_monitor_bp.route('/api/post-launch-monitor/<monitor_id>/state', methods=['GET'])
def get_state(monitor_id):
    """查詢監控狀態"""
    if monitor_id not in _monitors:
        return jsonify({"status": "error", "message": "找不到此監控"}), 404

    mon = _monitors[monitor_id]
    return jsonify({
        "status": "ok",
        "monitor_id": monitor_id,
        "project_id": mon["project_id"],
        "launch_date": mon["launch_date"],
        "snapshot_count": len(mon["snapshots"]),
        "categories": list(mon["categories"].keys()),
    })


def register(manager):
    """註冊此 skill 的 Blueprint"""
    manager.app.register_blueprint(post_launch_monitor_bp)
    return ["/api/post-launch-monitor/..."]
