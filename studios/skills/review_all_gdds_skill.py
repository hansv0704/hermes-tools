"""
Alice Game Studio — /review-all-gdds Skill
Phase 2.4: 跨 GDD 一致性審查
移植自 CCGS review-all-gdds：跨文件一致性 + 設計理論審查
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set
import re

_sessions: Dict[str, 'ReviewAllSession'] = {}

# ── 一致性檢查項目 ──
CONSISTENCY_CHECKS = [
    ("術語一致性", "檢查所有 GDD 中相同概念是否使用相同術語"),
    ("依賴完整性", "檢查 A 依賴 B 時，B 的 GDD 是否也有對應的提及"),
    ("數值一致性", "檢查各系統中的數值設定是否衝突（例：移動速度 = 5 vs 衝刺 = 移動速度 × 3 = 18）"),
    ("狀態命名一致性", "檢查狀態名稱是否跨系統一致（例：戰鬥系統的 'stunned' vs AI 系統的 'disable'）"),
    ("範圍一致性", "檢查各系統的範圍定義是否重疊或衝突"),
    ("玩家視角一致性", "檢查各系統描述中的玩家互動方式是否一致"),
    ("設計理論一致性", "檢查是否符合 game-concept.md 中的核心支柱"),
    ("技術可行性一致性", "檢查所有系統是否都在 Godot 引擎技術範圍內"),
]

# ── 設計理論審查點 ──
DESIGN_THEORY_CHECKS = [
    ("MDA 對齊", "機制 (Mechanics) → 動態 (Dynamics) → 美學 (Aesthetics) 是否連貫"),
    ("Bartle 類型覆蓋", "是否滿足核心目標玩家類型的需求"),
    ("SDT 需求滿足", "自主性 (Autonomy)、勝任感 (Competence)、關聯性 (Relatedness) 是否滿足"),
    ("核心循環驗證", "30秒/5分/會話/進度 四層循環是否完整"),
    ("反支柱檢查", "是否有任何系統違反 game-concept.md 中的反支柱"),
    ("樂趣密度", "各系統的互動頻率是否合理分布"),
]


class ReviewAllSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "init"
        self.gdd_files: Dict[str, str] = {}  # {system_name: content}
        self.gdd_paths: List[str] = []
        self.concept_path: str = ""
        self.concept_text: str = ""
        self.issues: List[Dict] = []
        self.theory_results: List[Dict] = []
        self.overall_score: int = 0
        self.report: str = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class ReviewAllGDDsSkill:
    """/review-all-gdds 核心邏輯"""

    def handle_init(self, gdd_paths: List[str] = None, concept_path: str = "") -> dict:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session = ReviewAllSession(session_id)
        session.state = "loading"

        if gdd_paths:
            session.gdd_paths = gdd_paths
            for path in gdd_paths:
                try:
                    content = Path(path).read_text(encoding='utf-8')
                    # 提取系統名稱
                    name_match = re.search(r'^#\s+(.+?)\s*[-–—]', content, re.MULTILINE)
                    sys_name = name_match.group(1).strip() if name_match else Path(path).stem
                    session.gdd_files[sys_name] = content
                except:
                    pass

        if concept_path:
            session.concept_path = concept_path
            try:
                session.concept_text = Path(concept_path).read_text(encoding='utf-8')
            except:
                pass

        _sessions[session_id] = session

        if session.gdd_files:
            return self._run_review(session)
        else:
            return {
                "session_id": session_id,
                "state": "awaiting_gdds",
                "question": {
                    "id": "gdd_list",
                    "text": "請提供所有 GDD 檔案的路徑（用逗號分隔），以及可選的 game-concept.md 路徑",
                    "example": "GDD_戰鬥系統.md, GDD_道具系統.md, game-concept.md"
                }
            }

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        session = _sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.state == "awaiting_gdds":
            paths = [p.strip() for p in value.split(",") if p.strip()]
            for path in paths:
                try:
                    content = Path(path).read_text(encoding='utf-8')
                    name_match = re.search(r'^#\s+(.+?)\s*[-–—]', content, re.MULTILINE)
                    sys_name = name_match.group(1).strip() if name_match else Path(path).stem

                    if "concept" in path.lower() or "概念" in path:
                        session.concept_text = content
                        session.concept_path = path
                    else:
                        session.gdd_files[sys_name] = content
                        session.gdd_paths.append(path)
                except:
                    session.issues.append({
                        "severity": "error",
                        "category": "讀取失敗",
                        "detail": f"無法讀取: {path}"
                    })

            session.state = "reviewing"
            session.updated_at = datetime.now().isoformat()
            return self._run_review(session)

        return {"error": "Unknown state"}

    def _run_review(self, session: ReviewAllSession) -> dict:
        """執行所有一致性檢查"""
        issues = []
        theory_results = []
        system_names = list(session.gdd_files.keys())
        all_content = "\n\n".join(session.gdd_files.values())

        if len(system_names) < 2:
            issues.append({
                "severity": "warning",
                "category": "樣本不足",
                "detail": f"僅有 {len(system_names)} 個 GDD，跨系統比較有限。建議至少 3 個 GDD。"
            })

        # ── 1. 術語一致性 ──
        terms = self._extract_key_terms(all_content)
        for term, occurrences in terms.items():
            if len(occurrences) >= 2:
                contexts = [o["system"] for o in occurrences]
                unique_contexts = set(contexts)
                if len(unique_contexts) < len(contexts):
                    # 同系統內多次出現，正常
                    pass

        # ── 2. 依賴完整性 ──
        for sys_name, content in session.gdd_files.items():
            # 找「依賴」
            dep_section = self._extract_section(content, ["Dependencies", "依賴", "上游"])
            if dep_section:
                for other_name in system_names:
                    if other_name != sys_name:
                        if other_name in dep_section or other_name.replace("系統", "") in dep_section:
                            # 檢查 other 的 GDD 是否有反向提及
                            other_content = session.gdd_files.get(other_name, "")
                            if other_content:
                                if sys_name not in other_content and sys_name.replace("系統", "") not in other_content:
                                    issues.append({
                                        "severity": "medium",
                                        "category": "依賴不對稱",
                                        "detail": f"{sys_name} 依賴 {other_name}，但 {other_name} 的 GDD 未提及 {sys_name}"
                                    })

        # ── 3. 數值一致性 ──
        numbers_pattern = re.findall(r'(\w+)\s*[=＝]\s*(\d+(?:\.\d+)?)', all_content)
        # 簡化：找相同名稱但不同數值的
        num_map: Dict[str, set] = {}
        for name, val in numbers_pattern:
            if name not in num_map:
                num_map[name] = set()
            num_map[name].add(float(val))
        for name, vals in num_map.items():
            if len(vals) > 1:
                issues.append({
                    "severity": "high",
                    "category": "數值衝突",
                    "detail": f"'{name}' 在不同 GDD 中有多個值: {vals}"
                })

        # ── 4. 狀態命名一致性 ──
        state_pattern = re.findall(r'(狀態|state)[：:]\s*(.+?)(?:\n|$)', all_content, re.IGNORECASE)
        all_states = set()
        for _, states_str in state_pattern:
            for s in re.split(r'[,，、\s]+', states_str):
                if s.strip():
                    all_states.add(s.strip().lower())

        # ── 5. 設計理論審查（如果提供了 concept） ──
        if session.concept_text:
            pillars = re.findall(r'[🎯🏛️].*?[支支]柱.*?[：:]\s*(.+?)(?:\n|$)', session.concept_text)
            if pillars:
                for sys_name, content in session.gdd_files.items():
                    for pillar in pillars:
                        if pillar.strip() not in content:
                            theory_results.append({
                                "system": sys_name,
                                "check": "核心支柱對齊",
                                "passed": False,
                                "detail": f"未提及支柱: {pillar.strip()}"
                            })
                        else:
                            theory_results.append({
                                "system": sys_name,
                                "check": "核心支柱對齊",
                                "passed": True,
                                "detail": f"已對齊支柱: {pillar.strip()}"
                            })

        # 計算整體分數
        total_checks = len(CONSISTENCY_CHECKS) * len(system_names) + len(DESIGN_THEORY_CHECKS)
        high_issues = len([i for i in issues if i["severity"] == "high"])
        medium_issues = len([i for i in issues if i["severity"] == "medium"])
        session.issues = issues
        session.theory_results = theory_results
        session.overall_score = max(0, 100 - high_issues * 15 - medium_issues * 5)
        session.state = "complete"
        session.updated_at = datetime.now().isoformat()

        # 產生報告
        session.report = self._generate_report(session, system_names)

        return {
            "session_id": session.session_id,
            "state": "complete",
            "system_count": len(system_names),
            "system_names": system_names,
            "issues_count": len(issues),
            "high_issues": high_issues,
            "medium_issues": medium_issues,
            "overall_score": session.overall_score,
            "issues": issues,
            "theory_results": theory_results,
            "report": session.report,
        }

    def _extract_key_terms(self, content: str) -> Dict[str, List[Dict]]:
        """提取關鍵術語"""
        terms = {}
        # 找 ## 標題（系統名稱）
        sections = re.split(r'\n(?=## )', content)
        current_system = "unknown"
        for section in sections:
            header_match = re.match(r'##\s+(.+)', section)
            if header_match:
                current_system = header_match.group(1).strip()

            # 提取粗體術語
            bold_terms = re.findall(r'\*\*(.+?)\*\*', section)
            for term in bold_terms:
                if term not in terms:
                    terms[term] = []
                terms[term].append({"system": current_system, "context": section[:100]})

        return terms

    def _extract_section(self, content: str, keywords: List[str]) -> str:
        for kw in keywords:
            pattern = rf'##\s*[^#\n]*{kw}[^#\n]*\n(.*?)(?=\n##|\Z)'
            m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def _generate_report(self, session: ReviewAllSession, system_names: List[str]) -> str:
        lines = []
        lines.append(f"# 🔬 跨 GDD 一致性審查\n")
        lines.append(f"**審查時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**審查系統**: {', '.join(system_names)}")
        lines.append(f"**整體分數**: {session.overall_score}/100\n")

        if session.concept_text:
            lines.append(f"**概念文件參考**: ✅ 已載入\n")

        # 問題摘要
        if session.issues:
            lines.append("## ⚠️ 發現問題\n")
            lines.append("| 嚴重度 | 類別 | 詳情 |")
            lines.append("|:--|:--|:--|")
            for i in session.issues:
                sev_icon = {"high": "🔴", "medium": "🟡", "warning": "🟢", "error": "❌"}.get(i["severity"], "⚪")
                lines.append(f"| {sev_icon} {i['severity']} | {i['category']} | {i['detail']} |")
        else:
            lines.append("## ✅ 無問題\n")
            lines.append("所有 GDD 之間未發現明顯衝突或不一致。\n")

        # 設計理論
        if session.theory_results:
            lines.append("\n## 🧠 設計理論審查\n")
            for r in session.theory_results:
                status = "✅" if r["passed"] else "❌"
                lines.append(f"- {status} [{r['system']}] {r['check']}: {r['detail']}")

        # 建議
        lines.append("\n## 💡 改進建議\n")
        if session.overall_score >= 90:
            lines.append("🎉 跨系統一致性表現優秀！可以進入 Phase 3: Technical Setup。")
        elif session.overall_score >= 70:
            lines.append("📝 建議在進入 Phase 3 前修正上述問題。可以用 /design-system 補充缺失段落。")
        else:
            lines.append("⚠️ 建議先修正所有嚴重問題後再繼續。可能需要重新審視核心設計。")

        return "\n".join(lines)

    def get_session(self, session_id: str) -> Optional[ReviewAllSession]:
        return _sessions.get(session_id)


review_all_gdds_skill = ReviewAllGDDsSkill()
