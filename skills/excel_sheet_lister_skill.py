import win32com.client
from skills.base_skill import BaseSkill

class ExcelSheetListerSkill(BaseSkill):
    @property
    def name(self):
        return "excel_sheet_lister_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "list_active_excel_sheets",
                "description": "列出當前活動 Excel 活頁簿中的所有工作表名稱。",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def execute(self, tool_name, args, context):
        if tool_name == "list_active_excel_sheets":
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
                wb = excel.ActiveWorkbook
                sheets = [sheet.Name for sheet in wb.Worksheets]
                return {"status": "success", "sheets": sheets, "active_workbook": wb.Name}
            except Exception as e:
                return {"status": "error", "message": str(e)}
