import pandas as pd
import os
from skills.base_skill import BaseSkill

class ExcelCustomProcessorSkill(BaseSkill):
    @property
    def name(self):
        return "excel_custom_processor_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "match_disaster_data",
                "description": "將『水保局全省災害資料』中的崩塌面積配對到『工作表1 (2)』並儲存至新分頁。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Excel 檔案路徑"}
                    },
                    "required": ["file_path"]
                }
            }
        ]

    def execute(self, tool_name: str, params: dict, context: dict = None):
        if tool_name == "match_disaster_data":
            file_path = params.get("file_path")
            if not file_path or not os.path.exists(file_path):
                return {"status": "error", "message": f"檔案路徑不存在: {file_path}"}
            
            try:
                # 讀取 Excel 所有工作表
                xls = pd.ExcelFile(file_path)
                sheet_names = xls.sheet_names
                
                if '工作表1 (2)' not in sheet_names or '水保局全省災害資料' not in sheet_names:
                    return {"status": "error", "message": f"找不到必要的工作表。現有分頁: {sheet_names}"}

                df_target = pd.read_excel(xls, sheet_name='工作表1 (2)')
                df_source = pd.read_excel(xls, sheet_name='水保局全省災害資料')

                # 數據清洗：移除欄位名稱的空格
                df_target.columns = [str(c).strip() for c in df_target.columns]
                df_source.columns = [str(c).strip() for c in df_source.columns]

                # 尋找配對鍵
                target_key = '事件' if '事件' in df_target.columns else df_target.columns[0]
                source_key = None
                for k in ['觸發事件', '事件名稱', '事件']:
                    if k in df_source.columns:
                        source_key = k
                        break
                if not source_key:
                    source_key = df_source.columns[0]

                # 確保配對鍵為字串且無空格
                df_target[target_key] = df_target[target_key].astype(str).str.strip()
                df_source[source_key] = df_source[source_key].astype(str).str.strip()

                # 提取崩塌面積欄位 (模糊匹配)
                area_col = None
                for c in df_source.columns:
                    if '崩塌面積' in c:
                        area_col = c
                        break
                
                if not area_col:
                    return {"status": "error", "message": "在來源表中找不到包含 '崩塌面積' 的欄位。"}

                # 關鍵修正：將崩塌面積轉為數值，處理混合類型錯誤
                df_source[area_col] = pd.to_numeric(df_source[area_col], errors='coerce')

                # 執行配對 (Left Join)
                # 為了避免一對多導致列數增加，我們先對來源表進行去重
                df_source_clean = df_source[[source_key, area_col]].dropna(subset=[area_col])
                df_source_clean = df_source_clean.groupby(source_key)[area_col].max().reset_index()

                df_merged = pd.merge(
                    df_target,
                    df_source_clean,
                    left_on=target_key,
                    right_on=source_key,
                    how='left'
                )

                # 移除重複的 key 欄位
                if target_key != source_key and source_key in df_merged.columns:
                    df_merged = df_merged.drop(columns=[source_key])

                # 寫入新分頁
                with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df_merged.to_excel(writer, sheet_name='配對結果_崩塌面積', index=False)

                return {
                    "status": "success", 
                    "message": f"配對完成！已在檔案中新增分頁『配對結果_崩塌面積』。配對成功(非空值)筆數: {df_merged[area_col].notna().sum()}"
                }

            except Exception as e:
                import traceback
                return {"status": "error", "message": f"執行失敗: {str(e)}\n{traceback.format_exc()}"}
        
        return {"status": "error", "message": f"未知工具: {tool_name}"}
