"""
Gmail IMAP 讀取 Skill
使用 IMAP + App Password，永久免 OAuth
純 Python 標準庫，零外部依賴
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
from base_skill import BaseSkill


class GmailSkill(BaseSkill):
    """Gmail IMAP 讀取 Skill"""

    @property
    def name(self) -> str:
        return "gmail_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "gmail_connect",
                "description": "連接 Gmail IMAP 伺服器並登入。使用 .env 中的 GMAIL_EMAIL 和 GMAIL_APP_PASSWORD。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "gmail_list_inbox",
                "description": "列出收件匣中最近的 N 封郵件（僅顯示寄件人、主旨、日期）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "要列出的郵件數量，預設 10"}
                    },
                    "required": []
                }
            },
            {
                "name": "gmail_search_mail",
                "description": "依關鍵字搜尋郵件（支援寄件人、主旨、內容關鍵字）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜尋關鍵字"},
                        "search_field": {
                            "type": "string",
                            "description": "搜尋欄位：FROM, SUBJECT, BODY, TEXT，預設 TEXT（全文）",
                            "default": "TEXT"
                        }
                    },
                    "required": ["keyword"]
                }
            },
            {
                "name": "gmail_read_mail",
                "description": "讀取特定郵件的完整內容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mail_index": {"type": "integer", "description": "郵件索引號（從 gmail_list_inbox 或 gmail_search_mail 取得）"}
                    },
                    "required": ["mail_index"]
                }
            }
        ]

    def _connect(self):
        """建立 IMAP 連線並登入"""
        email_addr = os.getenv("GMAIL_EMAIL")
        app_password = os.getenv("GMAIL_APP_PASSWORD")

        if not email_addr or not app_password:
            raise ValueError("請先在 .env 中設定 GMAIL_EMAIL 和 GMAIL_APP_PASSWORD")

        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, app_password)
        return mail

    def _decode_header_value(self, raw_value):
        """解碼郵件標頭（處理 =?UTF-8?B?...?= 編碼）"""
        if raw_value is None:
            return ""
        decoded_parts = decode_header(raw_value)
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                charset = charset or "utf-8"
                try:
                    result += part.decode(charset, errors="replace")
                except LookupError:
                    result += part.decode("utf-8", errors="replace")
            else:
                result += str(part)
        return result

    def _parse_email(self, raw_email, index):
        """解析原始郵件為結構化資料"""
        msg = email.message_from_bytes(raw_email)

        subject = self._decode_header_value(msg.get("Subject", ""))
        sender = self._decode_header_value(msg.get("From", ""))
        date_str = msg.get("Date", "")

        try:
            date = parsedate_to_datetime(date_str)
            date_formatted = date.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_formatted = date_str

        # 取得內文
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body += payload.decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
            except Exception:
                pass

        return {
            "index": index,
            "subject": subject,
            "sender": sender,
            "date": date_formatted,
            "body": body[:5000]  # 限制長度
        }

    def execute(self, tool_name: str, args: dict, context: dict) -> dict:
        try:
            if tool_name == "gmail_connect":
                mail = self._connect()
                mail.select("INBOX")
                status, messages = mail.search(None, "ALL")
                mail.logout()
                count = len(messages[0].split()) if messages[0] else 0
                return {"success": True, "total_mails": count, "message": f"成功連接，收件匣共 {count} 封郵件"}

            elif tool_name == "gmail_list_inbox":
                mail = self._connect()
                mail.select("INBOX")
                count = args.get("count", 10)

                status, messages = mail.search(None, "ALL")
                if status != "OK":
                    mail.logout()
                    return {"error": "搜尋郵件失敗"}

                all_ids = messages[0].split()
                if not all_ids:
                    mail.logout()
                    return {"mails": [], "message": "收件匣為空"}

                recent_ids = all_ids[-count:]
                result_mails = []

                for mid in reversed(recent_ids):
                    status, data = mail.fetch(mid, "(RFC822)")
                    if status == "OK":
                        parsed = self._parse_email(data[0][1], int(mid))
                        result_mails.append({
                            "index": parsed["index"],
                            "subject": parsed["subject"],
                            "sender": parsed["sender"],
                            "date": parsed["date"]
                        })

                mail.logout()
                return {"mails": result_mails, "count": len(result_mails)}

            elif tool_name == "gmail_search_mail":
                mail = self._connect()
                mail.select("INBOX")
                keyword = args["keyword"]
                search_field = args.get("search_field", "TEXT")

                search_criteria = f'({search_field} "{keyword}")'
                status, messages = mail.search(None, search_criteria)

                if status != "OK":
                    mail.logout()
                    return {"error": "搜尋失敗"}

                ids = messages[0].split() if messages[0] else []
                result_mails = []

                for mid in reversed(ids[-20:]):
                    status, data = mail.fetch(mid, "(RFC822)")
                    if status == "OK":
                        parsed = self._parse_email(data[0][1], int(mid))
                        result_mails.append({
                            "index": parsed["index"],
                            "subject": parsed["subject"],
                            "sender": parsed["sender"],
                            "date": parsed["date"]
                        })

                mail.logout()
                return {"keyword": keyword, "mails": result_mails, "count": len(result_mails)}

            elif tool_name == "gmail_read_mail":
                mail = self._connect()
                mail.select("INBOX")
                mail_index = str(args["mail_index"])

                status, data = mail.fetch(mail_index.encode(), "(RFC822)")
                mail.logout()

                if status != "OK":
                    return {"error": f"找不到索引 {mail_index} 的郵件"}

                parsed = self._parse_email(data[0][1], int(mail_index))
                return {"mail": parsed}

            else:
                return {"error": f"未知工具: {tool_name}"}

        except ValueError as e:
            return {"error": str(e)}
        except imaplib.IMAP4.error as e:
            return {"error": f"IMAP 錯誤: {e}"}
        except Exception as e:
            return {"error": f"未預期錯誤: {e}"}
