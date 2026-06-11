import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# 載入環境變數 (強制覆寫以解決重啟快取問題)
load_dotenv(override=True)

# 設定日誌格式
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# 1. 檔案日誌 (錯誤紀錄): alice_error.log
# 當發生 ERROR 等級以上的錯誤時，會寫入此檔案，方便事後查閱 Traceback
file_handler = RotatingFileHandler(
    "alice_error.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
)
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(log_formatter)

# 2. Console 日誌 (一般資訊)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# 初始化 Root Logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger("Alice_System")

class APIKeyManager:
    def __init__(self):
        keys_str = os.getenv("GOOGLE_API_KEYS", "")
        self.keys = [k.strip() for k in keys_str.replace("\\n", ",").split(",") if k.strip()]
        if not self.keys:
            logger.critical("❌ 未在 .env 找到 GOOGLE_API_KEYS")
            self.keys = []
        self.current_key_index = 0

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_key_index]

    def rotate_key(self):
        if not self.keys: return None
        prev_key = self.keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        new_key = self.keys[self.current_key_index]
        logger.warning(f"🔄 API Key 切換: {prev_key[:5]}... -> {new_key[:5]}...")
        return new_key
