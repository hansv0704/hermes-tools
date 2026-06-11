import os
import json
import time
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from skills.base_skill import BaseSkill

class GisFileUpdateHandler(FileSystemEventHandler):
    def __init__(self, skill):
        self.skill = skill
        self.last_triggered = {}

    def on_modified(self, event):
        if event.is_directory: return
        path = event.src_path
        filename = os.path.basename(path)
        
        # 監聽 sensor_config.json 或 監控記錄_ 開頭的文字檔
        if "sensor_config.json" in filename or ("監控記錄_" in filename and filename.endswith(".txt")):
            self.skill.handle_change(path)

class GisFileWatcherSkill(BaseSkill):
    @property
    def name(self):
        return "gis_file_watcher_skill"

    def __init__(self, agent=None):
        super().__init__(agent)
        self.gis_path = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
        self.last_notified_pending = []
        self.last_triggered = {}
        self.observer = None

    def start_watching(self):
        """啟動背景監聽執行緒"""
        if not os.path.exists(self.gis_path):
            print(f"⚠️ [GIS Watcher] 路徑不存在: {self.gis_path}")
            return
        
        if self.observer and self.observer.is_alive():
            print("ℹ️ [GIS Watcher] 監聽已在運行中。")
            return

        self.observer = Observer()
        handler = GisFileUpdateHandler(self)
        self.observer.schedule(handler, self.gis_path, recursive=False)
        self.observer.start()
        print(f"🚀 [GIS Watcher] 已啟動背景監聽: {self.gis_path}")

    def stop_watching(self):
        """停止監聽"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("🛑 [GIS Watcher] 監聽已停止。")

    def handle_change(self, path):
        """處理檔案變動邏輯"""
        now = time.time()
        # 3秒冷卻機制
        if now - self.last_triggered.get(path, 0) < 3.0: return
        self.last_triggered[path] = now
        
        config_path = os.path.join(self.gis_path, "sensor_config.json")
        if not os.path.exists(config_path): return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            pending_set = config.get("pending_set", [])
            pending_details = config.get("pending_details", {})
        except Exception as e:
            print(f"❌ [GIS Watcher] 讀取設定失敗: {e}")
            return

        if not pending_set:
            self.last_notified_pending = []
            return

        # 過濾出新出現的異常項目
        new_items = [uid for uid in pending_set if uid not in self.last_notified_pending]
        if not new_items: return
        
        self.last_notified_pending.extend(new_items)
        
        # 透過 Agent 的 Event Loop 觸發非同步警報（傳遞層級資訊）
        if self.agent and hasattr(self.agent, "loop") and self.agent.loop.is_running():
            self.agent.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.auto_gis_alert(new_items, pending_details))
            )

    async def auto_gis_alert(self, uids, pending_details=None):
        """執行產圖與推播，依層級區分 🔴警戒 / 🟡注意"""
        if pending_details is None:
            pending_details = {}
        for uid in uids:
            level = pending_details.get(uid, "alert")  # 預設為 alert (向後相容)
            if level in ("alert", "freeze"):
                emoji = "🔴"
                level_text = "警戒"
                detail = "數值已超過警戒管理基準值！"
            elif level == "attention":
                emoji = "🟡"
                level_text = "注意"
                detail = "數值已超過注意管理基準值。"
            else:
                emoji = "🚨"
                level_text = "異常"
                detail = "偵測到數值異常。"
            print(f"{emoji} [GIS Watcher] 偵測到{level_text}站點: {uid}，準備產圖...")
            # 呼叫 get_gis_chart 工具
            result = await self.agent.tools.execute_tool("get_gis_chart", {"uid": uid})
            
            if result.get("status") == "success" and "file_path" in result:
                caption = f"{emoji} GIS {level_text}警報\n測站: {uid}\n{detail}\n已自動產圖。"
                await self.agent.tools.execute_tool("telegram_send_photo", {
                    "photo": result["file_path"], 
                    "caption": caption
                })
            else:
                msg = f"{emoji} GIS {level_text}警報\n測站: {uid}\n{detail}\n但產圖失敗。"
                await self.agent.tools.execute_tool("telegram_send_message", {"text": msg})

    def get_tool_declarations(self):
        # 此 Skill 主要為背景服務，不提供主動呼叫的工具
        return []

    def execute(self, tool_name, args):
        return {"status": "error", "message": "This skill runs in background."}
