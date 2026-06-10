"""
profiling_skill.py — /profiling
Phase 6.1: 遊戲效能分析工具
CCGS 移植：profiling
"""

from flask import request, jsonify, session
import uuid
import time
from datetime import datetime


class ProfilingSkill:
    """效能分析 — FPS/CPU/GPU/Memory 追蹤、瓶頸識別、報告生成"""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.PHASES = {
            1: "目標設定",
            2: "基準測量",
            3: "瓶頸分析",
            4: "建議優化",
            5: "報告生成"
        }

    # ── API 端點 ─────────────────────────────────

    def register_routes(self, app):
        app.add_url_rule('/api/profiling/init', 'profiling_init',
                         self.init_session, methods=['POST'])
        app.add_url_rule('/api/profiling/respond', 'profiling_respond',
                         self.respond, methods=['POST'])
        app.add_url_rule('/api/profiling/state/<sid>', 'profiling_state',
                         self.get_state, methods=['GET'])
        app.add_url_rule('/api/profiling/phases', 'profiling_phases',
                         self.get_phases, methods=['GET'])
        app.add_url_rule('/api/profiling/save/<sid>', 'profiling_save',
                         self.save_report, methods=['POST'])

    # ── Phase 邏輯 ────────────────────────────────

    def init_session(self):
        data = request.get_json(silent=True) or {}
        sid = str(uuid.uuid4())[:8]

        self.sessions[sid] = {
            "phase": 1,
            "created_at": datetime.now().isoformat(),
            "target_fps": data.get("target_fps", 60),
            "platform": data.get("platform", "PC"),
            "engine": data.get("engine", "Godot 4.x"),
            "metrics": {
                "fps": {"avg": None, "min": None, "max": None, "1pct_low": None},
                "cpu": {"avg_ms": None, "peak_ms": None},
                "gpu": {"avg_ms": None, "peak_ms": None},
                "memory": {"avg_mb": None, "peak_mb": None, "leak_suspected": False},
                "draw_calls": None,
                "triangles": None,
                "batches": None
            },
            "bottlenecks": [],
            "recommendations": [],
            "fields": {}
        }

        return jsonify({
            "session_id": sid,
            "phase": 1,
            "phase_name": self.PHASES[1],
            "message": f"開始效能分析。目標：{self.sessions[sid]['target_fps']} FPS / {self.sessions[sid]['platform']}",
            "prompt": "請描述你觀察到的效能問題（掉幀場景、特定區域、特效密集時等）"
        })

    def respond(self):
        data = request.get_json(silent=True) or {}
        sid = data.get("session_id")
        field = data.get("field")
        value = data.get("value")

        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404

        s = self.sessions[sid]
        if field:
            s["fields"][field] = value

        # Phase 進階邏輯
        current = s["phase"]
        if current == 1 and s["fields"].get("symptoms"):
            s["phase"] = 2
        elif current == 2 and s["fields"].get("fps_avg") is not None:
            s["phase"] = 3
        elif current == 3 and s["fields"].get("bottleneck_identified"):
            s["phase"] = 4
        elif current == 4 and s["fields"].get("optimizations_proposed"):
            s["phase"] = 5

        return jsonify(self._phase_response(s))

    def get_state(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        return jsonify({
            "session_id": sid,
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "fields": s["fields"],
            "metrics": s["metrics"],
            "bottlenecks": s["bottlenecks"],
            "recommendations": s["recommendations"]
        })

    def get_phases(self):
        return jsonify({
            "phases": [
                {"id": i, "name": name, "description": self._phase_description(i)}
                for i, name in self.PHASES.items()
            ]
        })

    def save_report(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        report = self._build_report(s)
        filename = f"profiling_report_{sid}.md"
        # 儲存到 Game Studio 的輸出目錄
        import os
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return jsonify({
            "status": "saved",
            "path": out_path,
            "report": report
        })

    # ── 內部方法 ──────────────────────────────────

    def _phase_response(self, s):
        base = {
            "session_id": None,
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "message": "",
            "prompt": ""
        }

        prompts = {
            1: ("效能分析初始化", "請描述效能問題的具體場景（何時/何地/何條件下發生掉幀）"),
            2: ("基準測量階段", "輸入 FPS 數據：avg / min / max / 1% low，以及 CPU/GPU frame time (ms)"),
            3: ("瓶頸分析", "是否已識別瓶頸？CPU-bound / GPU-bound / Memory-bound？"),
            4: ("優化建議", "列出你考慮的優化方案（draw call batching / LOD / occlusion culling / shader 簡化等）"),
            5: ("報告生成", "所有數據收集完成。輸入 'save' 生成最終報告。")
        }

        msg, prompt = prompts.get(s["phase"], ("", ""))
        base["message"] = msg
        base["prompt"] = prompt
        return base

    def _phase_description(self, i):
        descs = {
            1: "定義目標 FPS、平台、引擎版本",
            2: "收集基準效能數據（FPS/CPU/GPU/Memory）",
            3: "識別效能瓶頸（CPU/GPU/Memory-bound）",
            4: "生成具體優化建議（附優先級）",
            5: "匯出完整效能分析報告"
        }
        return descs.get(i, "")

    def _build_report(self, s):
        lines = [
            "# 效能分析報告",
            f"日期：{s['created_at'][:10]}",
            f"目標：{s['target_fps']} FPS / {s['platform']} / {s['engine']}",
            "",
            "## 效能指標",
        ]
        m = s["metrics"]
        for key, val in m.items():
            if isinstance(val, dict):
                lines.append(f"- **{key}**: {val}")
            else:
                lines.append(f"- **{key}**: {val}")

        lines.append("\n## 瓶頸")
        for b in s["bottlenecks"]:
            lines.append(f"- {b}")

        lines.append("\n## 優化建議")
        for r in s["recommendations"]:
            lines.append(f"- {r}")

        lines.append("\n## 備註")
        for k, v in s["fields"].items():
            lines.append(f"- **{k}**: {v}")

        return "\n".join(lines)
