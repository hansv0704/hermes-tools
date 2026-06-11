import abc

class BaseSkill(abc.ABC):
    """
    Skill 基礎類別。
    所有新的擴充能力都應繼承此類別，並放入 skills/ 目錄下。系統將自動掃描並載入。
    MCP 協議未來也可以通過繼承這個類別來註冊到 ToolManager。
    """
    
    def __init__(self, agent=None):
        """初始化 Skill，可選擇性接收 agent 實體"""
        self.agent = agent
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """回傳 Skill 的唯一名稱"""
        return "base_skill"
        
    @abc.abstractmethod
    def get_tool_declarations(self) -> list:
        """回傳給 Gemini 的工具定義結構 (function_declarations format)"""
        return []

    @abc.abstractmethod
    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        """執行具體的工具邏輯"""
        pass
