import pandas as pd
from skills.base_skill import BaseSkill

class ReadSpecificExcelRowSkill(BaseSkill):
    @property
    def name(self):
        return "read_specific_excel_row_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "read_specific_excel_row",
                "description": "讀取大型 Excel 檔案中的特定列 (1-indexed)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Excel 檔案路徑"},
                        "sheet_name": {"type": "string", "description": "工作表名稱 (選填，預設為第一張)"},
                        "row_number": {"type": "integer", "description": "列號 (1-indexed)"}
                    },
                    "required": ["file_path", "row_number"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict):
        if function_name == "read_specific_excel_row":
            file_path = args.get("file_path")
            sheet_name = args.get("sheet_name", 0) # Default to first sheet
            row_number = args.get("row_number")
            
            try:
                # To get the header and a specific row efficiently:
                # 1. Read the header
                header_df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
                cols = header_df.columns.tolist()
                
                # 2. Read the specific row
                # skiprows=row_number-1 means we skip the header and all rows before the target row.
                # But since we want to use the original header, we skip row_number-1 rows and provide names.
                df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=row_number-1, nrows=1, header=None, names=cols)
                
                # Fix NaN for JSON serialization
                df = df.fillna("")
                
                # Convert any remaining non-serializable types (like Timestamps) to string
                for col in df.columns:
                    df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (pd.Timestamp, pd.Timedelta)) else x)
                
                data = df.to_dict(orient="records")
                return {"status": "success", "data": data[0] if data else {}}
            except Exception as e:
                import traceback
                return {"status": "error", "message": f"{str(e)}\n{traceback.format_exc()}"}
