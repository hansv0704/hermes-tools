import os
import sys
import win32com.client
from skills.base_skill import BaseSkill

class ExcelLiveSkill(BaseSkill):
    @property
    def name(self):
        return "excel_live_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "excel_live_edit",
                "description": "【Excel 現場操控】直接對接桌面上正在運行的 Excel 視窗進行即時編輯或讀取。不需要關閉檔案。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作類型：'write' (寫入), 'read' (讀取)",
                            "enum": ["write", "read"]
                        },
                        "cell": {
                            "type": "string",
                            "description": "儲存格位置 (如 'A1')"
                        },
                        "value": {
                            "type": "string",
                            "description": "欲寫入的內容 (僅用於 action='write')"
                        },
                        "sheet_name": {
                            "type": "string",
                            "description": "工作表名稱 (選填，預設為當前活動工作表)"
                        }
                    },
                    "required": ["action", "cell"]
                }
            }
        ]

    def execute(self, tool_name, params, context=None):
        if tool_name == "excel_live_edit":
            action = params.get("action")
            cell = params.get("cell")
            value = params.get("value")
            sheet_name = params.get("sheet_name")

            try:
                # 嘗試抓取當前運行的 Excel 實例
                try:
                    # 使用 Dispatch 配合 GetActiveObject 確保能抓到現有的
                    excel = win32com.client.GetActiveObject("Excel.Application")
                except Exception:
                    return {"error": "找不到正在運行的 Excel 程式。請確保 Excel 已開啟並處於活動狀態。"}

                # 獲取當前活動的活頁簿
                try:
                    wb = excel.ActiveWorkbook
                    if not wb:
                        return {"error": "Excel 已開啟，但找不到任何活動中的活頁簿。"}
                except Exception:
                    return {"error": "無法獲取活動中的活頁簿。"}

                # 獲取工作表
                if sheet_name:
                    try:
                        ws = wb.Worksheets(sheet_name)
                    except Exception:
                        return {"error": f"找不到名為 '{sheet_name}' 的工作表。"}
                else:
                    ws = excel.ActiveSheet

                if action == "write":
                    ws.Range(cell).Value = value
                    return {"status": "success", "message": f"已成功在 '{ws.Name}' 的 {cell} 寫入: {value}"}
                elif action == "read":
                    val = ws.Range(cell).Value
                    return {"status": "success", "cell": cell, "value": str(val)}

            except Exception as e:
                return {"error": f"執行 Excel 現場操控時發生錯誤: {str(e)}"}
        
        return {"error": f"Unknown tool: {tool_name}"}
