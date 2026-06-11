"""
asset_audit_skill.py — /asset-audit
Phase 6.3: 遊戲資產審計工具
CCGS 移植：asset-audit
"""

from flask import request, jsonify
import uuid
from datetime import datetime


class AssetAuditSkill:
    """資產審計 — 未使用資產偵測、命名規範、品質審查、優化建議"""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.PHASES = {
            1: "範圍掃描",
            2: "命名規範檢查",
            3: "未使用資產偵測",
            4: "品質審查",
            5: "報告生成"
        }

        self.CATEGORIES = [
            "textures", "models", "audio", "animations",
            "shaders", "fonts", "scenes", "scripts", "ui"
        ]

        self.NAMING_STANDARDS = {
            "textures": "T_ prefix, PascalCase (T_Wall_Stone_Diffuse.png)",
            "models": "SM_ / SK_ prefix (SM_Chair_01.fbx, SK_Player_Rig.fbx)",
            "audio": "A_ prefix + type (A_SFX_Footstep.wav, A_MUS_MainTheme.ogg)",
            "animations": "AM_ prefix (AM_Player_Run.anim)",
            "ui": "UI_ prefix (UI_Button_Start.png)",
            "scenes": "PascalCase + 場景類型後綴 (MainMenu.tscn, Level_01.tscn)",
            "scripts": "PascalCase .gd / .cs (PlayerController.gd)"
        }

    def register_routes(self, app):
        app.add_url_rule('/api/asset-audit/init', 'asset_audit_init',
                         self.init_session, methods=['POST'])
        app.add_url_rule('/api/asset-audit/respond', 'asset_audit_respond',
                         self.respond, methods=['POST'])
        app.add_url_rule('/api/asset-audit/state/<sid>', 'asset_audit_state',
                         self.get_state, methods=['GET'])
        app.add_url_rule('/api/asset-audit/phases', 'asset_audit_phases',
                         self.get_phases, methods=['GET'])
        app.add_url_rule('/api/asset-audit/save/<sid>', 'asset_audit_save',
                         self.save_report, methods=['POST'])

    def init_session(self):
        data = request.get_json(silent=True) or {}
        sid = str(uuid.uuid4())[:8]

        self.sessions[sid] = {
            "phase": 1,
            "created_at": datetime.now().isoformat(),
            "project_path": data.get("project_path", ""),
            "categories_scanned": data.get("categories", self.CATEGORIES),
            "total_assets": 0,
            "unused_assets": [],
            "naming_violations": [],
            "quality_issues": [],
            "size_issues": [],
            "fields": {}
        }

        return jsonify({
            "session_id": sid,
            "phase": 1,
            "phase_name": self.PHASES[1],
            "message": "開始資產審計",
            "prompt": "輸入專案路徑及要掃描的資產類別（預設全部 9 類）",
            "categories": self.CATEGORIES,
            "naming_standards": self.NAMING_STANDARDS
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
        if current == 1 and s["fields"].get("scan_complete"):
            s["phase"] = 2
        elif current == 2 and s["fields"].get("naming_check_done"):
            s["phase"] = 3
        elif current == 3 and s["fields"].get("unused_check_done"):
            s["phase"] = 4
        elif current == 4 and s["fields"].get("quality_check_done"):
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
            "total_assets": s["total_assets"],
            "unused_count": len(s["unused_assets"]),
            "violation_count": len(s["naming_violations"]),
            "quality_issue_count": len(s["quality_issues"]),
            "fields": s["fields"]
        })

    def get_phases(self):
        return jsonify({
            "phases": [
                {"id": i, "name": name, "description": self._phase_description(i)}
                for i, name in self.PHASES.items()
            ],
            "categories": self.CATEGORIES,
            "naming_standards": self.NAMING_STANDARDS
        })

    def save_report(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        report = self._build_report(s)
        import os
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"asset_audit_{sid}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return jsonify({"status": "saved", "path": out_path, "report": report})

    def _phase_response(self, s):
        prompts = {
            1: ("範圍掃描", "掃描專案目錄，回報各類別資產數量。完成後輸入 'scan_complete: true'"),
            2: ("命名規範檢查", "檢查所有資產是否符合命名規範，回報違規清單"),
            3: ("未使用資產偵測", "檢查哪些資產未被任何場景或腳本引用"),
            4: ("品質審查", "檢查資產解析度、多邊形數、音訊位元率等品質指標"),
            5: ("報告生成", "審計完成。輸入 'save' 匯出完整報告。")
        }
        msg, prompt = prompts.get(s["phase"], ("", ""))
        return {
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "message": msg,
            "prompt": prompt,
            "naming_standards": self.NAMING_STANDARDS if s["phase"] == 2 else None
        }

    def _phase_description(self, i):
        descs = {
            1: "掃描專案目錄，統計各類別資產數量",
            2: "依命名規範檢查所有資產檔名",
            3: "偵測未被引用的孤立資產",
            4: "檢查資產品質（解析度/多邊形數/檔案大小）",
            5: "匯出資產審計報告"
        }
        return descs.get(i, "")

    def _build_report(self, s):
        lines = [
            "# 資產審計報告",
            f"日期：{s['created_at'][:10]}",
            f"專案：{s['project_path']}",
            f"總資產數：{s['total_assets']}",
            "",
            f"## 命名違規（{len(s['naming_violations'])} 項）",
        ]
        for v in s["naming_violations"]:
            lines.append(f"- {v}")

        lines.append(f"\n## 未使用資產（{len(s['unused_assets'])} 項）")
        for u in s["unused_assets"]:
            lines.append(f"- {u}")

        lines.append(f"\n## 品質問題（{len(s['quality_issues'])} 項）")
        for q in s["quality_issues"]:
            lines.append(f"- {q}")

        lines.append("\n## 優化建議")
        lines.append("- 移除或封存未使用的資產以減少建置大小")
        lines.append("- 修正命名違規以維持專案一致性")
        lines.append("- 對超標資產進行壓縮或降級處理")

        return "\n".join(lines)
