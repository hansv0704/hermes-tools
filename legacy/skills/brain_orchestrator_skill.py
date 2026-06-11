import logging
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from base_skill import BaseSkill

class BrainOrchestratorSkill(BaseSkill):
    """
    【大腦指揮官 v4.3 — 修復 Regex 與強化還原匹配】
    """

    @property
    def name(self) -> str:
        return "brain_orchestrator_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "orchestrate_task",
                "description": "【大腦指揮官】分析複雜任務，制定執行策略並路由至最佳技能。實裝 OODA 循環邏輯。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string", "description": "任務描述"},
                        "context": {"type": "string", "description": "當前環境上下文"}
                    },
                    "required": ["task_description"]
                }
            },
            {
                "name": "record_skill_experience",
                "description": "【經驗海馬體】記錄技能執行結果與教訓。支持 URI 路徑化記憶 (如 skills://os/ime_failure)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path_uri": {"type": "string", "description": "記憶路徑 (例如 skills://work/gis_alert)"},
                        "outcome": {"type": "string", "enum": ["success", "failure", "partial"]},
                        "lesson": {"type": "string", "description": "具體的失敗教訓 or 成功關鍵"},
                        "token_cost": {"type": "integer", "description": "預估消耗的 Token"}
                    },
                    "required": ["path_uri", "outcome", "lesson"]
                }
            }
        ]

    def _analyze_task(self, task: str) -> Dict[str, Any]:
        task_lower = task.lower()
        actions = self._extract_actions(task_lower)
        objects = self._extract_objects(task_lower)
        task_type = self._classify_task(task_lower, actions)
        complexity = self._assess_complexity(task_lower, actions)
        
        return {
            "task_type": task_type,
            "complexity": complexity,
            "needs_scheduling": "監控" in task or "monitor" in task,
            "needs_pro": complexity != "簡單" or "架構" in task or "修改" in task,
            "can_parallel": "同時" in task,
            "estimated_steps": len(actions) + 1,
            "actions": actions,
            "objects": objects
        }

    def _extract_actions(self, task: str) -> List[Dict]:
        action_dict = {
            "讀取": "read", "打開": "open", "查看": "view", "檢查": "check",
            "寫入": "write", "修改": "edit", "新增": "create", "刪除": "delete",
            "搜尋": "search", "查詢": "query", "分析": "analyze", "比對": "compare",
            "發送": "send", "備份": "backup", "還原": "restore", "建立": "create",
            "執行": "run", "啟動": "start", "停止": "stop"
        }
        found = []
        for cn, en in action_dict.items():
            if cn in task: found.append({"cn": cn, "en": en})
        return found

    def _extract_objects(self, task: str) -> List[str]:
        object_keywords = {
            "excel": ["excel", "xlsx", "表格"],
            "檔案": ["檔案", "文件", "file"],
            "圖片": ["圖片", "照片", "image"],
            "股票": ["股票", "股價", "stock"],
            "GIS": ["gis", "監測", "測站"],
            "程式碼": ["程式", "代碼", "code", "python", "skill"],
            "系統": ["系統", "配置", "還原點", "restore point", "備份"]
        }
        found = []
        for obj, kws in object_keywords.items():
            if any(kw in task for kw in kws): found.append(obj)
        return found

    def _classify_task(self, task: str, actions: List[Dict]) -> str:
        categories = {
            "數據分析": ["分析", "統計", "excel"],
            "檔案操作": ["修改", "編輯", "覆寫", "檔案", "還原", "備份", "還原點"],
            "系統開發": ["開發", "程式", "代碼", "skill", "架構"],
            "監控/巡檢": ["監控", "巡檢", "gis"],
            "通訊/通知": ["發送", "通知", "telegram"],
            "電腦操作": ["點擊", "執行", "啟動"]
        }
        for cat, kws in categories.items():
            if any(kw in task for kw in kws): return cat
        return "未分類"

    def _assess_complexity(self, task: str, actions: List[Dict]) -> str:
        score = len(actions) + (2 if "系統" in task or "架構" in task else 0)
        return "複雜" if score > 5 else "中等" if score > 2 else "簡單"

    def _auto_extract_keywords(self, name: str, description: str) -> List[str]:
        combined = f"{name} {description}".lower()
        # 【修復】修正 Regex，確保能正確處理底線與空白
        parts = re.split(r'[\s_]+', combined)
        keywords = {p for p in parts if len(p) > 2 and not p.isdigit()}
        
        cn_tech = ["讀取", "寫入", "修改", "刪除", "新增", "建立", "搜尋", "分析", "比對", "備份", "還原", "監控", "檔案", "圖片", "股票", "Excel", "程式", "系統", "通知", "GIS", "還原點"]
        for term in cn_tech:
            if term in combined: keywords.add(term)
        return list(keywords)

    def _match_task_to_tools(self, task: str, declarations: List[Dict], analysis: Dict) -> Dict:
        task_lower = task.lower()
        scored_tools = []
        for decl in declarations:
            name = decl.get("name", "")
            desc = decl.get("description", "").lower()
            score = 0
            
            # 關鍵字匹配
            kws = self._auto_extract_keywords(name, desc)
            match_count = sum(1 for kw in kws if kw in task_lower)
            score += match_count * 2
            
            # 名稱直接匹配
            if name in task_lower: score += 10
            
            # 還原點/備份特殊加分
            if ("還原" in task or "備份" in task) and any(kw in name for kw in ["restore", "backup"]):
                score += 15

            if score > 0:
                scored_tools.append({"name": name, "score": score, "description": desc})

        scored_tools.sort(key=lambda x: x["score"], reverse=True)
        recommended = [t["name"] for t in scored_tools[:5]]
        
        return {
            "recommended_tools": recommended,
            "reasoning": f"最佳推薦：{recommended[0]}" if recommended else "未找到匹配工具",
            "steps": [{"step": i+1, "tool": t} for i, t in enumerate(recommended[:3])],
            "total_scanned": len(declarations)
        }

    def _decide_execution_plan(self, analysis: Dict, decomposition: Dict) -> Dict:
        rec = decomposition.get("recommended_tools", [])
        if rec:
            return {"decision": "execute", "primary_tools": rec[:3], "plan_summary": f"使用 {rec[0]} 執行任務"}
        return {"decision": "direct_reply", "plan_summary": "直接回應"}

    # ── 經驗追蹤 JSON 路徑（借鑒 hermes-agent skill_usage.py 設計）──
    _EXPERIENCE_PATH = Path("memory/skill_experience.json")

    def _load_experience(self) -> Dict[str, Any]:
        """載入經驗追蹤檔。若不存在或損毀則回傳空 dict。"""
        path = self._EXPERIENCE_PATH
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logging.debug(f"Failed to load skill_experience.json: {e}")
            return {}

    def _save_experience(self, data: Dict[str, Any]) -> None:
        """原子寫入經驗追蹤檔（tempfile → os.replace）。"""
        path = self._EXPERIENCE_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".exp_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            logging.debug(f"Failed to save skill_experience.json: {e}", exc_info=True)

    def _record_experience(self, path_uri: str, outcome: str, lesson: str, token_cost: int = 0) -> Dict[str, Any]:
        """記錄一次任務經驗，更新計數器。"""
        data = self._load_experience()
        key = path_uri
        
        if key not in data:
            data[key] = {
                "success_count": 0,
                "failure_count": 0,
                "partial_count": 0,
                "total_attempts": 0,
                "last_outcome": None,
                "last_lesson": "",
                "last_updated": None,
                "suggested_skill": False,
                "suggested_at": None,
                "first_seen": datetime.now(timezone.utc).isoformat(),
            }
        
        entry = data[key]
        entry["total_attempts"] += 1
        entry["last_outcome"] = outcome
        entry["last_lesson"] = lesson
        entry["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        if outcome == "success":
            entry["success_count"] += 1
        elif outcome == "failure":
            entry["failure_count"] += 1
        elif outcome == "partial":
            entry["partial_count"] += 1
        
        self._save_experience(data)
        return {
            "success_count": entry["success_count"],
            "failure_count": entry["failure_count"],
            "total_attempts": entry["total_attempts"],
        }

    def _check_skill_suggestion(self, path_uri: str) -> Optional[str]:
        """檢查是否該建議封裝成 Skill：連續成功 >= 3 次且尚未建議過。"""
        data = self._load_experience()
        entry = data.get(path_uri)
        if not entry:
            return None
        if entry.get("suggested_skill"):
            return None
        if entry.get("success_count", 0) >= 3:
            entry["suggested_skill"] = True
            entry["suggested_at"] = datetime.now(timezone.utc).isoformat()
            self._save_experience(data)
            skill_name = path_uri.replace("skills://", "").replace("/", "_")
            return (
                f"🔔 任務類型「{path_uri}」已成功 {entry['success_count']} 次，"
                f"建議封裝為永久 Skill（建議名稱：{skill_name}_skill）。"
                f"要我立刻建立嗎？"
            )
        return None

    def execute(self, tool_name: str, parameters: Dict, context: Dict) -> Dict:
        if tool_name == "orchestrate_task":
            task = parameters.get("task_description", "")
            analysis = self._analyze_task(task)
            decls = []
            tool_defs = context.get("tool_definitions", [])
            if tool_defs: decls = tool_defs[0].get("function_declarations", [])
            
            decomp = self._match_task_to_tools(task, decls, analysis)
            decision = self._decide_execution_plan(analysis, decomp)
            
            return {
                "status": "success",
                "analysis": analysis,
                "decomposition": decomp,
                "decision": decision,
                "message": "大腦路由分析完成"
            }
        
        elif tool_name == "record_skill_experience":
            path_uri = parameters.get("path_uri", "")
            outcome = parameters.get("outcome", "failure")
            lesson = parameters.get("lesson", "")
            token_cost = parameters.get("token_cost", 0)
            
            stats = self._record_experience(path_uri, outcome, lesson, token_cost)
            suggestion = self._check_skill_suggestion(path_uri)
            
            response = {
                "status": "success",
                "path_uri": path_uri,
                "outcome": outcome,
                "stats": stats,
                "message": f"經驗已記錄：{path_uri} → {outcome}"
            }
            if suggestion:
                response["suggestion"] = suggestion
            return response
        
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
