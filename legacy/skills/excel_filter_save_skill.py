import pandas as pd
import os
from skills.base_skill import BaseSkill

class ExcelFilterSaveSkill(BaseSkill):
    @property
    def name(self):
        return "excel_filter_save_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "filter_and_save_excel",
                "description": "讀取 Excel 檔案，根據指定欄位的數值進行過濾，並將結果儲存為新檔案。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "原始 Excel 檔案路徑"},
                        "output_path": {"type": "string", "description": "輸出的 Excel 檔案路徑"},
                        "sheet_name": {"type": "string", "description": "工作表名稱 (選填，預設為第一張)"},
                        "filter_column": {"type": "string", "description": "要過濾的欄位名稱 (如 '年度')"},
                        "min_value": {"type": "number", "description": "保留大於或等於此數值的資料"}
                    },
                    "required": ["input_path", "output_path", "filter_column", "min_value"]
                }
            }
        ]

    def execute(self, tool_name: str, params: dict, context: dict = None):
        if tool_name == "filter_and_save_excel":
            input_path = params.get("input_path")
            output_path = params.get("output_path")
            sheet_name = params.get("sheet_name", 0)
            filter_column = params.get("filter_column")
            min_value = params.get("min_value")

            if not os.path.exists(input_path):
                return {"status": "error", "message": f"找不到原始檔案: {input_path}"}

            try:
                # 讀取資料
                df = pd.read_excel(input_path, sheet_name=sheet_name)
                
                # 確保過濾欄位存在
                if filter_column not in df.columns:
                    return {"status": "error", "message": f"檔案中找不到欄位: {filter_column}。現有欄位: {df.columns.tolist()}"}

                # 轉換為數值並過濾
                df[filter_column] = pd.to_numeric(df[filter_column], errors='coerce')
                filtered_df = df[df[filter_column] >= min_value]

                # 確保輸出目錄存在
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                # 儲存檔案
                filtered_df.to_excel(output_path, index=False)

                return {
                    "status": "success",
                    "message": f"過濾完成！已將 {len(filtered_df)} 筆資料儲存至 {output_path}",
                    "original_count": len(df),
                    "filtered_count": len(filtered_df)
                }

            except Exception as e:
                return {"status": "error", "message": f"Excel 過濾儲存失敗: {str(e)}"}

        return {"status": "error", "message": f"未知工具: {tool_name}"}
