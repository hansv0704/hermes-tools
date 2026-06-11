import os
import pandas as pd
import win32com.client
from typing import List, Dict, Any
from base_skill import BaseSkill

class DynamicExcelMatcherSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "dynamic_excel_matcher_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "execute_dynamic_excel_match",
                "description": "【Excel 通用配對引擎】執行跨表多重條件模糊比對與資料擴充。支援 100% 參數化，無硬編碼。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Excel 檔案路徑"},
                        "target_sheet": {"type": "string", "description": "目標工作表名稱 (要填入資料的地方)"},
                        "source_sheet": {"type": "string", "description": "來源工作表名稱 (資料來源)"},
                        "target_keys": {"type": "array", "items": {"type": "string"}, "description": "目標表比對欄位名稱清單"},
                        "source_keys": {"type": "array", "items": {"type": "string"}, "description": "來源表比對欄位名稱清單"},
                        "match_modes": {"type": "array", "items": {"type": "string"}, "description": "比對模式：'exact' (精準) 或 'fuzzy' (包含)"},
                        "data_mapping": {"type": "object", "description": "資料映射字典 {來源欄位: 目標欄位}"},
                        "source_filter_col": {"type": "string", "description": "來源表過濾欄位 (選填)"},
                        "source_filter_min": {"type": "number", "description": "來源表過濾最小值 (選填)"},
                        "expand_unmatched": {"type": "boolean", "description": "是否將來源表中未配對的資料追加到目標表底部"}
                    },
                    "required": ["file_path", "target_sheet", "source_sheet", "target_keys", "source_keys", "match_modes", "data_mapping"]
                }
            }
        ]

    def execute(self, tool_name: str, args: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        if tool_name != "execute_dynamic_excel_match":
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        file_path = args["file_path"]
        target_sheet_name = args["target_sheet"]
        source_sheet_name = args["source_sheet"]
        target_keys = args["target_keys"]
        source_keys = args["source_keys"]
        match_modes = args["match_modes"]
        data_mapping = args["data_mapping"]
        source_filter_col = args.get("source_filter_col")
        source_filter_min = args.get("source_filter_min")
        expand_unmatched = args.get("expand_unmatched", False)

        try:
            # 1. 讀取資料
            df_target = pd.read_excel(file_path, sheet_name=target_sheet_name)
            df_source = pd.read_excel(file_path, sheet_name=source_sheet_name)

            # 2. 來源表過濾
            if source_filter_col and source_filter_min is not None:
                df_source = df_source[df_source[source_filter_col] >= source_filter_min]

            # 3. 執行配對邏輯 (記憶體中處理)
            matched_indices_in_source = set()
            
            # 準備寫入的資料結構
            updates = [] # List of (row_index, col_name, value)

            for t_idx, t_row in df_target.iterrows():
                match_found = False
                for s_idx, s_row in df_source.iterrows():
                    conditions = []
                    for i in range(len(target_keys)):
                        t_val = str(t_row.get(target_keys[i], "")).strip()
                        s_val = str(s_row.get(source_keys[i], "")).strip()
                        
                        if match_modes[i] == "exact":
                            conditions.append(t_val == s_val)
                        elif match_modes[i] == "fuzzy":
                            conditions.append(t_val in s_val or s_val in t_val)
                    
                    if all(conditions):
                        match_found = True
                        matched_indices_in_source.add(s_idx)
                        for s_col, t_col in data_mapping.items():
                            val = s_row.get(s_col)
                            # 處理 Timestamp 轉字串
                            if pd.api.types.is_datetime64_any_dtype(val) or isinstance(val, pd.Timestamp):
                                val = val.strftime('%Y-%m-%d %H:%M:%S') if not pd.isnull(val) else ""
                            updates.append((t_idx + 2, t_col, val)) # Excel row is 1-based, +1 for header
                        break # 找到第一個匹配就跳出

            # 4. 準備擴充資料
            new_rows = []
            if expand_unmatched:
                unmatched_df = df_source[~df_source.index.isin(matched_indices_in_source)]
                for _, s_row in unmatched_df.iterrows():
                    new_row_data = {}
                    # 這裡假設擴充是將來源表的對應欄位填入目標表的對應欄位，其餘留空
                    for s_col, t_col in data_mapping.items():
                        val = s_row.get(s_col)
                        if pd.api.types.is_datetime64_any_dtype(val) or isinstance(val, pd.Timestamp):
                            val = val.strftime('%Y-%m-%d %H:%M:%S') if not pd.isnull(val) else ""
                        new_row_data[t_col] = val
                    # 同時也要填入比對用的 Key 欄位，方便辨識
                    for i in range(len(target_keys)):
                        new_row_data[target_keys[i]] = s_row.get(source_keys[i])
                    new_rows.append(new_row_data)

            # 5. 透過 COM 寫入 Excel
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            sheet = wb.Worksheets(target_sheet_name)

            # 執行更新
            # 為了效率，我們先找出目標欄位的索引
            col_map = {}
            for j in range(1, sheet.UsedRange.Columns.Count + 1):
                header = sheet.Cells(1, j).Value
                if header:
                    col_map[header] = j

            for row_idx, col_name, val in updates:
                if col_name in col_map:
                    sheet.Cells(row_idx, col_map[col_name]).Value = val

            # 執行擴充
            if new_rows:
                last_row = sheet.UsedRange.Rows.Count + 1
                for row_data in new_rows:
                    for col_name, val in row_data.items():
                        if col_name in col_map:
                            sheet.Cells(last_row, col_map[col_name]).Value = val
                    last_row += 1

            wb.Save()
            wb.Close()
            return {"status": "success", "message": f"成功完成配對與擴充。更新了 {len(updates)//len(data_mapping) if data_mapping else 0} 筆現有資料，追加了 {len(new_rows)} 筆新資料。"}

        except Exception as e:
            return {"status": "error", "message": f"執行失敗: {str(e)}"}
        finally:
            if 'excel' in locals():
                excel.Quit()
