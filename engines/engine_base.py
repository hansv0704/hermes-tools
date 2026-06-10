class BaseEngine:
    def __init__(self, agent):
        self.agent = agent

    def init_session(self):
        """初始化對話會話 (選填)"""
        pass

    async def generate_response(self, final_input, original_input, is_file, media_files=None):
        raise NotImplementedError

    async def summarize(self, memory_list):
        """記憶壓縮 (選填)"""
        return ""
