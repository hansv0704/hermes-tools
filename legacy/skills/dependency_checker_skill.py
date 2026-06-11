
import subprocess
import sys
from skills.base_skill import BaseSkill

class DependencyCheckerSkill(BaseSkill):
    @property
    def name(self):
        return "dependency_checker_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "check_and_install_openai",
                "description": "檢查並安裝 openai 套件。",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def execute(self, tool_name, args):
        if tool_name == "check_and_install_openai":
            try:
                import openai
                return {"status": "success", "message": "openai 套件已安裝。"}
            except ImportError:
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai"])
                    return {"status": "success", "message": "openai 套件安裝成功。"}
                except Exception as e:
                    return {"status": "error", "message": f"安裝失敗: {str(e)}"}
