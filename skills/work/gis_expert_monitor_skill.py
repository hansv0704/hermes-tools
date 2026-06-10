import os
import re
import json
from pathlib import Path
from base_skill import BaseSkill
from config import logger

# 嘗試導入獨立的 GIS 工具
try:
    import gis_utils_v1 as gis_utils
except ImportError:
    try:
        import gis_utils
    except ImportError:
        gis_utils = None

class GisExpertMonitorSkill(BaseSkill):
    @property
    def name(self):
        return "gis_expert_monitor_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "check_gis_status",
                "description": "GIS 專家巡檢：檢查 JSON 狀態與日誌。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "manual_trigger": {"type": "boolean", "description": "是否為手動觸發。"}
                    }
                }
            },
            {
                "name": "get_gis_chart",
                "description": "生成指定測站(Station)的全維度數據趨勢報告 (包含 GPS, TM, GW 三連圖)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uid": {"type": "string", "description": "測站 ID (例如 DS011_02 或完整儀器 ID DS011_02_GPS)"}
                    },
                    "required": ["uid"]
                }
            },
            {
                "name": "set_gis_sensor_status",
                "description": "修改儀器狀態。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uid": {"type": "string", "description": "儀器 ID"},
                        "status": {"type": "string", "description": "ack, maint, normal, default"},
                        "reason": {"type": "string", "description": "原因"}
                    },
                    "required": ["uid", "status", "reason"]
                }
            }
        ]

    def execute(self, tool_name, args, context):
        if tool_name == "check_gis_status":
            return self._run_expert_inspection(args.get("manual_trigger", False), context)
        elif tool_name == "get_gis_chart":
            return self._generate_professional_report(args.get("uid"), context)
        elif tool_name == "set_gis_sensor_status":
            return self._update_config_status(args.get("uid"), args.get("status"), args.get("reason", ""), context)
        return {"error": "Unsupported tool"}

    def _get_config_path(self):
        gis_dir = os.getenv("GIS_DATA_DIR", r"C:\Users\hans\Desktop\大崩儀器DATA回傳")
        return Path(gis_dir) / "sensor_config.json"

    def _generate_professional_report(self, uid, context):
        if not gis_utils:
            return {"status": "error", "message": "找不到獨立的 gis_utils 模組，請確認檔案是否存在。"}

        match = re.match(r"(DS\d+_\d+)", uid)
        if not match:
            return {"status": "error", "message": f"無法辨識測站 ID: {uid}"}
        st_id = match.group(1)
        site_id = st_id.split('_')[0]

        logger.info(f"📊 Alice 正在透過獨立工具為 {st_id} 生成報告...")
        
        # 呼叫獨立工具進行數據擷取
        data = gis_utils.fetch_history(site_id, st_id)
        if not data["times"]:
            return {"status": "error", "message": f"無法獲取 {st_id} 的歷史數據。"}

        try:
            # 呼叫獨立工具繪圖，並自動存入 photo/YYYYMMDD/
            output_path, msg = gis_utils.generate_professional_chart(st_id, data)
            if output_path:
                return {
                    "status": "success", 
                    "message": f"📊 **{st_id} 全維度趨勢報告已生成並存檔。**\n儲存路徑: {output_path}",
                    "file_path": output_path
                }
            else:
                return {"status": "error", "message": f"繪圖失敗: {msg}"}
        except Exception as e:
            return {"status": "error", "message": f"執行繪圖工具時發生異常: {str(e)}"}

    def _run_expert_inspection(self, manual, context):
        config_path = self._get_config_path()
        try:
            with open(config_path, "r", encoding="utf-8") as f: config = json.load(f)
        except: return {"status": "error", "message": "讀取 JSON 失敗。"}
        p_set = config.get("pending_set", [])
        pending_details = config.get("pending_details", {})
        ccd_status = config.get("ccd_status", {})
        ccd_offline = [k for k, v in ccd_status.items() if v == "offline"]
        if not p_set and not ccd_offline and not manual: return {"status": "quiet"}
        report = "🚨 **GIS 專家巡檢報告**\n"
        for uid in p_set:
            level = pending_details.get(uid, "alert")
            if level in ("alert", "freeze"):
                emoji = "🔴 警戒"
            elif level == "attention":
                emoji = "🟡 注意"
            else:
                emoji = "🚨 異常"
            report += f"\n🔍 **分析對象：{uid}** ({emoji})\n   - [建議]：執行 `get_gis_chart` 查看全維度趨勢。\n"
        if ccd_offline:
            report += "\n⚠️ **CCD 斷線警報**\n"
            for ccd in ccd_offline:
                report += f"   - {ccd} CCD 目前為 **offline** 🔴\n"
        return {"status": "success", "message": report}

    def _update_config_status(self, uid, status, reason, context):
        config_path = self._get_config_path()
        target_sets = {"ack": "acknowledged_set", "maint": "maintenance_set", "normal": "normal_set"}
        try:
            with open(config_path, "r", encoding="utf-8") as f: config = json.load(f)
            # 1. 從 pending_set 移除
            if uid in config.get("pending_set", []): config["pending_set"].remove(uid)
            # 1b. 從 pending_details 移除
            if "pending_details" in config and uid in config["pending_details"]:
                del config["pending_details"][uid]
            # 2. 從所有其他 set 中移除以避免重複
            for s in ["acknowledged_set", "maintenance_set", "normal_set"]:
                lst = config.get(s, [])
                if uid in lst: lst.remove(uid)
            # 3. 加入目標 set (default 模式則不加入任何 set，回歸純監控)
            if status != "default" and status in target_sets:
                target_key = target_sets[status]
                config.setdefault(target_key, []).append(uid)
            # 4. 先用暫存檔寫入再取代，防止檔案競爭導致空白
            tmp_path = str(config_path) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=4)
            os.replace(tmp_path, config_path)
            logger.info(f"✅ GIS 狀態已更新: {uid} → {status}")
            return {"status": "success", "message": f"✅ 已將 {uid} 更新為 {status}。"}
        except Exception as e:
            logger.error(f"❌ 更新 GIS 狀態失敗: {e}")
            return {"status": "error", "message": f"更新失敗: {str(e)}"}
