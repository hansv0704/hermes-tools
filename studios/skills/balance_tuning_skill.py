"""
balance_tuning_skill.py — /balance-tuning
Phase 6.2: 遊戲數值平衡調整工具
CCGS 移植：balance-tuning
"""

from flask import request, jsonify
import uuid
from datetime import datetime


class BalanceTuningSkill:
    """平衡調整 — 數值矩陣、變數追蹤、敏感度分析、調整建議"""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.PHASES = {
            1: "範圍定義",
            2: "基準數據",
            3: "平衡矩陣",
            4: "敏感度分析",
            5: "調整建議",
            6: "報告生成"
        }

    def register_routes(self, app):
        app.add_url_rule('/api/balance-tuning/init', 'balance_init',
                         self.init_session, methods=['POST'])
        app.add_url_rule('/api/balance-tuning/respond', 'balance_respond',
                         self.respond, methods=['POST'])
        app.add_url_rule('/api/balance-tuning/state/<sid>', 'balance_state',
                         self.get_state, methods=['GET'])
        app.add_url_rule('/api/balance-tuning/phases', 'balance_phases',
                         self.get_phases, methods=['GET'])
        app.add_url_rule('/api/balance-tuning/save/<sid>', 'balance_save',
                         self.save_report, methods=['POST'])
        app.add_url_rule('/api/balance-tuning/matrix/<sid>', 'balance_matrix',
                         self.get_matrix, methods=['GET'])

    def init_session(self):
        data = request.get_json(silent=True) or {}
        sid = str(uuid.uuid4())[:8]

        self.sessions[sid] = {
            "phase": 1,
            "created_at": datetime.now().isoformat(),
            "game_name": data.get("game_name", "未命名"),
            "balance_type": data.get("balance_type", "combat"),  # combat/economy/progression
            "variables": [],
            "targets": {},
            "matrix": {},
            "sensitivity_results": {},
            "recommendations": [],
            "fields": {}
        }

        return jsonify({
            "session_id": sid,
            "phase": 1,
            "phase_name": self.PHASES[1],
            "message": f"開始平衡調整：{self.sessions[sid]['game_name']} / 類型：{self.sessions[sid]['balance_type']}",
            "prompt": "定義需要平衡的變數（如：攻擊力、防禦力、價格、掉落率等），以逗號分隔"
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

        current = s["phase"]
        if current == 1 and s["fields"].get("variables"):
            s["variables"] = [v.strip() for v in s["fields"]["variables"].split(",")]
            s["phase"] = 2
        elif current == 2 and s["fields"].get("baseline_values"):
            s["phase"] = 3
        elif current == 3 and s["fields"].get("matrix_complete"):
            s["phase"] = 4
        elif current == 4 and s["fields"].get("sensitivity_done"):
            s["phase"] = 5
        elif current == 5 and s["fields"].get("recommendations"):
            s["phase"] = 6

        return jsonify(self._phase_response(s))

    def get_state(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        return jsonify({
            "session_id": sid,
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "variables": s["variables"],
            "targets": s["targets"],
            "matrix": s["matrix"],
            "sensitivity_results": s["sensitivity_results"],
            "recommendations": s["recommendations"],
            "fields": s["fields"]
        })

    def get_phases(self):
        return jsonify({
            "phases": [
                {"id": i, "name": name, "description": self._phase_description(i)}
                for i, name in self.PHASES.items()
            ]
        })

    def get_matrix(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        return jsonify({
            "variables": s["variables"],
            "matrix": s["matrix"],
            "sensitivity": s["sensitivity_results"]
        })

    def save_report(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        report = self._build_report(s)
        import os
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"balance_report_{sid}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return jsonify({"status": "saved", "path": out_path, "report": report})

    def _phase_response(self, s):
        prompts = {
            1: ("範圍定義", "輸入需要平衡的變數名稱（逗號分隔），如：attack, defense, hp, cost"),
            2: ("基準數據", "輸入每個變數的基準值與容許範圍，格式：attack=10±2, defense=5±1"),
            3: ("平衡矩陣", "輸入單位之間的互動關係矩陣（如：A對B的傷害倍率）"),
            4: ("敏感度分析", "輸入想要測試的變數波動範圍（如 ±10%），系統將計算影響"),
            5: ("調整建議", "輸入調整方案（如：降低 attack 5%，提高 defense 10%）"),
            6: ("報告生成", "所有數據已收集。輸入 'save' 生成平衡報告。")
        }
        msg, prompt = prompts.get(s["phase"], ("", ""))
        return {
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "message": msg,
            "prompt": prompt
        }

    def _phase_description(self, i):
        descs = {
            1: "定義需要平衡的遊戲系統範圍",
            2: "收集所有變數的基準數值",
            3: "建立變數之間的互動矩陣",
            4: "對關鍵變數進行敏感度分析",
            5: "根據分析結果提出調整建議",
            6: "匯出完整平衡調整報告"
        }
        return descs.get(i, "")

    def _build_report(self, s):
        lines = [
            "# 平衡調整報告",
            f"遊戲：{s['game_name']}",
            f"日期：{s['created_at'][:10]}",
            f"類型：{s['balance_type']}",
            "",
            "## 變數清單",
        ]
        for v in s["variables"]:
            lines.append(f"- {v}")

        lines.append("\n## 平衡矩陣")
        for k, v in s["matrix"].items():
            lines.append(f"- {k}: {v}")

        lines.append("\n## 敏感度分析")
        for k, v in s["sensitivity_results"].items():
            lines.append(f"- {k}: {v}")

        lines.append("\n## 調整建議")
        for r in s["recommendations"]:
            lines.append(f"- {r}")

        return "\n".join(lines)
