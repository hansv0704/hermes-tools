
"""
Agent Orchestrator Skill — 移植自 mano-afk 的多層 Agent 協作架構。
負責 spawn Worker Agent、管理角色定義、匯總結果。
"""

import json
from pathlib import Path
from skills.base_skill import BaseSkill
from config import logger


class AgentOrchestratorSkill(BaseSkill):
    """協調器 Skill：讀取角色定義、spawn Worker、匯總結果"""

    def __init__(self, agent=None):
        super().__init__(agent=agent)
        self._roles_cache = {}

    @property
    def name(self) -> str:
        return "agent_orchestrator_skill"

    def get_tool_declarations(self) -> list:
        return [{
            "name": "spawn_worker_agent",
            "description": "【Worker Agent 協調器】spawn 一個專注的 Worker Agent 來執行特定角色任務。"
                           "當 Alice 需要程式碼審查時使用 code_reviewer，"
                           "當需要驗證數據時使用 fact_checker。"
                           "Worker 獨立思考、不寫入主記憶、回傳結構化 JSON。",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "Worker 角色名稱：code_reviewer（程式碼審查）或 fact_checker（事實查核）",
                        "enum": self._get_available_roles()
                    },
                    "task": {
                        "type": "string",
                        "description": "指派給 Worker 的任務描述"
                    },
                    "context": {
                        "type": "string",
                        "description": "額外的上下文資訊，如檔案內容、前後文等（選填）"
                    }
                },
                "required": ["role", "task"]
            }
        }]

    def _get_available_roles(self) -> list:
        """動態掃描 worker_roles/ 目錄，回傳所有可用角色名稱"""
        roles_dir = Path("skills/worker_roles")
        if not roles_dir.exists():
            return []
        return [f.stem for f in roles_dir.glob("*.json")]

    def _find_role_file(self, role_name: str) -> Path:
        """尋找角色定義 JSON 檔案"""
        if role_name in self._roles_cache:
            return self._roles_cache[role_name]

        # 多路徑搜尋
        search_paths = [
            Path("skills/worker_roles") / f"{role_name}.json",
        ]

        for path in search_paths:
            if path.exists():
                self._roles_cache[role_name] = path
                return path

        raise FileNotFoundError(f"找不到角色定義檔案: {role_name}.json，搜尋路徑: {[str(p) for p in search_paths]}")

    def _load_role_definition(self, role_name: str) -> dict:
        """載入角色定義 JSON"""
        path = self._find_role_file(role_name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"載入角色定義失敗 {path}: {e}")
            raise

    async def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name != "spawn_worker_agent":
            return {"status": "error", "message": f"未知函數: {function_name}"}

        role_name = args.get("role", "")
        task = args.get("task", "")
        extra_context = args.get("context", "")

        # 載入角色定義
        try:
            role_def = self._load_role_definition(role_name)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"載入角色定義失敗: {e}"}

        # 需求驗證 — 任務不可為空
        if not task.strip():
            return {"status": "skipped", "reason": "任務描述為空，略過 Worker 呼叫"}

        logger.info(f"🤖 [Orchestrator] Spawning Worker: {role_name} | Task: {task[:80]}...")

        # Spawn Worker Engine
        from engines.engine_worker import WorkerEngine

        try:
            worker = WorkerEngine(self.agent, role_def)
            result = await worker.run(task, extra_context)

            # 記錄 Worker 結果
            verdict = result.get("verdict", "unknown")
            turns = result.get("_turns_used", "?")
            logger.info(f"✅ [Orchestrator] Worker {role_name} 完成 (verdict={verdict}, turns={turns})")

            return {
                "status": "success",
                "role": role_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"❌ [Orchestrator] Worker {role_name} 失敗: {e}")
            return {
                "status": "error",
                "role": role_name,
                "message": str(e)
            }
