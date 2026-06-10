import win32com.client
import os
from skills.base_skill import BaseSkill

class ExcelFormulaBuilderSkill(BaseSkill):
    @property
    def name(self):
        return "excel_formula_builder_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "inject_excel_formulas",
                "description": "【Excel 公式建築師】在指定工作表的特定欄位注入動態公式。支援 {row} 佔位符以實現自動列號對齊。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sheet_name": {"type": "string", "description": "工作表名稱"},
                        "column_letter": {"type": "string", "description": "目標欄位代號 (如 'D')"},
                        "start_row": {"type": "integer", "description": "起始列號 (通常為 2)"},
                        "end_row": {"type": "integer", "description": "結束列號"},
                        "formula_template": {"type": "string", "description": "公式模板，使用 {row} 代表當前列。例如 '=A{row}*B{row}'"}
                    },
                    "required": ["sheet_name", "column_letter", "start_row", "end_row", "formula_template"]
                }
            }
        ]

    def execute(self, tool_name, args, context):
        if tool_name == "inject_excel_formulas":
            sheet_name = args.get("sheet_name")
            col = args.get("column_letter")
            start = args.get("start_row")
            end = args.get("end_row")
            template = args.get("formula_template")
            
            try:
                try:
                    excel = win32com.client.GetActiveObject("Excel.Application")
                except Exception:
                    return {"status": "error", "message": "找不到正在運行的 Excel 程式。"}
                
                wb = excel.ActiveWorkbook
                try:
                    ws = wb.Worksheets(sheet_name)
                except Exception:
                    return {"status": "error", "message": f"找不到工作表: {sheet_name}"}
                
                count = 0
                excel.ScreenUpdating = False
                try:
                    for r in range(start, end + 1):
                        formula = template.replace("{row}", str(r))
                        ws.Range(f"{col}{r}").Formula = formula
                        count += 1
                finally:
                    excel.ScreenUpdating = True
                
                return {"status": "success", "message": f"已在 {sheet_name} 注入 {count} 筆公式。"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
