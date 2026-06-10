"""
Alice Game Studio — /start 技能
移植自 CCGS start + project-stage-detect
引導式專案初始化：偵測階段 → 四選項 → 路徑選擇 → 審查模式
"""

from pathlib import Path
from datetime import datetime

# ═══════════════ Phase 1: 專案狀態偵測 ═══════════════

def detect_project_state(project_path=None):
    """掃描專案目錄，判定當前階段 (移植自 CCGS project-stage-detect)"""
    result = {
        "phase": 0,
        "phase_name": "No Project",
        "engine": None,
        "godot_version": None,
        "has_source_code": False,
        "has_design_docs": False,
        "has_architecture": False,
        "has_prototypes": False,
        "has_gdd": False,
        "has_adr": False,
        "indicators": [],
        "recommended_next": "start"
    }

    if not project_path or not Path(project_path).exists():
        result["indicators"].append("❌ 未找到專案目錄")
        return result

    pp = Path(project_path)

    # ── 引擎偵測 ──
    if (pp / "project.godot").exists():
        result["engine"] = "Godot"
        result["indicators"].append("✅ 偵測到 Godot 專案")
        try:
            content = (pp / "project.godot").read_text(encoding='utf-8')
            for line in content.split('\n'):
                if 'config/version' in line or 'config/features' in line:
                    pass
        except:
            pass

    if list(pp.glob("*.unity")):
        result["engine"] = "Unity"
        result["indicators"].append("✅ 偵測到 Unity 專案")

    if list(pp.glob("*.uproject")):
        result["engine"] = "Unreal"
        result["indicators"].append("✅ 偵測到 Unreal 專案")

    if not result["engine"]:
        result["indicators"].append("⚠️ 未偵測到遊戲引擎")

    # ── 源碼檢查 ──
    src_dirs = ['src', 'scripts', 'Source', 'source', 'scenes']
    for d in src_dirs:
        if (pp / d).exists() and any((pp / d).iterdir()):
            result["has_source_code"] = True
            result["indicators"].append(f"✅ 源碼目錄: {d}/")
            break

    # ── 設計文件檢查 ──
    design_dirs = ['design', 'docs', 'documentation', 'GDD']
    gdd_files = ['game-concept.md', 'GDD.md', 'design-doc.md', 'game-design-document.md']
    for d in design_dirs:
        if (pp / d).exists():
            result["has_design_docs"] = True
            result["indicators"].append(f"✅ 設計目錄: {d}/")
            break
    for g in gdd_files:
        if (pp / g).exists() or list(pp.glob(f"**/{g}")):
            result["has_gdd"] = True
            result["indicators"].append(f"✅ GDD: {g}")
            break

    # ── 架構文件檢查 ──
    arch_indicators = ['ADR', 'architecture', 'ARCHITECTURE.md', 'adr/']
    for ind in arch_indicators:
        if (pp / ind).exists():
            result["has_architecture"] = True
            result["indicators"].append(f"✅ 架構目錄: {ind}/")
            break
    if list(pp.glob("**/ADR*.md")) or list(pp.glob("**/adr/*.md")):
        result["has_adr"] = True
        result["has_architecture"] = True
        result["indicators"].append("✅ ADR 文件")

    # ── 原型檢查 ──
    proto_dirs = ['prototypes', 'Prototype', 'prototype', 'prototyping']
    for d in proto_dirs:
        if (pp / d).exists():
            result["has_prototypes"] = True
            result["indicators"].append(f"✅ 原型目錄: {d}/")
            break

    # ── 階段判定 ──
    if not result["engine"] and not result["has_source_code"] and not result["has_design_docs"]:
        result["phase"] = 0
        result["phase_name"] = "No Project / Early Concept"
        result["recommended_next"] = "onboarding"
    elif result["engine"] and not result["has_design_docs"] and not result["has_gdd"]:
        result["phase"] = 1
        result["phase_name"] = "Concept"
        result["recommended_next"] = "brainstorm"
    elif result["has_gdd"] and not result["has_architecture"]:
        result["phase"] = 2
        result["phase_name"] = "Systems Design"
        result["recommended_next"] = "map-systems"
    elif result["has_architecture"] and not result["has_prototypes"]:
        result["phase"] = 3
        result["phase_name"] = "Technical Setup"
        result["recommended_next"] = "create-architecture"
    elif result["has_prototypes"] and not result["has_source_code"]:
        result["phase"] = 4
        result["phase_name"] = "Pre-Production"
        result["recommended_next"] = "create-epics"
    elif result["has_source_code"]:
        result["phase"] = 5
        result["phase_name"] = "Production"
        result["recommended_next"] = "dev-story"

    return result


