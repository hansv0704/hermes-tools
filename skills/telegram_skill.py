import os
import httpx
from base_skill import BaseSkill

class TelegramSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "telegram_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "telegram_send_message",
                "description": "透過 Telegram Bot 發送文字訊息給主人。支援 HTML 或 Markdown 格式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "訊息內容"},
                        "chat_id": {"type": "string", "description": "目標 Chat ID (選填，預設為主人)"},
                        "parse_mode": {"type": "string", "description": "HTML 或是 Markdown", "default": "HTML"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "telegram_send_photo",
                "description": "透過 Telegram Bot 發送圖片給主人。自動處理網路 URL 防盜鏈機制。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "photo": {"type": "string", "description": "圖片的 URL 或本地檔案路徑"},
                        "caption": {"type": "string", "description": "圖片說明文字 (選填)"},
                        "chat_id": {"type": "string", "description": "目標 Chat ID (選填)"}
                    },
                    "required": ["photo"]
                }
            },
            {
                "name": "telegram_get_updates",
                "description": "獲取 Telegram Bot 的最新更新訊息 (用於接收主人指令)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "offset": {"type": "integer", "description": "訊息偏移量"},
                        "limit": {"type": "integer", "description": "獲取數量 (預設 100)"}
                    }
                }
            }
        ]

    def execute(self, tool_name: str, args: dict, context: dict) -> dict:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        default_chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_OWNER_ID")
        
        if not token:
            return {"error": "找不到 TELEGRAM_BOT_TOKEN 環境變數。"}

        base_url = f"https://api.telegram.org/bot{token}"
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            if tool_name == "telegram_get_updates":
                params = {
                    "offset": args.get("offset"),
                    "limit": args.get("limit", 100),
                    "timeout": 10
                }
                resp = client.get(f"{base_url}/getUpdates", params=params)
                return resp.json()

            chat_id = args.get("chat_id") or default_chat_id
            if not chat_id:
                return {"error": "未提供 chat_id 且環境變數中無 TELEGRAM_CHAT_ID。"}

            if tool_name == "telegram_send_message":
                payload = {
                    "chat_id": chat_id,
                    "text": args["text"],
                    "parse_mode": args.get("parse_mode", "HTML")
                }
                resp = client.post(f"{base_url}/sendMessage", json=payload)
                return resp.json()
            
            elif tool_name == "telegram_send_photo":
                photo = args["photo"]
                caption = args.get("caption", "")
                temp_file = "temp_tele_img.jpg"
                
                try:
                    if photo.startswith(("http://", "https://")):
                        # 實作鐵律第 13 條：先下載至本地，繞過防盜鏈
                        img_resp = client.get(photo)
                        if img_resp.status_code == 200:
                            with open(temp_file, "wb") as f:
                                f.write(img_resp.content)
                            with open(temp_file, "rb") as f:
                                files = {"photo": f}
                                data = {"chat_id": chat_id, "caption": caption}
                                resp = client.post(f"{base_url}/sendPhoto", data=data, files=files)
                            return resp.json()
                        else:
                            return {"error": f"下載圖片失敗，狀態碼: {img_resp.status_code}"}
                    else:
                        if os.path.exists(photo):
                            with open(photo, 'rb') as f:
                                files = {'photo': f}
                                data = {'chat_id': chat_id, 'caption': caption}
                                resp = client.post(f"{base_url}/sendPhoto", data=data, files=files)
                            return resp.json()
                        else:
                            return {"error": f"找不到檔案: {photo}"}
                finally:
                    # 確保發送後即刻銷毀臨時檔案，不留痕跡
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
        
        return {"error": f"未知工具: {tool_name}"}
