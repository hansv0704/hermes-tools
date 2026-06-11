"""
polish_pass_skill.py — /polish-pass
Phase 6.5: 遊戲打磨通行證
CCGS 移植：polish-pass
"""

from flask import request, jsonify
import uuid
from datetime import datetime


class PolishPassSkill:
    """打磨通行證 — 7 類別打磨清單、優先級分類、追蹤管理"""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.PHASES = {
            1: "範圍定義",
            2: "視覺打磨",
            3: "音訊打磨",
            4: "UI/UX 打磨",
            5: "遊戲感打磨",
            6: "效能打磨",
            7: "報告生成"
        }

        self.CATEGORIES = {
            "visual": {
                "name": "視覺打磨",
                "items": [
                    "粒子效果（落地灰塵、腳步塵埃、攻擊軌跡）",
                    "畫面震動（打擊感、爆炸）",
                    "轉場效果（場景切換淡入淡出）",
                    "光影一致性",
                    "材質細節與法線貼圖",
                    "LOD 彈出距離調整",
                    "後處理效果（Bloom、DOF、色調映射）",
                    "UI 動畫（按鈕懸停、過渡）"
                ]
            },
            "audio": {
                "name": "音訊打磨",
                "items": [
                    "UI 音效（按鈕點擊、頁面切換）",
                    "環境音效（風、水、腳步回音）",
                    "打擊音效層級（輕擊/重擊/爆擊）",
                    "音樂淡入淡出",
                    "語音音量一致性",
                    "3D 音效定位精準度",
                    "音效優先級管理（避免同時播放過多）"
                ]
            },
            "ui_ux": {
                "name": "UI/UX 打磨",
                "items": [
                    "手把/鍵鼠 UI 自動切換",
                    "載入畫面提示/小遊戲",
                    "教學提示時機與清晰度",
                    "HUD 資訊架構（不遮擋重要畫面）",
                    "按鈕點擊區域（最少 48x48px）",
                    "文字排版與閱讀流暢度",
                    "設定頁面完整度",
                    "在地化字型支援"
                ]
            },
            "gamefeel": {
                "name": "遊戲感打磨",
                "items": [
                    "角色移動慣性與加減速",
                    "跳躍曲線（上升/頂點/下降）",
                    "打擊命中停幀（Hit Stop）",
                    "擊退/擊飛力道感",
                    "鏡頭晃動與跟隨平滑度",
                    "死亡/重生流程流暢度",
                    "物件互動回饋（推、拉、拾取）",
                    "自動瞄準輔助（如適用）"
                ]
            },
            "performance": {
                "name": "效能打磨",
                "items": [
                    "載入時間（< 15 秒目標）",
                    "記憶體使用（< 平台上限 80%）",
                    "Shader 編譯預熱",
                    "Asset Bundle 最佳化",
                    "網路延遲補償（如適用）",
                    "背景載入（不卡頓）",
                    "儲存檔案大小控管"
                ]
            },
            "localization": {
                "name": "在地化",
                "items": [
                    "文字框自動擴展（日文/德文較長）",
                    "字型 fallback（中日韓）",
                    "數字/日期/貨幣格式",
                    "語音語言切換",
                    "文化敏感度審查"
                ]
            },
            "accessibility": {
                "name": "輔助功能",
                "items": [
                    "色盲模式",
                    "字幕大小/背景調整",
                    "按鍵全自訂",
                    "難度細調選項",
                    "遊戲速度調整"
                ]
            }
        }

        self.PRIORITIES = {
            "P0": "必須修復（阻礙發行）",
            "P1": "高度建議（嚴重影響體驗）",
            "P2": "建議（明顯改善體驗）",
            "P3": "錦上添花（時間允許再做）"
        }

    def register_routes(self, app):
        app.add_url_rule('/api/polish-pass/init', 'polish_init',
                         self.init_session, methods=['POST'])
        app.add_url_rule('/api/polish-pass/respond', 'polish_respond',
                         self.respond, methods=['POST'])
        app.add_url_rule('/api/polish-pass/state/<sid>', 'polish_state',
                         self.get_state, methods=['GET'])
        app.add_url_rule('/api/polish-pass/categories', 'polish_categories',
                         self.get_categories, methods=['GET'])
        app.add_url_rule('/api/polish-pass/save/<sid>', 'polish_save',
                         self.save_report, methods=['POST'])

    def init_session(self):
        data = request.get_json(silent=True) or {}
        sid = str(uuid.uuid4())[:8]

        self.sessions[sid] = {
            "phase": 1,
            "created_at": datetime.now().isoformat(),
            "game_name": data.get("game_name", "未命名"),
            "categories_selected": data.get("categories", list(self.CATEGORIES.keys())),
            "items": {},  # {item_name: {priority, status, notes}}
            "fields": {}
        }

        return jsonify({
            "session_id": sid,
            "phase": 1,
            "phase_name": self.PHASES[1],
            "message": f"開始打磨通行：{self.sessions[sid]['game_name']}",
            "prompt": "選擇要打磨的類別（可多選，預設全部 7 類）",
            "categories": {k: v["name"] for k, v in self.CATEGORIES.items()},
            "total_items": sum(len(v["items"]) for v in self.CATEGORIES.values()),
            "priorities": self.PRIORITIES
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
        phase_progress = {
            1: ("categories_selected", 2),
            2: ("visual_done", 3),
            3: ("audio_done", 4),
            4: ("ui_ux_done", 5),
            5: ("gamefeel_done", 6),
            6: ("performance_done", 7),
        }

        if current in phase_progress:
            trigger, next_phase = phase_progress[current]
            if s["fields"].get(trigger):
                s["phase"] = next_phase

        return jsonify(self._phase_response(s))

    def get_state(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        completed = sum(1 for v in s["items"].values() if v.get("status") == "done")
        total = len(s["items"])
        return jsonify({
            "session_id": sid,
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "progress": f"{completed}/{total} ({int(completed/max(total,1)*100)}%)",
            "items": s["items"],
            "fields": s["fields"]
        })

    def get_categories(self):
        return jsonify({
            "categories": {
                k: {"name": v["name"], "items": v["items"]}
                for k, v in self.CATEGORIES.items()
            },
            "priorities": self.PRIORITIES
        })

    def save_report(self, sid):
        if sid not in self.sessions:
            return jsonify({"error": "Session not found"}), 404
        s = self.sessions[sid]
        report = self._build_report(s)
        import os
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"polish_pass_{sid}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return jsonify({"status": "saved", "path": out_path, "report": report})

    def _phase_response(self, s):
        cat_keys = list(self.CATEGORIES.keys())
        phase_prompts = {
            1: ("範圍定義", f"選擇打磨類別：{', '.join(cat_keys)}。完成後輸入 'categories_selected: true'"),
            2: ("視覺打磨", f"審查 {len(self.CATEGORIES['visual']['items'])} 項視覺項目。完成後輸入 'visual_done: true'"),
            3: ("音訊打磨", f"審查 {len(self.CATEGORIES['audio']['items'])} 項音訊項目。完成後輸入 'audio_done: true'"),
            4: ("UI/UX 打磨", f"審查 {len(self.CATEGORIES['ui_ux']['items'])} 項 UI/UX 項目。完成後輸入 'ui_ux_done: true'"),
            5: ("遊戲感打磨", f"審查 {len(self.CATEGORIES['gamefeel']['items'])} 項遊戲感項目。完成後輸入 'gamefeel_done: true'"),
            6: ("效能打磨", f"審查效能/在地化/輔助功能。完成後輸入 'performance_done: true'"),
            7: ("報告生成", "所有類別完成。輸入 'save' 匯出打磨清單報告。")
        }
        msg, prompt = phase_prompts.get(s["phase"], ("", ""))
        resp = {
            "phase": s["phase"],
            "phase_name": self.PHASES.get(s["phase"], "Unknown"),
            "message": msg,
            "prompt": prompt,
            "priorities": self.PRIORITIES
        }
        # 附上當前類別的清單
        cat_map = {2: "visual", 3: "audio", 4: "ui_ux", 5: "gamefeel", 6: "performance"}
        if s["phase"] in cat_map:
            cat = cat_map[s["phase"]]
            resp["checklist"] = self.CATEGORIES[cat]["items"]
        return resp

    def _phase_description(self, i):
        descs = {
            1: "選擇要打磨的類別範圍",
            2: "視覺效果打磨（粒子/震動/光影/轉場/UI動畫）",
            3: "音訊打磨（UI音效/環境音/打擊音/音樂/3D定位）",
            4: "UI/UX 改善（手把支援/載入畫面/教學/HUD/排版）",
            5: "遊戲感打磨（移動/跳躍/HitStop/鏡頭/互動回饋）",
            6: "效能與其他（載入/記憶體/在地化/輔助功能）",
            7: "匯出完整打磨清單報告"
        }
        return descs.get(i, "")

    def _build_report(self, s):
        lines = [
            "# 打磨通行報告",
            f"遊戲：{s['game_name']}",
            f"日期：{s['created_at'][:10]}",
            "",
            "## 優先級摘要"
        ]

        # 按優先級分組
        by_priority = {"P0": [], "P1": [], "P2": [], "P3": []}
        for item_name, info in s["items"].items():
            p = info.get("priority", "P3")
            by_priority[p].append(item_name)

        for p in ["P0", "P1", "P2", "P3"]:
            lines.append(f"\n### {p} — {self.PRIORITIES[p]}（{len(by_priority[p])} 項）")
            for item in by_priority[p]:
                info = s["items"].get(item, {})
                status_icon = "✅" if info.get("status") == "done" else "⬜"
                lines.append(f"- {status_icon} {item}")
                if info.get("notes"):
                    lines.append(f"  - 備註：{info['notes']}")

        lines.append("\n## 統計")
        total = len(s["items"])
        done = sum(1 for v in s["items"].values() if v.get("status") == "done")
        lines.append(f"- 完成：{done}/{total} ({int(done/max(total,1)*100)}%)")
        lines.append(f"- P0 待辦：{len(by_priority['P0'])}")
        lines.append(f"- P1 待辦：{len(by_priority['P1'])}")

        return "\n".join(lines)
