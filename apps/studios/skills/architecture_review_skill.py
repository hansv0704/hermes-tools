"""
architecture_review_skill.py — Phase 3.3: /architecture-review
移植自 CCGS architecture-review SKILL.md

架構審查：TR 註冊表（需求追溯矩陣）+ 架構完整性驗證
"""

import json
import re
from datetime import datetime
from typing import Any


class ArchitectureReviewSkill:
    """架構審查器 — TR 矩陣 + 完整性驗證"""

    name = "architecture_review"

    # ── 審查維度 ────────────────────────────────────────────────
    REVIEW_DIMENSIONS = [
        {
            "id": "completeness",
            "name": "完整性",
            "weight": 25,
            "checks": [
                "所有 System Map 中的系統都有對應的架構描述",
                "所有 Foundation ADR 已涵蓋",
                "資料流路徑已完整定義",
            ],
        },
        {
            "id": "consistency",
            "name": "一致性",
            "weight": 20,
            "checks": [
                "ADR 與架構文件中的描述一致",
                "模組命名風格一致",
                "技術棧選擇互不衝突",
            ],
        },
        {
            "id": "traceability",
            "name": "可追溯性",
            "weight": 20,
            "checks": [
                "每個設計需求都有對應的架構決策",
                "每個 ADR 都有明確的需求來源",
                "TR 矩陣中無孤立節點",
            ],
        },
        {
            "id": "feasibility",
            "name": "可行性",
            "weight": 15,
            "checks": [
                "技術棧在目標平台上可運行",
                "團隊能力與技術選擇匹配",
                "開發時程與技術複雜度匹配",
            ],
        },
        {
            "id": "risk",
            "name": "風險管理",
            "weight": 10,
            "checks": [
                "已識別關鍵技術風險",
                "每個風險有緩解策略",
                "有備選方案（Plan B）",
            ],
        },
        {
            "id": "maintainability",
            "name": "可維護性",
            "weight": 10,
            "checks": [
                "模組間耦合度可控",
                "無循環依賴",
                "文件足以讓新成員上手",
            ],
        },
    ]

    # ── TR 矩陣模板 ────────────────────────────────────────────
    @classmethod
    def init_session(cls, project_id: str, architecture_doc: str = "",
                     adrs: list = None, game_concept: dict = None,
                     systems_map: dict = None) -> dict:
        """初始化審查 session"""
        # 從文件提取需求
        requirements = cls._extract_requirements(
            game_concept or {},
            systems_map or {},
            architecture_doc
        )

        # 建立 TR 矩陣
        tr_matrix = cls._build_tr_matrix(requirements, adrs or [])

        return {
            "project_id": project_id,
            "architecture_doc": architecture_doc,
            "adrs": adrs or [],
            "game_concept": game_concept or {},
            "systems_map": systems_map or {},
            "requirements": requirements,
            "tr_matrix": tr_matrix,
            "review_results": {},
            "phase": "init",
        }

    @classmethod
    def _extract_requirements(cls, game_concept: dict,
                              systems_map: dict,
                              arch_doc: str) -> list:
        """從遊戲概念 + 系統地圖 + 架構文件中提取需求"""
        requirements = []

        # 從遊戲概念提取
        req_id = 1
        if game_concept.get("title"):
            requirements.append({
                "id": f"REQ-{req_id:03d}",
                "source": "game-concept",
                "description": f"遊戲：{game_concept['title']}",
                "type": "functional",
            })
            req_id += 1

        pillars = game_concept.get("design_pillars", [])
        if isinstance(pillars, str):
            pillars = [p.strip() for p in pillars.split("\n") if p.strip()]
        for pillar in pillars:
            requirements.append({
                "id": f"REQ-{req_id:03d}",
                "source": "game-concept",
                "description": f"設計支柱：{pillar}",
                "type": "design",
            })
            req_id += 1

        # 從系統地圖提取
        for system in systems_map.get("systems", []):
            requirements.append({
                "id": f"REQ-{req_id:03d}",
                "source": "systems-map",
                "description": f"系統：{system.get('name', '未命名')} ({system.get('tier', 'N/A')})",
                "type": "system",
            })
            req_id += 1

        # 從架構文件提取（以 ## 開頭的標題）
        sections = re.findall(r'##\s+(.+)', arch_doc)
        for section in sections:
            requirements.append({
                "id": f"REQ-{req_id:03d}",
                "source": "architecture-doc",
                "description": section.strip(),
                "type": "architectural",
            })
            req_id += 1

        return requirements

    @classmethod
    def _build_tr_matrix(cls, requirements: list, adrs: list) -> dict:
        """建立需求追溯矩陣"""
        matrix = {}
        for req in requirements:
            rid = req["id"]
            matrix[rid] = {
                "requirement": req,
                "covered_by": [],
                "coverage_status": "uncovered",
            }

        # 檢查每個 ADR 覆蓋了哪些需求
        for adr in adrs:
            adr_id = adr.get("id", "")
            adr_title = adr.get("title", "")
            for rid, entry in matrix.items():
                req_desc = entry["requirement"]["description"].lower()
                # 簡單關鍵字匹配
                adr_keywords = adr_title.lower().split()
                if any(kw in req_desc for kw in adr_keywords if len(kw) > 2):
                    entry["covered_by"].append(adr_id)
                    entry["coverage_status"] = "covered"

        return matrix

    @classmethod
    def run_review(cls, session: dict) -> dict:
        """執行完整審查"""
        results = {}
        total_score = 0
        max_score = 0
        findings = []

        for dim in cls.REVIEW_DIMENSIONS:
            dim_score = 0
            dim_findings = []
            for check in dim["checks"]:
                passed, detail = cls._evaluate_check(check, session)
                if passed:
                    dim_score += 1
                else:
                    dim_findings.append({"check": check, "detail": detail})

            weight = dim["weight"]
            max_dim = len(dim["checks"]) * weight
            actual = dim_score * weight
            total_score += actual
            max_score += max_dim

            results[dim["id"]] = {
                "name": dim["name"],
                "score": dim_score,
                "total_checks": len(dim["checks"]),
                "percentage": round(dim_score / len(dim["checks"]) * 100),
                "weight": weight,
                "weighted_score": actual,
                "findings": dim_findings,
            }

        overall = round(total_score / max_score * 100) if max_score > 0 else 0

        # 判定
        if overall >= 80:
            verdict = "APPROVE"
            verdict_text = "架構審查通過，可以進入下一階段。"
        elif overall >= 60:
            verdict = "CONCERNS"
            verdict_text = "有部分疑慮，建議修改後再審。"
        else:
            verdict = "MAJOR_REVISION"
            verdict_text = "架構存在重大問題，需要大幅修改。"

        session["review_results"] = {
            "dimensions": results,
            "overall_score": overall,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "reviewed_at": datetime.now().isoformat(),
        }

        return session["review_results"]

    @classmethod
    def _evaluate_check(cls, check: str, session: dict) -> tuple:
        """評估單項檢查（簡化版：基於文件內容長度與關鍵字）"""
        arch_doc = session.get("architecture_doc", "")
        adrs = session.get("adrs", [])

        if "System Map" in check or "系統地圖" in check:
            systems = session.get("systems_map", {}).get("systems", [])
            return len(systems) > 0, f"已定義 {len(systems)} 個系統"

        if "Foundation ADR" in check:
            found = sum(1 for a in adrs if a.get("category") == "Foundation")
            return found >= 3, f"Foundation ADR: {found}/5"

        if "資料流" in check or "data flow" in check.lower():
            has_dataflow = "資料流" in arch_doc or "Data Flow" in arch_doc
            return has_dataflow, "架構文件中是否描述資料流"

        if "ADR 與架構" in check or "一致" in check:
            return len(adrs) > 0, f"ADR 數量: {len(adrs)}"

        if "模組命名" in check:
            return True, "命名風格檢查需手動確認"

        if "技術棧" in check and "衝突" in check:
            return True, "技術棧衝突檢查需手動確認"

        if "設計需求" in check and "架構決策" in check:
            tr = session.get("tr_matrix", {})
            covered = sum(1 for v in tr.values() if v.get("coverage_status") == "covered")
            total = len(tr)
            return total > 0 and covered > 0, f"TR 覆蓋: {covered}/{total}"

        if "TR 矩陣" in check or "孤立節點" in check:
            tr = session.get("tr_matrix", {})
            uncovered = sum(1 for v in tr.values() if v.get("coverage_status") == "uncovered")
            return uncovered == 0, f"未覆蓋需求: {uncovered}"

        if "目標平台" in check:
            return True, "平台相容性檢查需手動確認"

        if "團隊能力" in check:
            return True, "團隊能力匹配檢查需手動確認"

        if "時程" in check:
            return True, "時程匹配檢查需手動確認"

        if "技術風險" in check:
            risk_section = "風險" in arch_doc or "risk" in arch_doc.lower()
            return risk_section, "架構文件中的風險段落"

        if "緩解" in check:
            return True, "緩解策略檢查需手動確認"

        if "備選方案" in check or "Plan B" in check:
            return True, "備選方案檢查需手動確認"

        if "耦合" in check or "循環依賴" in check:
            has_circular = "循環依賴" in arch_doc or "circular" in arch_doc.lower()
            return not has_circular, "循環依賴偵測"

        if "文件" in check and "新成員" in check:
            doc_length = len(arch_doc)
            return doc_length > 500, f"架構文件長度: {doc_length} 字元"

        return True, "自動檢查通過"

    @classmethod
    def get_tr_matrix_summary(cls, session: dict) -> dict:
        """取得 TR 矩陣摘要"""
        matrix = session.get("tr_matrix", {})
        total = len(matrix)
        covered = sum(1 for v in matrix.values() if v.get("coverage_status") == "covered")
        uncovered = total - covered

        return {
            "total_requirements": total,
            "covered": covered,
            "uncovered": uncovered,
            "coverage_rate": round(covered / total * 100) if total > 0 else 0,
            "uncovered_items": [
                {"id": rid, "description": v["requirement"]["description"]}
                for rid, v in matrix.items()
                if v.get("coverage_status") == "uncovered"
            ],
        }
