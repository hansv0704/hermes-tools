"""
【Background Self-Review Skill v1.0】
借鑒 NousResearch/hermes-agent 的 _run_review_in_thread() 設計：
- Fork 子 Agent 審查記憶+技能質量
- 每 N 輪自動觸發，或透過 schedule_reminder 定時審查
- 產出結構化健康報告

核心機制對應：
  hermes-agent memory_manager.py  → _review_memory()    記憶評分、淘汰建議
  hermes-agent skill_manager.py   → _review_skills()    技能成功率、封裝建議
  hermes-agent conversation_loop  → _run_full_review()  整合審查 + 報告生成
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from base_skill import BaseSkill


class SelfReviewSkill(BaseSkill):
    """Background Self-Review：定時自我審查記憶/技能/架構質量"""

    @property
    def name(self) -> str:
        return "self_review_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "self_review",
                "description": "【自我審查】執行全面的系統健康檢查，包含記憶質量、技能成功率、架構一致性。借鑒 hermes-agent 的 Fork 子 Agent 審查機制。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "enum": ["full", "memory", "skills", "architecture", "trigger_check"],
                            "description": "審查範圍：full=全面, memory=記憶, skills=技能, architecture=架構, trigger_check=檢查是否需要觸發審查"
                        }
                    },
                    "required": []
                }
            }
        ]

    # ── 路徑常數 ──
    _MEMORY_DIR = Path("memory")
    _ALICE_DIR = Path(".alice")
    _SKILLS_DIR = Path("skills")
    _EXPERIENCE_PATH = _MEMORY_DIR / "skill_experience.json"
    _REVIEW_LOG_PATH = _MEMORY_DIR / "self_review_log.json"

    # ── 審查觸發閾值 ──
    DEFAULT_REVIEW_INTERVAL = 20       # 每 20 輪對話觸發
    DEFAULT_MEMORY_WARN_SIZE = 800     # 短期記憶超過此值警告
    DEFAULT_FTS_WARN_SIZE = 800        # FTS 超過此值警告
    DEFAULT_SKILL_FAILURE_RATE = 0.5   # 技能失敗率超過 50% 警告

    # ═══════════════════════════════════════════════════════════
    # 公開介面
    # ═══════════════════════════════════════════════════════════

    def execute(self, tool_name: str, parameters: Dict, context: Dict) -> Dict:
        if tool_name == "self_review":
            scope = parameters.get("scope", "full")

            if scope == "trigger_check":
                return self._check_trigger(context)

            report = self._run_review(scope, context)
            return {
                "status": "success",
                "report": report,
                "message": f"自我審查完成（範圍：{scope}）"
            }

        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    # ═══════════════════════════════════════════════════════════
    # 觸發檢查
    # ═══════════════════════════════════════════════════════════

    def _check_trigger(self, context: Dict) -> Dict:
        """檢查是否該觸發自我審查（每 N 輪對話）"""
        agent = context.get("agent")
        if not agent:
            return {"should_review": False, "reason": "無法存取 agent"}

        # 從長期記憶讀取計數器
        settings = agent.memory.long_term.get("settings", {})
        counter = settings.get("self_review_counter", 0)
        interval = settings.get("self_review_interval", self.DEFAULT_REVIEW_INTERVAL)

        should_review = counter >= interval
        return {
            "should_review": should_review,
            "counter": counter,
            "interval": interval,
            "remaining": max(0, interval - counter)
        }

    def increment_counter(self, agent) -> int:
        """遞增審查計數器（每次對話後由 agent.py 呼叫）"""
        settings = agent.memory.long_term.get("settings", {})
        counter = settings.get("self_review_counter", 0) + 1
        settings["self_review_counter"] = counter
        agent.memory.long_term["settings"] = settings
        agent.memory.unsaved_changes = True
        return counter

    def reset_counter(self, agent) -> None:
        """重置審查計數器（審查完成後呼叫）"""
        settings = agent.memory.long_term.get("settings", {})
        settings["self_review_counter"] = 0
        agent.memory.long_term["settings"] = settings
        agent.memory.unsaved_changes = True

    # ═══════════════════════════════════════════════════════════
    # 主審查流程
    # ═══════════════════════════════════════════════════════════

    def _run_review(self, scope: str, context: Dict) -> Dict[str, Any]:
        """執行全面自我審查（借鑒 hermes-agent _run_review_in_thread）"""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope": scope,
            "overall_health": "healthy",
            "warnings": [],
            "suggestions": [],
            "sections": {}
        }

        if scope in ("full", "memory"):
            mem = self._review_memory(context)
            results["sections"]["memory"] = mem
            if mem.get("warnings"):
                results["warnings"].extend(mem["warnings"])
            if mem.get("suggestions"):
                results["suggestions"].extend(mem["suggestions"])

        if scope in ("full", "skills"):
            sk = self._review_skills(context)
            results["sections"]["skills"] = sk
            if sk.get("warnings"):
                results["warnings"].extend(sk["warnings"])
            if sk.get("suggestions"):
                results["suggestions"].extend(sk["suggestions"])

        if scope in ("full", "architecture"):
            arch = self._review_architecture(context)
            results["sections"]["architecture"] = arch
            if arch.get("warnings"):
                results["warnings"].extend(arch["warnings"])
            if arch.get("suggestions"):
                results["suggestions"].extend(arch["suggestions"])

        # 計算整體健康度
        if results["warnings"]:
            critical = any("🔴" in w for w in results["warnings"])
            results["overall_health"] = "critical" if critical else "warning"

        # 寫入審查日誌
        self._save_review_log(results)

        # 重置計數器
        agent = context.get("agent")
        if agent:
            self.reset_counter(agent)

        return results

    # ═══════════════════════════════════════════════════════════
    # 記憶審查（對應 hermes-agent memory_manager.py）
    # ═══════════════════════════════════════════════════════════

    def _review_memory(self, context: Dict) -> Dict[str, Any]:
        """審查記憶系統健康度：規模、壓縮狀態、向量庫連線"""
        result = {
            "status": "ok",
            "warnings": [],
            "suggestions": [],
            "metrics": {}
        }

        agent = context.get("agent")
        if not agent:
            result["status"] = "skipped"
            result["warnings"].append("⚠️ 無法存取 agent，跳過記憶審查")
            return result

        memory = agent.memory

        # ── 1. 短期記憶規模 ──
        st_len = len(memory.short_term)
        result["metrics"]["short_term_count"] = st_len
        if st_len > self.DEFAULT_MEMORY_WARN_SIZE:
            result["warnings"].append(
                f"🟡 短期記憶膨脹：{st_len} 筆（建議 < {self.DEFAULT_MEMORY_WARN_SIZE}），"
                f"下次整合時將自動修剪至 200 筆"
            )

        # ── 2. 中期記憶規模 ──
        mt_len = len(memory.medium_term)
        result["metrics"]["medium_term_count"] = mt_len
        if mt_len > 40:
            result["warnings"].append(f"🟡 中期記憶接近上限：{mt_len}/50")

        # ── 3. 長期記憶結構 ──
        prefs_len = len(memory.long_term.get("preferences", []))
        knowledge_len = len(memory.long_term.get("knowledge", []))
        directives_len = len(memory.long_term.get("core_directives", []))
        result["metrics"]["preferences_count"] = prefs_len
        result["metrics"]["knowledge_count"] = knowledge_len
        result["metrics"]["core_directives_count"] = directives_len

        if prefs_len > 150:
            result["warnings"].append(f"🟡 偏好記憶接近上限：{prefs_len}/200，下次自動修剪至 150")
        if knowledge_len > 250:
            result["warnings"].append(f"🟡 知識記憶接近上限：{knowledge_len}/300，下次自動壓縮為摘要")

        # ── 4. FTS 全文索引規模 ──
        try:
            import sqlite3
            conn = sqlite3.connect(memory.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM fts_memory")
            fts_count = c.fetchone()[0]
            conn.close()
            result["metrics"]["fts_count"] = fts_count
            if fts_count > self.DEFAULT_FTS_WARN_SIZE:
                result["warnings"].append(
                    f"🟡 FTS 全文索引膨脹：{fts_count} 筆（建議 < {self.DEFAULT_FTS_WARN_SIZE}），"
                    f"下次寫入時將自動壓縮舊記錄為摘要"
                )
        except Exception as e:
            result["metrics"]["fts_count"] = f"查詢失敗: {e}"

        # ── 5. Qdrant 向量庫狀態 ──
        if memory._qdrant_available and memory._qdrant_client:
            try:
                info = memory._qdrant_client.get_collection("alice_memories")
                result["metrics"]["qdrant_vectors"] = info.points_count if info else 0
                result["metrics"]["qdrant_status"] = "connected"
            except Exception:
                result["metrics"]["qdrant_status"] = "error"
                result["warnings"].append("🟡 Qdrant 向量庫查詢失敗，向量搜尋可能降級為純 FTS")
        else:
            result["metrics"]["qdrant_status"] = "disabled"

        # ── 6. 排程任務數量 ──
        pending_tasks = [t for t in memory.tasks
                         if isinstance(t, dict) and t.get("status") == "pending"]
        result["metrics"]["pending_tasks"] = len(pending_tasks)

        # ── 7. 健康評分 ──
        result["health_score"] = self._calc_memory_health(result)
        if result["health_score"] < 60:
            result["warnings"].append(
                f"🔴 記憶健康度低落：{result['health_score']}/100，建議執行 /cleanup 深度優化"
            )
            result["suggestions"].append("執行 /cleanup 深度優化記憶庫")

        return result

    def _calc_memory_health(self, review: Dict) -> int:
        """計算記憶健康分數（0-100），借鑒 hermes-agent 的記憶評分機制"""
        score = 100
        m = review.get("metrics", {})

        st = m.get("short_term_count", 0)
        if st > 800: score -= 30
        elif st > 500: score -= 15

        fts = m.get("fts_count", 0)
        if isinstance(fts, int) and fts > 1000: score -= 20
        elif isinstance(fts, int) and fts > 800: score -= 10

        if m.get("qdrant_status") == "error":
            score -= 10

        prefs = m.get("preferences_count", 0)
        if prefs > 180: score -= 10

        knowledge = m.get("knowledge_count", 0)
        if knowledge > 280: score -= 10

        return max(0, score)

    # ═══════════════════════════════════════════════════════════
    # 技能審查（對應 hermes-agent skill_manager.py）
    # ═══════════════════════════════════════════════════════════

    def _review_skills(self, context: Dict) -> Dict[str, Any]:
        """審查技能系統：成功率、未封裝高頻任務、經驗追蹤"""
        result = {
            "status": "ok",
            "warnings": [],
            "suggestions": [],
            "metrics": {},
            "skill_details": []
        }

        # ── 1. 讀取經驗追蹤檔 ──
        experience = self._load_experience()
        if not experience:
            result["metrics"]["tracked_skills"] = 0
            result["status"] = "no_data"
            return result

        result["metrics"]["tracked_skills"] = len(experience)

        # ── 2. 分析各技能 ──
        low_performers = []
        high_performers_unsuggested = []

        for path_uri, entry in experience.items():
            total = entry.get("total_attempts", 0)
            success = entry.get("success_count", 0)
            failure = entry.get("failure_count", 0)
            partial = entry.get("partial_count", 0)
            last_outcome = entry.get("last_outcome", "?")
            suggested = entry.get("suggested_skill", False)

            if total == 0:
                continue

            success_rate = success / total if total > 0 else 0
            failure_rate = failure / total if total > 0 else 0

            detail = {
                "path_uri": path_uri,
                "total": total,
                "success": success,
                "failure": failure,
                "partial": partial,
                "success_rate": round(success_rate, 3),
                "last_outcome": last_outcome,
                "suggested": suggested
            }
            result["skill_details"].append(detail)

            # 低成功率標記
            if failure_rate > self.DEFAULT_SKILL_FAILURE_RATE and total >= 3:
                low_performers.append((path_uri, failure_rate))

            # 高成功率但未建議封裝
            if success >= 3 and not suggested:
                high_performers_unsuggested.append(path_uri)

        result["metrics"]["low_performers"] = len(low_performers)
        result["metrics"]["high_performers_unsuggested"] = len(high_performers_unsuggested)

        # ── 3. 警告與建議 ──
        for path_uri, rate in low_performers:
            result["warnings"].append(
                f"🔴 技能「{path_uri}」失敗率 {rate:.0%}，"
                f"可能需檢查基礎設施或更新邏輯"
            )

        for path_uri in high_performers_unsuggested:
            skill_name = path_uri.replace("skills://", "").replace("/", "_")
            result["suggestions"].append(
                f"💡 任務「{path_uri}」已成功 >= 3 次，"
                f"建議封裝為永久 Skill（{skill_name}_skill）"
            )

        # ── 4. 技能目錄掃描 ──
        if self._SKILLS_DIR.exists():
            skill_files = list(self._SKILLS_DIR.glob("*_skill.py"))
            result["metrics"]["skill_files_count"] = len(skill_files)
        else:
            result["metrics"]["skill_files_count"] = 0

        # ── 5. 健康評分 ──
        result["health_score"] = self._calc_skill_health(result)

        return result

    def _calc_skill_health(self, review: Dict) -> int:
        """計算技能健康分數（0-100）"""
        score = 100
        m = review.get("metrics", {})
        low = m.get("low_performers", 0)
        if low > 3: score -= 30
        elif low > 1: score -= 15
        elif low > 0: score -= 5

        unsuggested = m.get("high_performers_unsuggested", 0)
        if unsuggested > 0:
            score -= min(unsuggested * 5, 25)

        return max(0, score)

    # ═══════════════════════════════════════════════════════════
    # 架構審查（比對 facts 表 ↔ ARCHITECTURE.md）
    # ═══════════════════════════════════════════════════════════

    def _review_architecture(self, context: Dict) -> Dict[str, Any]:
        """審查架構一致性：facts 表與 ARCHITECTURE.md 交叉比對"""
        result = {
            "status": "ok",
            "warnings": [],
            "suggestions": [],
            "metrics": {}
        }

        # ── 1. 讀取 ARCHITECTURE.md ──
        arch_path = self._ALICE_DIR / "ARCHITECTURE.md"
        arch_servers = {}  # {port: name}
        arch_bats = set()

        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8")
            # 解析獨立伺服器清單表格
            import re
            table_pattern = re.compile(
                r'\|\s*([\w\s\-]+)\s*\|\s*(\d+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|'
            )
            for match in table_pattern.finditer(content):
                name = match.group(1).strip()
                port = match.group(2).strip()
                arch_servers[port] = name

            # 解析 bat 檔
            bat_pattern = re.compile(r'`([^`]+\.bat)`')
            for match in bat_pattern.finditer(content):
                arch_bats.add(match.group(1))

        result["metrics"]["arch_documented_servers"] = len(arch_servers)

        # ── 2. 讀取 DuckDB facts 表 ──
        facts_servers = set()
        try:
            import duckdb
            db_path = Path("data/alice_core.db")
            if db_path.exists():
                conn = duckdb.connect(str(db_path), read_only=True)
                rows = conn.execute(
                    "SELECT fact_key, fact_value FROM system_facts WHERE fact_key LIKE 'arch:%'"
                ).fetchall()
                conn.close()
                for key, value in rows:
                    if "bat" in key:
                        facts_servers.add(value)
                result["metrics"]["facts_arch_entries"] = len(rows)
            else:
                result["metrics"]["facts_arch_entries"] = 0
        except Exception as e:
            result["metrics"]["facts_arch_entries"] = f"查詢失敗: {e}"

        # ── 3. 交叉比對 ──
        # 檢查 ARCHITECTURE.md 中記錄的 bat 檔是否實際存在
        root = Path(".")
        for bat in arch_bats:
            if not (root / bat).exists():
                result["warnings"].append(
                    f"🟡 ARCHITECTURE.md 記錄的 `{bat}` 不存在於根目錄"
                )

        # ── 4. 檢查關鍵設定檔 ──
        critical_files = [
            ".alice/INDEX.md",
            ".alice/FACTS.md",
            ".alice/TASK_BOARD.md",
            ".alice/LOG.md",
            ".alice/ARCHITECTURE.md",
        ]
        for cf in critical_files:
            if not Path(cf).exists():
                result["warnings"].append(f"🔴 關鍵設定檔遺失：{cf}")

        result["metrics"]["critical_files_present"] = sum(
            1 for cf in critical_files if Path(cf).exists()
        )

        # ── 5. 健康評分 ──
        result["health_score"] = self._calc_arch_health(result)

        return result

    def _calc_arch_health(self, review: Dict) -> int:
        """計算架構健康分數（0-100）"""
        score = 100
        m = review.get("metrics", {})
        present = m.get("critical_files_present", 5)
        missing = 5 - present
        score -= missing * 20

        warnings_count = len(review.get("warnings", []))
        score -= warnings_count * 5

        return max(0, score)

    # ═══════════════════════════════════════════════════════════
    # 經驗檔讀寫（與 brain_orchestrator_skill.py 共用同一檔案）
    # ═══════════════════════════════════════════════════════════

    def _load_experience(self) -> Dict[str, Any]:
        """載入經驗追蹤檔"""
        path = self._EXPERIENCE_PATH
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    # ═══════════════════════════════════════════════════════════
    # 審查日誌
    # ═══════════════════════════════════════════════════════════

    def _save_review_log(self, report: Dict) -> None:
        """將審查報告寫入日誌檔（保留最近 50 筆）"""
        path = self._REVIEW_LOG_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                logs = json.loads(path.read_text(encoding="utf-8"))
            else:
                logs = []
            if not isinstance(logs, list):
                logs = []

            # 只保留摘要，不存完整報告（節省空間）
            summary = {
                "timestamp": report.get("timestamp"),
                "scope": report.get("scope"),
                "overall_health": report.get("overall_health"),
                "warnings_count": len(report.get("warnings", [])),
                "suggestions_count": len(report.get("suggestions", [])),
                "memory_health": report.get("sections", {}).get("memory", {}).get("health_score"),
                "skill_health": report.get("sections", {}).get("skills", {}).get("health_score"),
                "arch_health": report.get("sections", {}).get("architecture", {}).get("health_score"),
            }
            logs.append(summary)

            # 只保留最近 50 筆
            if len(logs) > 50:
                logs = logs[-50:]

            path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logging.debug(f"Failed to save review log: {e}")

    def get_review_history(self, limit: int = 10) -> List[Dict]:
        """讀取審查日誌歷史"""
        path = self._REVIEW_LOG_PATH
        if not path.exists():
            return []
        try:
            logs = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(logs, list):
                return logs[-limit:]
        except Exception:
            pass
        return []
