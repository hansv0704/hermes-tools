"""
Alice Game Studio — /map-systems Skill
Phase 2.1: 系統拆解與依賴圖
移植自 CCGS map-systems：讀取 game-concept.md → 系統清單 → 分類 → 依賴圖 → 優先級
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# ── Session 管理 ──
_sessions: Dict[str, 'MapSystemsSession'] = {}

class MapSystemsSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "init"
        self.phase = 0
        self.total_phases = 5
        self.concept_path: str = ""
        self.concept_text: str = ""
        self.systems_raw: List[Dict] = []
        self.systems_classified: Dict[str, List[Dict]] = {"foundation": [], "core": [], "extension": []}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.priority_order: List[Dict] = []
        self.final_report: str = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "phase": self.phase,
            "total_phases": self.total_phases,
            "concept_path": self.concept_path,
            "systems_count": len(self.systems_raw),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Phase 定義 ──
MAP_PHASES = {
    1: {"name": "讀取概念文件", "icon": "📖", "desc": "載入 game-concept.md，提取所有系統線索"},
    2: {"name": "系統提取", "icon": "🔍", "desc": "從概念文件中提取所有遊戲系統"},
    3: {"name": "系統分類", "icon": "🏗️", "desc": "Foundation / Core / Extension 三層分類"},
    4: {"name": "依賴圖", "icon": "🔗", "desc": "建立系統間依賴關係與拓撲排序"},
    5: {"name": "優先級排序", "icon": "📊", "desc": "產出系統實現優先級與報告"},
}

# ── 系統分類定義 ──
SYSTEM_CATEGORIES = {
    "foundation": {
        "name": "Foundation (基礎層)",
        "icon": "🏗️",
        "desc": "所有其他系統依賴的基礎設施。必須最先實現。",
        "examples": "引擎核心、渲染管線、輸入系統、資源管理、存檔系統",
        "keywords": ["引擎", "渲染", "輸入", "資源", "存檔", "音頻", "物理", "網路底層", "場景", "攝影機", "UI框架"]
    },
    "core": {
        "name": "Core (核心層)",
        "icon": "⚙️",
        "desc": "遊戲核心機制。定義玩家體驗。",
        "examples": "戰鬥系統、移動系統、AI行為、技能系統、道具系統、對話系統",
        "keywords": ["戰鬥", "移動", "AI", "技能", "道具", "對話", "任務", "升級", "裝備", "經濟", "製作"]
    },
    "extension": {
        "name": "Extension (擴展層)",
        "icon": "🧩",
        "desc": "增強體驗的附加系統。可以在核心完成後實現。",
        "examples": "成就系統、排行榜、裝飾品、圖鑑、拍照模式、新遊戲+",
        "keywords": ["成就", "排行", "裝飾", "圖鑑", "拍照", "社交", "賽季", "活動", "DLC"]
    }
}

# ── 系統關鍵字匹配表 ──
SYSTEM_PATTERNS = [
    # (系統名稱, 關鍵字列表, 預設分類)
    ("移動系統", ["移動", "走路", "跑步", "跳躍", "飛行", "游泳", "攀爬", "閃避", "衝刺", "platform", "movement"], "core"),
    ("戰鬥系統", ["戰鬥", "攻擊", "防禦", "傷害", "HP", "血量", "combat", "fight", "battle"], "core"),
    ("AI 系統", ["AI", "敵人", "NPC", "行為樹", "尋路", "pathfinding", "behavior"], "core"),
    ("技能系統", ["技能", "法術", "天賦", "skill", "ability", "spell"], "core"),
    ("道具系統", ["道具", "物品", "背包", "inventory", "item", "倉庫"], "core"),
    ("裝備系統", ["裝備", "武器", "防具", "equipment", "gear", "武器欄"], "core"),
    ("任務系統", ["任務", "quest", "mission", "目標", "委託"], "core"),
    ("對話系統", ["對話", "dialogue", "對話樹", "選項", "分支"], "core"),
    ("升級系統", ["升級", "等級", "經驗", "level", "exp", "成長"], "core"),
    ("經濟系統", ["金錢", "貨幣", "商店", "購買", "economy", "currency", "shop"], "core"),
    ("製作系統", ["製作", "合成", "crafting", "配方", "recipe", "鍛造"], "core"),
    ("渲染系統", ["渲染", "render", "shader", "光影", "後處理", "post-process"], "foundation"),
    ("輸入系統", ["輸入", "input", "鍵盤", "滑鼠", "手把", "controller"], "foundation"),
    ("音頻系統", ["音效", "音樂", "audio", "sound", "BGM", "配音"], "foundation"),
    ("存檔系統", ["存檔", "save", "讀檔", "load", "自動保存", "checkpoint"], "foundation"),
    ("場景管理", ["場景", "scene", "關卡", "地圖切換", "level", "傳送"], "foundation"),
    ("UI 系統", ["UI", "介面", "HUD", "選單", "menu", "血條", "圖示"], "foundation"),
    ("資源管理", ["資源", "asset", "載入", "pool", "物件池", "preload"], "foundation"),
    ("物理系統", ["物理", "physics", "碰撞", "重力", "rigidbody", "collider"], "foundation"),
    ("網路系統", ["網路", "network", "multiplayer", "連線", "同步", "server"], "foundation"),
    ("成就系統", ["成就", "achievement", "獎盃", "trophy"], "extension"),
    ("排行榜", ["排行", "leaderboard", "排名", "分數"], "extension"),
    ("社交系統", ["好友", "公會", "聊天", "social", "friend", "guild"], "extension"),
    ("賽季系統", ["賽季", "season", "battle pass", "通行證"], "extension"),
    ("圖鑑系統", ["圖鑑", "收集", "collection", "百科", "bestiary"], "extension"),
    ("拍照模式", ["拍照", "photo", "截圖", "相機模式"], "extension"),
    ("裝飾系統", ["造型", "skin", "外觀", "cosmetic", "時裝"], "extension"),
    ("新手教學", ["教學", "tutorial", "引導", "新手", "提示"], "core"),
    ("天氣系統", ["天氣", "weather", "下雨", "晝夜", "季節"], "core"),
    ("地圖系統", ["地圖", "map", "小地圖", "minimap", "導航"], "core"),
    ("角色自訂", ["創角", "捏臉", "自訂", "character creation", "customization"], "core"),
]


def extract_systems_from_concept(concept_text: str) -> List[Dict]:
    """從 game-concept.md 中提取系統清單"""
    systems = []
    found_names = set()

    for sys_name, keywords, default_cat in SYSTEM_PATTERNS:
        matched = False
        matched_kw = []
        for kw in keywords:
            if kw.lower() in concept_text.lower():
                matched = True
                matched_kw.append(kw)
        if matched:
            systems.append({
                "name": sys_name,
                "category": default_cat,
                "matched_keywords": matched_kw,
                "confidence": min(len(matched_kw) * 25 + 25, 100),
            })
            found_names.add(sys_name)

    # 從文件結構中提取自訂系統（## 開頭的區段）
    custom_systems = re.findall(r'^##\s+(.+?系統)', concept_text, re.MULTILINE)
    for cs in custom_systems:
        if cs not in found_names:
            systems.append({
                "name": cs,
                "category": "core",
                "matched_keywords": ["自訂"],
                "confidence": 70,
            })

    return systems


def classify_systems(systems: List[Dict]) -> Dict[str, List[Dict]]:
    """分類系統為 Foundation / Core / Extension"""
    classified = {"foundation": [], "core": [], "extension": []}
    for s in systems:
        cat = s.get("category", "core")
        if cat in classified:
            classified[cat].append(s)
        else:
            classified["core"].append(s)
    return classified


def build_dependency_graph(systems: List[Dict]) -> Dict[str, List[str]]:
    """建立系統依賴圖"""
    # Foundation 系統彼此無依賴，Core 依賴 Foundation，Extension 依賴 Core
    foundation_names = [s["name"] for s in systems if s["category"] == "foundation"]
    core_names = [s["name"] for s in systems if s["category"] == "core"]
    extension_names = [s["name"] for s in systems if s["category"] == "extension"]

    graph = {}
    for s in systems:
        deps = []
        if s["category"] == "core":
            deps = foundation_names
        elif s["category"] == "extension":
            deps = foundation_names + core_names
        graph[s["name"]] = deps

    return graph


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """拓撲排序"""
    in_degree = {node: 0 for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[node] += 1

    queue = [node for node, deg in in_degree.items() if deg == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for other, deps in graph.items():
            if node in deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    return result


def generate_report(session: MapSystemsSession) -> str:
    """產生完整報告"""
    lines = []
    lines.append("# 🗺️ 系統拆解報告\n")
    lines.append(f"**產生時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**來源文件**: {session.concept_path}\n")
    lines.append(f"**系統總數**: {len(session.systems_raw)}\n")

    # Foundation
    fnd = session.systems_classified.get("foundation", [])
    lines.append(f"\n## 🏗️ Foundation 基礎層 ({len(fnd)} 系統)\n")
    for s in fnd:
        lines.append(f"- **{s['name']}** (信心: {s['confidence']}%) — 關鍵字: {', '.join(s['matched_keywords'])}")

    # Core
    core = session.systems_classified.get("core", [])
    lines.append(f"\n## ⚙️ Core 核心層 ({len(core)} 系統)\n")
    for s in core:
        lines.append(f"- **{s['name']}** (信心: {s['confidence']}%) — 關鍵字: {', '.join(s['matched_keywords'])}")

    # Extension
    ext = session.systems_classified.get("extension", [])
    lines.append(f"\n## 🧩 Extension 擴展層 ({len(ext)} 系統)\n")
    for s in ext:
        lines.append(f"- **{s['name']}** (信心: {s['confidence']}%) — 關鍵字: {', '.join(s['matched_keywords'])}")

    # 依賴圖
    lines.append(f"\n## 🔗 依賴關係圖\n")
    sorted_order = session.priority_order if session.priority_order else topological_sort(session.dependency_graph)
    lines.append("```")
    lines.append("Foundation → Core → Extension")
    lines.append("")
    for i, name in enumerate(sorted_order):
        deps = session.dependency_graph.get(name, [])
        dep_str = f" ← 依賴: {', '.join(deps)}" if deps else ""
        lines.append(f"{i+1}. {name}{dep_str}")
    lines.append("```")

    # 實現優先級
    lines.append(f"\n## 📊 實現優先級\n")
    lines.append("| 優先級 | 系統 | 分類 | 依賴數 |")
    lines.append("|:--|:--|:--|:--|")
    for i, name in enumerate(sorted_order):
        deps = session.dependency_graph.get(name, [])
        cat = "🏗️" if name in [s['name'] for s in fnd] else ("⚙️" if name in [s['name'] for s in core] else "🧩")
        lines.append(f"| P{i+1} | {name} | {cat} | {len(deps)} |")

    return "\n".join(lines)


# ── Skill 主體 ──
class MapSystemsSkill:
    """/map-systems 核心邏輯"""

    def handle_init(self, concept_path: str = "", concept_text: str = "") -> dict:
        """初始化流程"""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session = MapSystemsSession(session_id)
        session.state = "phase1_reading"
        session.phase = 1

        if concept_path:
            session.concept_path = concept_path
            try:
                session.concept_text = Path(concept_path).read_text(encoding='utf-8')
            except:
                pass

        if concept_text and not session.concept_text:
            session.concept_text = concept_text

        _sessions[session_id] = session

        has_text = bool(session.concept_text)
        text_preview = session.concept_text[:500] + "..." if len(session.concept_text) > 500 else session.concept_text

        return {
            "session_id": session_id,
            "phase": 1,
            "phase_name": "讀取概念文件",
            "has_concept": has_text,
            "concept_path": session.concept_path,
            "text_preview": text_preview if has_text else "",
            "next_action": "upload_or_use_brainstorm" if not has_text else "proceed_to_extraction",
            "question": {
                "id": "concept_input",
                "text": "請提供 game-concept.md 的路徑，或貼上概念文件內容。也可以使用 /brainstorm 產出的文件。" if not has_text else "已讀取概念文件。是否開始提取系統？(輸入 yes 繼續)",
                "options": [
                    {"value": "yes", "label": "✅ 開始提取"},
                    {"value": "auto", "label": "🤖 自動分析（使用內建關鍵字匹配）"},
                    {"value": "paste", "label": "📋 我要貼上內容"},
                ] if has_text else None
            }
        }

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        """處理回應"""
        session = _sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        # Phase 1: 讀取概念
        if session.phase == 1:
            if field == "concept_input":
                if value == "yes" or value == "auto":
                    # 自動提取
                    if not session.concept_text:
                        return {"error": "無概念文件內容。請先提供。", "session_id": session_id}
                    session.systems_raw = extract_systems_from_concept(session.concept_text)
                    session.phase = 2
                    session.state = "phase2_extracted"
                    session.updated_at = datetime.now().isoformat()
                    return self._phase2_response(session)
                elif value == "paste":
                    return {
                        "session_id": session_id,
                        "phase": 1,
                        "state": "awaiting_paste",
                        "question": {
                            "id": "paste_content",
                            "text": "請貼上 game-concept.md 的完整內容：",
                            "type": "textarea"
                        }
                    }
                else:
                    # 當作路徑
                    session.concept_path = value
                    try:
                        session.concept_text = Path(value).read_text(encoding='utf-8')
                        session.systems_raw = extract_systems_from_concept(session.concept_text)
                        session.phase = 2
                        session.state = "phase2_extracted"
                        session.updated_at = datetime.now().isoformat()
                        return self._phase2_response(session)
                    except:
                        return {"error": f"無法讀取檔案: {value}", "session_id": session_id}

            elif field == "paste_content":
                session.concept_text = value
                session.systems_raw = extract_systems_from_concept(value)
                session.phase = 2
                session.state = "phase2_extracted"
                session.updated_at = datetime.now().isoformat()
                return self._phase2_response(session)

        # Phase 2: 系統提取 - 確認清單
        elif session.phase == 2:
            if value == "yes":
                session.systems_classified = classify_systems(session.systems_raw)
                session.phase = 3
                session.state = "phase3_classified"
                session.updated_at = datetime.now().isoformat()
                return self._phase3_response(session)
            elif value.startswith("add:"):
                new_name = value[4:].strip()
                session.systems_raw.append({
                    "name": new_name,
                    "category": "core",
                    "matched_keywords": ["手動添加"],
                    "confidence": 100,
                })
                return self._phase2_response(session)
            elif value.startswith("remove:"):
                rm_name = value[7:].strip()
                session.systems_raw = [s for s in session.systems_raw if s["name"] != rm_name]
                return self._phase2_response(session)
            elif value == "no":
                return self._phase2_response(session)

        # Phase 3: 分類確認
        elif session.phase == 3:
            if value == "yes":
                session.dependency_graph = build_dependency_graph(session.systems_raw)
                sorted_order = topological_sort(session.dependency_graph)
                session.priority_order = [{"name": n, "deps": session.dependency_graph.get(n, [])} for n in sorted_order]
                session.phase = 4
                session.state = "phase4_graph"
                session.updated_at = datetime.now().isoformat()
                return self._phase4_response(session)
            elif value.startswith("reclass:"):
                parts = value[8:].strip().split(":")
                if len(parts) == 2:
                    sys_name, new_cat = parts[0].strip(), parts[1].strip()
                    for s in session.systems_raw:
                        if s["name"] == sys_name:
                            s["category"] = new_cat
                    session.systems_classified = classify_systems(session.systems_raw)
                return self._phase3_response(session)

        # Phase 4: 依賴圖確認
        elif session.phase == 4:
            if value == "yes":
                session.phase = 5
                session.state = "phase5_complete"
                session.final_report = generate_report(session)
                session.updated_at = datetime.now().isoformat()
                return self._phase5_response(session)
            elif value == "no":
                return self._phase4_response(session)

        # Phase 5: 完成
        elif session.phase == 5:
            if value == "save":
                return self.finalize(session)
            return self._phase5_response(session)

        return {"error": "Unknown state", "session_id": session_id}

    def _phase2_response(self, session: MapSystemsSession) -> dict:
        systems_list = [f"- {s['name']} [{s['category']}] (信心: {s['confidence']}%)" for s in session.systems_raw]
        return {
            "session_id": session.session_id,
            "phase": 2,
            "phase_name": "系統提取",
            "systems_count": len(session.systems_raw),
            "systems": session.systems_raw,
            "systems_display": "\n".join(systems_list),
            "question": {
                "id": "confirm_systems",
                "text": f"已提取 {len(session.systems_raw)} 個系統。是否繼續分類？\n輸入 'add:系統名稱' 添加 / 'remove:系統名稱' 移除 / 'yes' 繼續",
                "options": [
                    {"value": "yes", "label": "✅ 確認並繼續"},
                    {"value": "no", "label": "🔍 讓我再確認一下"},
                ]
            }
        }

    def _phase3_response(self, session: MapSystemsSession) -> dict:
        fnd = session.systems_classified.get("foundation", [])
        core = session.systems_classified.get("core", [])
        ext = session.systems_classified.get("extension", [])

        display = []
        display.append(f"🏗️ Foundation ({len(fnd)}): " + ", ".join([s['name'] for s in fnd]))
        display.append(f"⚙️ Core ({len(core)}): " + ", ".join([s['name'] for s in core]))
        display.append(f"🧩 Extension ({len(ext)}): " + ", ".join([s['name'] for s in ext]))

        return {
            "session_id": session.session_id,
            "phase": 3,
            "phase_name": "系統分類",
            "classified": {
                "foundation": fnd,
                "core": core,
                "extension": ext,
            },
            "classified_display": "\n".join(display),
            "question": {
                "id": "confirm_classify",
                "text": f"系統已分類。輸入 'reclass:系統名稱:foundation/core/extension' 調整，或輸入 'yes' 建立依賴圖",
                "options": [
                    {"value": "yes", "label": "✅ 確認並建立依賴圖"},
                ]
            }
        }

    def _phase4_response(self, session: MapSystemsSession) -> dict:
        lines = []
        sorted_order = [item["name"] for item in session.priority_order]
        for i, name in enumerate(sorted_order):
            deps = session.dependency_graph.get(name, [])
            dep_str = f" ← {', '.join(deps)}" if deps else ""
            cat = ""
            for s in session.systems_raw:
                if s["name"] == name:
                    cat_icons = {"foundation": "🏗️", "core": "⚙️", "extension": "🧩"}
                    cat = cat_icons.get(s["category"], "")
                    break
            lines.append(f"{i+1}. {cat} {name}{dep_str}")

        return {
            "session_id": session.session_id,
            "phase": 4,
            "phase_name": "依賴圖",
            "dependency_graph": session.dependency_graph,
            "priority_order": session.priority_order,
            "graph_display": "\n".join(lines),
            "question": {
                "id": "confirm_graph",
                "text": f"依賴圖已建立（{len(session.dependency_graph)} 個節點）。輸入 'yes' 完成並產出報告",
                "options": [
                    {"value": "yes", "label": "✅ 完成並產出報告"},
                ]
            }
        }

    def _phase5_response(self, session: MapSystemsSession) -> dict:
        return {
            "session_id": session.session_id,
            "phase": 5,
            "phase_name": "完成",
            "state": "complete",
            "report": session.final_report,
            "question": {
                "id": "save_or_done",
                "text": "分析完成！輸入 'save' 儲存報告為 map-systems-report.md",
                "options": [
                    {"value": "save", "label": "💾 儲存報告"},
                    {"value": "done", "label": "✅ 完成"},
                ]
            }
        }

    def get_session(self, session_id: str) -> Optional[MapSystemsSession]:
        return _sessions.get(session_id)

    def finalize(self, session: MapSystemsSession, output_dir: str = "") -> dict:
        """儲存最終報告"""
        if not session.final_report:
            session.final_report = generate_report(session)

        saved_path = None
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            report_path = out_path / "map-systems-report.md"
            report_path.write_text(session.final_report, encoding='utf-8')
            saved_path = str(report_path)

        return {
            "session_id": session.session_id,
            "state": "complete",
            "report": session.final_report,
            "saved_path": saved_path,
            "systems_count": len(session.systems_raw),
            "dependency_count": len(session.dependency_graph),
        }


# ── 全域實例 ──
map_systems_skill = MapSystemsSkill()