# ═══════════════ Phase 2: Onboarding 問題 ═══════════════

ONBOARDING_QUESTION = {
    "id": "onboarding_001",
    "text": "歡迎來到 Alice Game Studio！請選擇你的起點：",
    "note": "（移植自 CCGS /start 的 onboarding 流程，改用 API + Inline Keyboard）",
    "options": [
        {
            "id": "A",
            "label": "🅰️ 我完全沒有頭緒",
            "desc": "只是想探索遊戲開發的可能性，需要完整的引導。",
            "icon": "🌱",
            "next_path": "A",
            "recommended_skills": ["/brainstorm", "/setup-engine"]
        },
        {
            "id": "B",
            "label": "🅱️ 我有模糊的想法",
            "desc": "知道想做什麼類型的遊戲，但還沒具體規劃。",
            "icon": "💭",
            "next_path": "B",
            "recommended_skills": ["/brainstorm"]
        },
        {
            "id": "C",
            "label": "©️ 我有明確的遊戲概念",
            "desc": "已經有清楚的遊戲設計想法，準備開始系統化設計。",
            "icon": "📋",
            "next_path": "C",
            "recommended_skills": ["/map-systems", "/design-system"]
        },
        {
            "id": "D",
            "label": "🅳️ 我已有現成專案",
            "desc": "已經有一個遊戲專案，需要整合到工作室流程。",
            "icon": "📂",
            "next_path": "D",
            "recommended_skills": ["/project-stage-detect"]
        }
    ]
}


# ═══════════════ Phase 3: 四條路徑 ═══════════════

def get_path_A():
    """Path A: 完全沒有頭緒 → 完整 7 Phase 引導"""
    return {
        "id": "A",
        "name": "🌱 完整引導路徑",
        "description": "從零開始，逐步引導你完成完整的 7 階段遊戲開發流程。每個階段結束後會進行驗收。",
        "total_phases": 7,
        "estimated_hours": "40-120h (視專案規模)",
        "steps": [
            {"phase": 1, "phase_name": "Concept", "skill": "/brainstorm",
             "desc": "創意發想：探索遊戲類型、核心機制、目標玩家、情感錨點"},
            {"phase": 1, "phase_name": "Concept", "skill": "/setup-engine",
             "desc": "設定 Godot 引擎版本、專案結構、命名規範"},
            {"phase": 1, "phase_name": "Concept", "skill": "/gate-check",
             "desc": "Concept 階段驗收：核心循環、玩家類型、可行性評估"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/map-systems",
             "desc": "系統拆解：將遊戲概念分解為獨立系統，建立依賴圖"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/design-system",
             "desc": "GDD 寫作：逐一撰寫各系統的完整設計文件（8 必要段落）"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/design-review",
             "desc": "設計審查：驗證 GDD 完整性、跨系統一致性"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/create-architecture",
             "desc": "技術架構設計：主架構文件 + 需求追溯矩陣"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/architecture-decision",
             "desc": "ADR 撰寫：記錄每個關鍵技術決策的理由與取捨"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/art-bible",
             "desc": "美術聖經：定義視覺風格、色盤、UI 風格、VFX 方向"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/asset-spec",
             "desc": "資產規格：列出所有需要的視覺資產 + AI 生成提示詞"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/ux-design",
             "desc": "UX 設計：主選單、HUD、暫停選單等核心 UI 流程"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-epics",
             "desc": "Epic 拆分：從設計文件拆解為 Foundation/Core/Extension 三層 Epic"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-stories",
             "desc": "Story 撰寫：將 Epic 拆解為可獨立實現的開發 Story"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/vertical-slice",
             "desc": "垂直切片：建立最小可玩原型，驗證核心循環"},
            {"phase": 5, "phase_name": "Production", "skill": "/dev-story",
             "desc": "開發實現：逐個 Story 實現，每 Story 完成後審查"},
            {"phase": 5, "phase_name": "Production", "skill": "/code-review",
             "desc": "程式碼審查：架構級程式碼品質驗證"},
            {"phase": 5, "phase_name": "Production", "skill": "/sprint-status",
             "desc": "Sprint 管理：追蹤進度、識別阻礙"},
            {"phase": 6, "phase_name": "Polish", "skill": "/perf-profile",
             "desc": "效能分析：Godot Profiler 深度分析 CPU/GPU/記憶體"},
            {"phase": 6, "phase_name": "Polish", "skill": "/balance-check",
             "desc": "遊戲平衡：數據驅動的平衡調整"},
            {"phase": 6, "phase_name": "Polish", "skill": "/playtest-report",
             "desc": "試玩報告：結構化回饋收集與分析（最少 3 次）"},
            {"phase": 7, "phase_name": "Release", "skill": "/release-checklist",
             "desc": "發布清單：跨部門發布前最終驗證"},
            {"phase": 7, "phase_name": "Release", "skill": "/launch-checklist",
             "desc": "上線準備：Store 頁面、定價、行銷素材"},
            {"phase": 7, "phase_name": "Release", "skill": "/patch-notes",
             "desc": "更新說明：玩家面向的 Patch Notes 生成"},
        ]
    }


