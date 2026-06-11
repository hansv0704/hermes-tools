"""
accessibility_review_skill.py — /accessibility-review
Phase 6.4: 遊戲無障礙審查
CCGS 移植：accessibility-review
"""

from flask import request, jsonify
import uuid
from datetime import datetime


class AccessibilityReviewSkill:
    """無障礙審查 — WCAG 啟發式 + 遊戲專用最佳實踐"""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.PHASES = {
            1: "範圍定義",
            2: "視覺無障礙",
            3: "聽覺無障礙",
            4: "操作無障礙",
            5: "認知無障礙",
            6: "裁決與報告"
        }

        self.CHECKLIST = {
            "visual": [
                {"id": "V1", "name": "色盲友善", "desc": "關鍵資訊不依賴顏色區分，支援色盲模式"},
                {"id": "V2", "name": "對比度", "desc": "文字與背景對比度 ≥ 4.5:1（一般）/ 3:1（大字）"},
                {"id": "V3", "name": "字體大小", "desc": "最小字體 ≥ 14px，支援縮放至 200%"},
                {"id": "V4", "name": "閃爍控制", "desc": "無 >3Hz 閃爍，避免光敏性癲癇觸發"},
                {"id": "V5", "name": "HUD 可讀性", "desc": "HUD 元素在所有背景下可辨識"},
                {"id": "V6", "name": "字幕背景", "desc": "字幕有半透明背景或外框以提高可讀性"}
            ],
            "audio": [
                {"id": "A1", "name": "字幕", "desc": "所有對話提供字幕，包含說話者標示"},
                {"id": "A2", "name": "聽覺提示視覺化", "desc": "重要音效有對應的視覺提示"},
                {"id": "A3", "name": "音量獨立控制", "desc": "主音量/音效/語音/音樂可分開調整"},
                {"id": "A4", "name": "單聲道支援", "desc": "支援單聲道輸出，避免立體聲依賴"}
            ],
            "motor": [
                {"id": "M1", "name": "按鍵自訂", "desc": "所有操作可重新綁定按鍵"},
                {"id": "M2", "name": "長按替代", "desc": "提供長按/連打的替代方案"},
                {"id": "M3", "name": "反應時間", "desc": "QTE 等限時操作可調整或關閉"},
                {"id": "M4", "name": "陀螺儀替代", "desc": "體感操作提供傳統輸入替代方案"},
                {"id": "M5", "name": "滑鼠/鍵盤/手把", "desc": "支援多種輸入裝置"},
                {"id": "M6", "name": "靈敏度調整", "desc": "相機/瞄準靈敏度可大幅調整"}
            ],
            "cognitive": [
                {"id": "C1", "name": "難度選項", "desc": "提供多個難度等級"},
                {"id": "C2", "name": "導引與提示", "desc": "清晰的任務目標與方向導引"},
                {"id": "C3", "name": "UI 簡潔", "desc": "避免資訊過載，重要資訊優先展示"},
                {"id": "C4", "name": "教學", "desc": "互動式教學，可隨時回顧"},
                {"id": "C5", "name": "暫停與儲存", "desc": "隨時可暫停/儲存，無懲罰"}
            ]
        }

    def register_routes(self, app):
        app.add_url_rule('/api/accessibility-review/init', 'acc_init',
                         self.init_session, methods=['POST'])
        app.add_url_rule('/api/accessibility-review/respond', 'acc_respond',
                         self.respond, methods=['POST'])
        app.add_url_rule('/api/accessibility-review/state/<sid>', 'acc_state',
                         self.get_state, methods=['GET'])
        app.add_url_rule('/api/accessibility-review/checklist', 'acc_checklist',
                         self.get_checklist, methods=['GET'])
        app.add_url_rule('/api/accessibility-review/save/<sid>', 'acc_save',
                         self.save_report, methods=['POST'])

    def init_session(self):
        data = request.get_json(silent=True) or {}
        sid = str(uuid.uuid4())[:8]

        self.sessions[sid] = {
            "phase": 1,
            "created_at": datetime.now().isoformat(),
            "game_name": data.get("game_name", "未命名"),
            "target_rating": data.get("target_rating", "AA"),  # A / AA / AAA
            "results": {},
            "overall_score": 0,
            "verdict": "",
            "fields": {}
        }

        return jsonify({
            "session_id": sid,
            "phase": 1,
            "phase_name": self.PHASES[1],
            "message": f"無障礙審查：{self.sessions[sid]['game_name']} / 目標等級：{self.sessions[sid]['target_rating']}",
            "prompt": "選擇要審查的類別：visual / audio / motor / cognitive / all",
            "categories": list(self.CHECKLIST.keys()),
            "total_checklist_items": sum(len(v) for v in self.CHECKLIST.values())
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
        if current == 1 and s["fields"].get("category"):
            s["phase"] = 2
        elif current == 2 and s["fields"].get("visual_done"):
            s["phase"] = 3
        elif current == 3 and s["fields"].get("audio_done"):
            s["phase"] = 4
        elif current == 4 and s["fields"].get("motor_done"):
            s["phase"] = 5
        elif current == 5 and s["fields"].get("cognitive_done"):
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
            "results": s["results"],
            "overall_score": s["overall_score"],
            "verdict": s["verdict"],
            "fields": s["fields"]
        })

    def get_checklist(self):
        return jsonify({
            "checklist": self.CHECKLIST,
            "total_items": sum(len(v) for v in self.CHECKLIST.values()),
            "ratings": {
                "A": "基本無障礙（滿足核心項目）",
                "AA": "良好無障礙（滿足大部分項目）",
                "AAA": "卓越無障礙（滿足所有項目）"
            }
        })

    def save_report(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        report = self._build_report(s)
        import os
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"accessibility_report_{sid}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return jsonify({"status": "saved", "path": out_path, "report": report})

    def _phase_response(self, s):
        prompts = {
            1: ("範圍定義", "選擇審查類別：visual / audio / motor / cognitive / all"),
            2: ("視覺無障礙", f"審查 {len(self.CHECKLIST['visual'])} 項視覺項目。完成後輸入 'visual_done: true'"),
            3: ("聽覺無障礙", f"審查 {len(self.CHECKLIST['audio'])} 項聽覺項目。完成後輸入 'audio_done: true'"),
            4: ("操作無障礙", f"審查 {len(self.CHECKLIST['motor'])} 項操作項目。完成後輸入 'motor_done: true'"),
            5: ("認知無障礙", f"審查 {len(self.CHECKLIST['cognitive'])} 項認知項目。完成後輸入 'cognitive_done: true'"),
            6: ("裁決與報告", "所有類別審查完成。系統將計算總分。輸入 'save' 匯出報告。")
        }
        msg, prompt = prompts.get(s["phase"], ("", ""))
        resp = {
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "message": msg,
            "prompt": prompt
        }
        if s["phase"] in [2, 3, 4, 5]:
            cat_map = {2: "visual", 3: "audio", 4: "motor", 5: "cognitive"}
            resp["checklist"] = self.CHECKLIST.get(cat_map.get(s["phase"], ""), [])
        return resp

    def _phase_description(self, i):
        descs = {
            1: "定義目標無障礙等級 (A/AA/AAA)",
            2: "審查視覺無障礙（色盲/對比度/字體/閃爍/HUD/字幕）",
            3: "審查聽覺無障礙（字幕/視覺提示/音量控制/單聲道）",
            4: "審查操作無障礙（按鍵自訂/替代方案/多裝置/靈敏度）",
            5: "審查認知無障礙（難度/導引/UI簡潔/教學/暫停）",
            6: "裁決與完整報告匯出"
        }
        return descs.get(i, "")

    def _build_report(self, s):
        lines = [
            "# 無障礙審查報告",
            f"遊戲：{s['game_name']}",
            f"日期：{s['created_at'][:10]}",
            f"目標等級：{s['target_rating']}",
            f"總分：{s['overall_score']}",
            f"裁決：{s['verdict']}",
            "",
            "## 逐類別結果"
        ]
        for cat, items in self.CHECKLIST.items():
            lines.append(f"\n### {cat}")
            for item in items:
                result = s["results"].get(item["id"], "未審查")
                icon = "✅" if result == "pass" else ("❌" if result == "fail" else "⬜")
                lines.append(f"- {icon} **{item['id']}** {item['name']}: {item['desc']}")

        lines.append("\n## 建議改進項目")
        for cat, items in self.CHECKLIST.items():
            for item in items:
                if s["results"].get(item["id"]) == "fail":
                    lines.append(f"- [{item['id']}] {item['name']}: {item['desc']}")

        return "\n".join(lines)
