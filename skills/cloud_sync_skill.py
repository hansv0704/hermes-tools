import os
import zipfile
import time
import shutil
from datetime import datetime
from base_skill import BaseSkill
from config import logger
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

class CloudSyncSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "cloud_sync_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "backup_architecture_to_cloud",
                "description": "【全量備份】打包 Alice 資料夾並上傳至 Google Drive。已優化排除邏輯，防止備份套娃。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder_name": {"type": "string", "description": "雲端資料夾名稱"}
                    },
                }
            },
            {
                "name": "upload_existing_backup",
                "description": "【補傳工具】將本地已存在的備份壓縮檔補傳至雲端。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "壓縮檔路徑"},
                        "folder_name": {"type": "string", "description": "雲端資料夾名稱"}
                    },
                    "required": ["file_path"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "backup_architecture_to_cloud":
            return self._backup_and_upload(args.get("folder_name", "alice"))
        elif function_name == "upload_existing_backup":
            return self._direct_upload(args.get("file_path"), args.get("folder_name", "alice"))
        return {"error": "Unknown function"}

    def _wait_for_file_release(self, file_path, timeout=10):
        """等待檔案被作業系統釋放，解決 WinError 32"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 嘗試以附加模式開啟檔案，若成功代表檔案沒被鎖定
                with open(file_path, 'a'):
                    pass
                return True
            except IOError:
                time.sleep(1)
        return False

    def _backup_and_upload(self, folder_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"Alice_Full_Backup_{timestamp}.zip"
        temp_dir = Path("temp_sync_workplace")
        temp_dir.mkdir(exist_ok=True)
        zip_path = temp_dir / zip_filename
        
        try:
            # 確保 zip 檔案寫入完成並關閉
            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk("."):
                    # 排除不必要的資料夾
                    if any(x in root for x in ["__pycache__", ".git", ".venv", "node_modules", "backups", "temp_sync_workplace"]): 
                        continue
                    for file in files:
                        if file.endswith(".zip") or "Alice_Full_Backup_" in file:
                            continue
                        f_p = os.path.join(root, file)
                        zipf.write(f_p, os.path.relpath(f_p, "."))
            
            logger.info(f"📦 打包完成，等待系統釋放控制權: {zip_filename}")
            
            # 物理檢查檔案是否已釋放
            if self._wait_for_file_release(str(zip_path)):
                return self._direct_upload(str(zip_path), folder_name, cleanup_dir=temp_dir)
            else:
                return {"status": "error", "message": "檔案長時間被鎖定，上傳取消。"}
                
        except Exception as e:
            return {"status": "error", "message": f"打包失敗: {str(e)}"}

    def _direct_upload(self, file_path, folder_name, cleanup_dir=None):
        if not HAS_GDRIVE: return {"status": "error", "message": "No Google SDK"}
        try:
            # 確保檔案存在且可讀取
            if not os.path.exists(file_path):
                return {"status": "error", "message": f"找不到檔案: {file_path}"}

            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            creds = Credentials.from_authorized_user_file('token.json', SCOPES) if os.path.exists('token.json') else None
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
                else: creds = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES).run_local_server(port=0)
                with open('token.json', 'w') as t: t.write(creds.to_json())
            
            service = build('drive', 'v3', credentials=creds)
            q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            f_results = service.files().list(q=q, fields='files(id)').execute()
            f_id = f_results.get('files')[0]['id'] if f_results.get('files') else service.files().create(body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}, fields='id').execute().get('id')
            
            media = MediaFileUpload(file_path, resumable=True)
            up = service.files().create(body={'name': os.path.basename(file_path), 'parents': [f_id]}, media_body=media, fields='webViewLink').execute()
            
            # 上傳成功後再清理
            if cleanup_dir and os.path.exists(cleanup_dir):
                # 這裡也要防禦性清理，防止刪除時檔案還在被 MediaFileUpload 占用
                time.sleep(1)
                try:
                    shutil.rmtree(cleanup_dir)
                except:
                    pass # 清理失敗不影響上傳成功的結果
            
            return {"status": "success", "message": f"Uploaded {os.path.basename(file_path)}", "link": up.get('webViewLink')}
        except Exception as e:
            # 統一回傳錯誤，不再讓外部觸發補傳邏輯
            logger.error(f"❌ 上傳失敗: {str(e)}")
            return {"status": "error", "message": f"上傳失敗: {str(e)}"}