def get_path_B():
    """Path B: 模糊想法 → 從 brainstorming 聚焦"""
    return {
        "id": "B",
        "name": "💭 創意聚焦路徑",
        "description": "你已經有想法了，讓我們先聚焦創意，再進入完整開發流程。",
        "total_phases": 7,
        "estimated_hours": "30-100h (視專案規模)",
        "steps": [
            {"phase": 1, "phase_name": "Concept", "skill": "/brainstorm",
             "desc": "聚焦創意：把你的想法轉化為完整遊戲概念文件"},
            {"phase": 1, "phase_name": "Concept", "skill": "/setup-engine",
             "desc": "設定 Godot 引擎與專案結構"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/map-systems",
             "desc": "系統拆解"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/design-system",
             "desc": "GDD 寫作"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/create-architecture",
             "desc": "技術架構設計"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/architecture-decision",
             "desc": "ADR 撰寫"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-epics",
             "desc": "Epic 拆分"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-stories",
             "desc": "Story 撰寫"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/vertical-slice",
             "desc": "垂直切片"},
            {"phase": 5, "phase_name": "Production", "skill": "/dev-story",
             "desc": "開發實現"},
            {"phase": 5, "phase_name": "Production", "skill": "/sprint-status",
             "desc": "Sprint 管理"},
            {"phase": 6, "phase_name": "Polish", "skill": "/perf-profile",
             "desc": "效能優化"},
            {"phase": 6, "phase_name": "Polish", "skill": "/playtest-report",
             "desc": "試玩報告"},
            {"phase": 7, "phase_name": "Release", "skill": "/release-checklist",
             "desc": "發布檢查"},
            {"phase": 7, "phase_name": "Release", "skill": "/patch-notes",
             "desc": "更新說明"},
        ]
    }


def get_path_C():
    """Path C: 明確概念 → 跳過 brainstorming，直接系統化設計"""
    return {
        "id": "C",
        "name": "📋 系統化設計路徑",
        "description": "概念已清晰，跳過 brainstorming，直接進入系統設計。",
        "total_phases": 7,
        "estimated_hours": "25-80h (視專案規模)",
        "steps": [
            {"phase": 1, "phase_name": "Concept", "skill": "/setup-engine",
             "desc": "設定 Godot 引擎（快速確認）"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/map-systems",
             "desc": "系統拆解：將你的概念分解為獨立系統"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/design-system",
             "desc": "GDD 寫作：為每個系統撰寫完整設計文件"},
            {"phase": 2, "phase_name": "Systems Design", "skill": "/design-review",
             "desc": "設計審查：確保設計完整性與一致性"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/create-architecture",
             "desc": "技術架構設計"},
            {"phase": 3, "phase_name": "Technical Setup", "skill": "/architecture-decision",
             "desc": "關鍵 ADR 撰寫"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-epics",
             "desc": "Epic 拆分"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/create-stories",
             "desc": "Story 撰寫"},
            {"phase": 4, "phase_name": "Pre-Production", "skill": "/vertical-slice",
             "desc": "垂直切片"},
            {"phase": 5, "phase_name": "Production", "skill": "/dev-story",
             "desc": "開發實現"},
            {"phase": 5, "phase_name": "Production", "skill": "/sprint-status",
             "desc": "Sprint 管理"},
            {"phase": 6, "phase_name": "Polish", "skill": "/perf-profile",
             "desc": "效能優化"},
            {"phase": 6, "phase_name": "Polish", "skill": "/playtest-report",
             "desc": "試玩報告"},
            {"phase": 7, "phase_name": "Release", "skill": "/release-checklist",
             "desc": "發布檢查"},
            {"phase": 7, "phase_name": "Release", "skill": "/patch-notes",
             "desc": "更新說明"},
        ]
    }


