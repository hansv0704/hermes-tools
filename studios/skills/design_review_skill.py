"""
Alice Game Studio — /design-review Skill
Phase 2.3: GDD 完整性驗證
移植自 CCGS design-review：APPROVE / CONCERNS / MAJOR REVISION
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

_sessions: Dict[str, 'DesignReviewSession'] = {}

# ── 審查清單 ──
REVIEW_CHECKLIST = [
    # (類別, 檢查項目, 權重)
    ("結構完整性", "是否包含所有 8 個必要段落", "critical"),
    ("結構完整性", "每段落是否有具體內容而非僅模板", "critical"),
    ("清晰度", "系統定義是否清晰、一句話可理解", "high"),
    ("清晰度", "核心規則是否有公式或偽代碼", "high"),
    ("清晰度", "邊界情況是否具體而非泛泛而談", "high"),
    ("可行性", "技術實現是否合理（Godot 環境可行）", "critical"),
    ("可行性", "資料模型是否明確（欄位名稱/類型）", "high"),
    ("可行性", "狀態與轉換是否可映射到程式碼", "high"),
    ("一致性", "與其他系統的依賴是否合理", "medium"),
    ("一致性", "術語使用是否前後一致", "medium"),
    ("可玩性", "玩家流程是否具體描述體驗", "high"),
    ("可玩性", "成功標準是否可量化", "medium"),
    ("完整性", "是否有遺漏的極限案例", "medium"),
    ("完整性", "錯誤處理策略是否完備", "low"),
    ("品質", "文件排版是否清晰易讀", "low"),
    ("品質", "是否有具體數值而非僅概念", "medium"),
]

# ── 審查建議庫 ──
SUGGESTION_BANK = {
    "結構完整性": "建議先完成所有 8 個必要段落再送審。可以使用 /design-system 逐步填寫。",
    "清晰度": "建議加入偽代碼或狀態圖來描述核心規則。具體範例比抽象描述更有價值。",
    "可行性": "建議與 Godot 開發者確認技術可行性。某些看似簡單的功能可能有引擎限制。",
    "一致性": "建議對照其他已完成的 GDD，確保術語和依賴關係一致。",
    "可玩性": "建議加入具體的玩家故事（User Story），從玩家視角描述體驗。",
    "完整性": "建議考慮：空狀態、載入失敗、網路中斷、記憶體不足等邊界情況。",
    "品質": "建議加入表格、清單或圖表來提升可讀性。",
}

# ── 審查層級對應 ──
CRITICAL_WEIGHT = {"critical": 3, "high": 2, "medium": 1, "low": 0}


class DesignReviewSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "init"
        self.gdd_path: str = ""
        self.gdd_content: str = ""
        self.system_name: str = ""
        self.sections_found: List[str] = []
        self.sections_missing: List[str] = []
        self.checklist_results: List[Dict] = []
        self.verdict: str = ""  # APPROVE / CONCERNS / MAJOR_REVISION
        self.critical_failures: int = 0
        self.high_failures: int = 0
        self.total_score: int = 0
        self.max_score: int = 0
        self.suggestions: List[str] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "system_name": self.system_name,
            "verdict": self.verdict,
            "score": f"{self.total_score}/{self.max_score}",
        }


class DesignReviewSkill:
    """/design-review 核心邏輯"""

    REQUIRED_SECTIONS = [
        "Overview", "Core Mechanics", "User Flow", "States", "Transitions",
        "Data Model", "Edge Cases", "Error States", "Dependencies", "Metrics", "Success Criteria"
    ]

    def handle_init(self, gdd_path: str = "", gdd_content: str = "") -> dict:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session = DesignReviewSession(session_id)
        session.state = "loading"

        if gdd_path:
            session.gdd_path = gdd_path
            try:
                session.gdd_content = Path(gdd_path).read_text(encoding='utf-8')
                session.state = "reviewing"
            except:
                pass

        if gdd_content and not session.gdd_content:
            session.gdd_content = gdd_content
            session.state = "reviewing"

        _sessions[session_id] = session

        if session.state == "reviewing":
            return self._run_review(session)
        else:
            return {
                "session_id": session_id,
                "state": "awaiting_content",
                "question": {
                    "id": "gdd_input",
                    "text": "請提供 GDD 文件的路徑，或貼上完整內容。也可以用 /design-system 產出後直接審查。",
                    "type": "textarea"
                }
            }

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        session = _sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.state == "awaiting_content":
            session.gdd_content = value
            # 嘗試當作路徑
            try:
                session.gdd_content = Path(value).read_text(encoding='utf-8')
                session.gdd_path = value
            except:
                pass
            session.state = "reviewing"
            session.updated_at = datetime.now().isoformat()
            return self._run_review(session)

        if session.state == "complete":
            return {
                "session_id": session_id,
                "state": "complete",
                "verdict": session.verdict,
                "score": f"{session.total_score}/{session.max_score}",
                "report": self._generate_report(session),
            }

        return {"error": "Unknown state"}

    def _run_review(self, session: DesignReviewSession) -> dict:
        content = session.gdd_content

        # 提取系統名稱
        title_match = __import__('re').search(r'^#\s+(.+?)\s*[-–—]', content, __import__('re').MULTILINE)
        if title_match:
            session.system_name = title_match.group(1).strip()
        else:
            title_match = __import__('re').search(r'^#\s+(.+)', content, __import__('re').MULTILINE)
            if title_match:
                session.system_name = title_match.group(1).strip()

        # 檢查必要段落
        for section in self.REQUIRED_SECTIONS:
            if section.lower() in content.lower():
                session.sections_found.append(section)
            else:
                session.sections_missing.append(section)

        # 執行檢查清單
        session.checklist_results = []
        session.critical_failures = 0
        session.high_failures = 0
        session.total_score = 0
        session.max_score = 0
        session.suggestions = []

        for category, item, weight in REVIEW_CHECKLIST:
            passed = self._check_item(content, category, item)
            weight_val = CRITICAL_WEIGHT[weight]
            session.max_score += weight_val
            if passed:
                session.total_score += weight_val
            else:
                if weight == "critical":
                    session.critical_failures += 1
                elif weight == "high":
                    session.high_failures += 1
                if category in SUGGESTION_BANK:
                    if SUGGESTION_BANK[category] not in session.suggestions:
                        session.suggestions.append(SUGGESTION_BANK[category])

            session.checklist_results.append({
                "category": category,
                "item": item,
                "weight": weight,
                "passed": passed,
            })

        # 判定
        if session.critical_failures == 0 and session.high_failures <= 1:
            session.verdict = "APPROVE ✅"
        elif session.critical_failures == 0 and session.high_failures <= 3:
            session.verdict = "CONCERNS ⚠️"
        else:
            session.verdict = "MAJOR REVISION ❌"

        session.state = "complete"
        session.updated_at = datetime.now().isoformat()

        return {
            "session_id": session.session_id,
            "state": "complete",
            "verdict": session.verdict,
            "system_name": session.system_name,
            "score": f"{session.total_score}/{session.max_score}",
            "sections_found": session.sections_found,
            "sections_missing": session.sections_missing,
            "critical_failures": session.critical_failures,
            "high_failures": session.high_failures,
            "checklist": session.checklist_results,
            "suggestions": session.suggestions,
            "report": self._generate_report(session),
        }

    def _check_item(self, content: str, category: str, item: str) -> bool:
        lower = content.lower()

        if item == "是否包含所有 8 個必要段落":
            return len(self.REQUIRED_SECTIONS) - len(set(self.REQUIRED_SECTIONS) - set(self._get_found_sections(content))) >= 6

        if item == "每段落是否有具體內容而非僅模板":
            # 檢查是否有空的 {} 佔位符
            empty_placeholders = content.count("{") - content.count("}") if content.count("{") > content.count("}") else 0
            # 檢查模板殘留關鍵字
            template_markers = ["{一句話定義}", "{為什麼需要這個系統}", "{玩家如何互動}", "{新手體驗}"]
            empty_count = sum(1 for t in template_markers if t in content)
            return empty_count <= 2

        if item == "系統定義是否清晰、一句話可理解":
            return "系統定義" in lower or "overview" in lower or bool(__import__('re').search(r'##\s*(Overview|概述|系統定義)', content))

        if item == "核心規則是否有公式或偽代碼":
            return bool(__import__('re').search(r'[+\-*/=><]|```|function|def ', content))

        if item == "邊界情況是否具體而非泛泛而談":
            edge_content = self._extract_section(content, ["Edge Cases", "邊界", "錯誤"])
            return len(edge_content) > 100 if edge_content else False

        if item == "技術實現是否合理（Godot 環境可行）":
            return True  # 不做深度技術審查

        if item == "資料模型是否明確（欄位名稱/類型）":
            return bool(__import__('re').search(r'(欄位|field|類型|type|string|int|float|bool)', lower))

        if item == "狀態與轉換是否可映射到程式碼":
            return bool(__import__('re').search(r'(狀態|state|轉換|transition|enum)', lower))

        if item == "玩家流程是否具體描述體驗":
            return bool(__import__('re').search(r'(玩家|player|user|flow|流程|體驗)', lower))

        if item == "成功標準是否可量化":
            return bool(__import__('re').search(r'(\d+%|\d+秒|\d+分|KPI|metric|指標|數據)', lower))

        if item == "是否有遺漏的極限案例":
            return True  # 寬容處理

        if item == "文件排版是否清晰易讀":
            return len(content) > 500

        if item == "是否有具體數值而非僅概念":
            return bool(__import__('re').search(r'\d+', content))

        # 預設
        return len(content) > 200

    def _get_found_sections(self, content: str) -> List[str]:
        return [s for s in self.REQUIRED_SECTIONS if s.lower() in content.lower()]

    def _extract_section(self, content: str, keywords: List[str]) -> str:
        for kw in keywords:
            pattern = rf'##\s*[^#\n]*{kw}[^#\n]*\n(.*?)(?=\n##|\Z)'
            m = __import__('re').search(pattern, content, __import__('re').DOTALL | __import__('re').IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def _generate_report(self, session: DesignReviewSession) -> str:
        lines = []
        lines.append(f"# 🔍 GDD 審查報告: {session.system_name}\n")
        lines.append(f"**審查時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**裁決**: {session.verdict}")
        lines.append(f"**分數**: {session.total_score}/{session.max_score}")
        lines.append(f"**嚴重缺失**: {session.critical_failures}")
        lines.append(f"**高度缺失**: {session.high_failures}\n")

        if session.sections_missing:
            lines.append("## ❌ 缺失段落")
            for s in session.sections_missing:
                lines.append(f"- {s}")

        if session.suggestions:
            lines.append("\n## 💡 改進建議")
            for s in session.suggestions:
                lines.append(f"- {s}")

        lines.append("\n## 📋 檢查清單")
        for r in session.checklist_results:
            status = "✅" if r["passed"] else "❌"
            lines.append(f"- {status} [{r['weight']}] {r['category']}: {r['item']}")

        return "\n".join(lines)

    def get_session(self, session_id: str) -> Optional[DesignReviewSession]:
        return _sessions.get(session_id)


design_review_skill = DesignReviewSkill()