def get_path_D():
    """Path D: 現成專案 → 偵測階段後整合"""
    return {
        "id": "D",
        "name": "📂 專案整合路徑",
        "description": "你已經有專案了，讓我們偵測目前階段並無縫整合到工作室流程。",
        "total_phases": "動態",
        "estimated_hours": "取決於專案當前階段",
        "steps": [
            {"phase": 0, "phase_name": "Detection", "skill": "/project-stage-detect",
             "desc": "掃描專案目錄，偵測引擎、設計文件、源碼、架構文件"},
            {"phase": 0, "phase_name": "Detection", "skill": "-",
             "desc": "根據偵測結果自動判定當前階段（Phase 0-5）"},
            {"phase": 0, "phase_name": "Detection", "skill": "-",
             "desc": "比對 Phase Gate 標準，產出差距報告"},
            {"phase": "動態", "phase_name": "動態", "skill": "-",
             "desc": "根據差距報告，自動推薦下一步（可能是補文件、進入下一階段、或直接開發）"},
        ]
    }


# ═══════════════ Phase 4: 審查模式 ═══════════════

REVIEW_MODE_QUESTION = {
    "id": "review_mode_001",
    "text": "選擇審查模式 — 決定 AI 在每個階段的參與程度：",
    "note": "（移植自 CCGS brainstorm 的 review mode，三選一）",
    "options": [
        {
            "id": "full",
            "label": "🔍 Full Review",
            "desc": "完整審查。每個階段結束後進行深度審查。適合新手或高品質要求的專案。",
            "icon": "🔍",
            "characteristics": [
                "每個 Phase 結束 → 完整審查",
                "Gate check 強制 PASS 才能前進",
                "橫向專家諮詢（如 UI 專家審查 UX 設計）",
                "產出詳細審查報告"
            ]
        },
        {
            "id": "lean",
            "label": "⚡ Lean Review",
            "desc": "精簡審查。只審查關鍵決策點，加快開發速度。適合有經驗的開發者。",
            "icon": "⚡",
            "characteristics": [
                "只審查 Phase Gate 關鍵門檻",
                "Gate check 可 CONCERNS 通過（標記追蹤）",
                "跳過非關鍵專家諮詢",
                "產出簡要審查備忘錄"
            ]
        },
        {
            "id": "solo",
            "label": "🎯 Solo Mode",
            "desc": "獨立模式。AI 輔助但不主導，只在卡住時請求協助。最大自主性。",
            "icon": "🎯",
            "characteristics": [
                "無強制審查，開發者自主決定何時請求 review",
                "Gate check 僅供參考",
                "所有技能仍可用（/brainstorm, /dev-story 等）",
                "適合快速原型或個人專案"
            ]
        }
    ]
}


# ═══════════════ 狀態機 ═══════════════

class StartSession:
    """/start 流程的會話狀態機"""

    def __init__(self):
        self.state = "idle"           # idle → onboarding → path_selected → review_mode → complete
        self.onboarding_answer = None  # A/B/C/D
        self.selected_path = None      # Path dict
        self.review_mode = None        # full/lean/solo
        self.project_state = None      # detect_project_state() 結果
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "state": self.state,
            "onboarding_answer": self.onboarding_answer,
            "selected_path_id": self.selected_path["id"] if self.selected_path else None,
            "selected_path_name": self.selected_path["name"] if self.selected_path else None,
            "review_mode": self.review_mode,
            "project_state": self.project_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def reset(self):
        self.state = "idle"
        self.onboarding_answer = None
        self.selected_path = None
        self.review_mode = None
        self.project_state = None
        self.updated_at = datetime.now().isoformat()


# ── 記憶體會話儲存 (未來可遷移至 DuckDB) ──

_active_sessions: dict[str, StartSession] = {}

def get_session(session_id: str = "default") -> StartSession:
    if session_id not in _active_sessions:
        _active_sessions[session_id] = StartSession()
    return _active_sessions[session_id]

def reset_session(session_id: str = "default"):
    if session_id in _active_sessions:
        _active_sessions[session_id].reset()
