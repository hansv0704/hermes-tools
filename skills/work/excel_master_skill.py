import pandas as pd
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import numpy as np
import datetime
from base_skill import BaseSkill

class ExcelMasterSkill(BaseSkill):
    def __init__(self, agent=None):
        super().__init__(agent)
        # 設定中文字體以防圖表亂碼 (針對 Windows 環境優化)
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
        plt.rcParams['axes.unicode_minus'] = False

    @property
    def name(self):
        return "excel_master_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "excel_master_analyze",
                "description": "【Excel 大師分析】支援單/多檔案讀取、複雜數據清洗、分組統計與自定義邏輯運算。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Excel 檔案路徑清單"},
                        "operations": {
                            "type": "array", 
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["read", "group_by", "filter", "merge", "stats"]},
                                    "params": {
                                        "type": "object",
                                        "properties": {
                                            "file_path": {"type": "string"},
                                            "sheet_name": {"type": "string", "description": "工作表名稱 (選填)"},
                                            "column": {"type": "string"},
                                            "target_col": {"type": "string"}
                                        }
                                    }
                                }
                            },
                            "description": "要執行的操作序列"
                        }
                    },
                    "required": ["file_paths", "operations"]
                }
            },
            {
                "name": "excel_master_compare",
                "description": "【Excel 大師比對】精準分析兩個 Excel 檔案之間的差異，支援跨表關聯比對。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_a": {"type": "string", "description": "檔案 A 路徑"},
                        "file_b": {"type": "string", "description": "檔案 B 路徑"},
                        "key_column": {"type": "string", "description": "用來對齊的主鍵欄位名稱"}
                    },
                    "required": ["file_a", "file_b", "key_column"]
                }
            },
            {
                "name": "excel_master_visualize",
                "description": "【Excel 大師視覺化】生成專業級圖表 (折線圖、柱狀圖、散佈圖、熱力圖)，並儲存為圖片。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "數據來源檔案路徑"},
                        "chart_type": {"type": "string", "enum": ["line", "bar", "scatter", "heatmap", "box"]},
                        "x_axis": {"type": "string", "description": "X 軸欄位"},
                        "y_axis": {"type": "array", "items": {"type": "string"}, "description": "Y 軸欄位清單"},
                        "title": {"type": "string", "description": "圖表標題"},
                        "output_path": {"type": "string", "description": "圖片輸出路徑 (預設為 excel_chart.png)"}
                    },
                    "required": ["file_path", "chart_type", "x_axis", "y_axis"]
                }
            },
            {
                "name": "excel_master_edit",
                "description": "【Excel 大師編輯】精準修改儲存格、新增欄位或工作表，不破壞原格式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "目標檔案路徑"},
                        "sheet_name": {"type": "string", "description": "工作表名稱"},
                        "edits": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "cell": {"type": "string", "description": "儲存格位置 (如 A1)"},
                                    "value": {"type": "string", "description": "寫入內容"}
                                }
                            }
                        }
                    },
                    "required": ["file_path", "edits"]
                }
            }
        ]

    def execute(self, tool_name, params, context):
        try:
            if tool_name == "excel_master_analyze":
                return self._handle_analyze(params)
            elif tool_name == "excel_master_compare":
                return self._handle_compare(params)
            elif tool_name == "excel_master_visualize":
                return self._handle_visualize(params)
            elif tool_name == "excel_master_edit":
                return self._handle_edit(params)
        except Exception as e:
            return {"status": "error", "message": f"Excel 大師執行失敗: {str(e)}"}

    def _clean_nan(self, data):
        """遞迴清理字典或列表中的 NaN，將其轉換為 None (JSON 友善)"""
        if isinstance(data, dict):
            return {k: self._clean_nan(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_nan(v) for v in data]
        elif isinstance(data, (float, np.float64, np.float32)) and np.isnan(data):
            return None
        elif pd.isna(data):
            return None
        elif isinstance(data, (pd.Timestamp, datetime.datetime)):
            return data.isoformat()
        return data

    def _handle_analyze(self, params):
        result_summary = {}
        
        for op in params['operations']:
            op_type = op['type']
            p = op.get('params', {})
            path = p.get('file_path', params['file_paths'][0])
            sheet = p.get('sheet_name', 0) # 預設讀取第一張表
            
            df = pd.read_excel(path, sheet_name=sheet)
            
            if op_type == "stats":
                result_summary[f"stats_{os.path.basename(path)}_{sheet}"] = df.describe().to_dict()
            
            elif op_type == "group_by":
                col = p.get('column')
                target = p.get('target_col')
                if col and target:
                    res = df.groupby(col)[target].agg(['mean', 'max', 'min', 'count'])
                    result_summary[f"group_{col}_{sheet}"] = res.to_dict()
            
            elif op_type == "read":
                result_summary[f"read_{os.path.basename(path)}_{sheet}"] = {
                    "columns": df.columns.tolist(),
                    "head": df.head(10).to_dict(),
                    "total_rows": len(df)
                }

        return self._clean_nan(result_summary)

    def _handle_compare(self, params):
        df_a = pd.read_excel(params['file_a'])
        df_b = pd.read_excel(params['file_b'])
        key = params['key_column']
        
        merged = pd.merge(df_a, df_b, on=key, how='outer', suffixes=('_A', '_B'), indicator=True)
        diff = merged[merged['_merge'] != 'both']
        
        result = {
            "summary": f"比對完成。檔案 A 筆數: {len(df_a)}, 檔案 B 筆數: {len(df_b)}",
            "diff_count": len(diff),
            "diff_sample": diff.head(10).to_dict()
        }
        return self._clean_nan(result)

    def _handle_visualize(self, params):
        df = pd.read_excel(params['file_path'])
        plt.figure(figsize=(12, 6))
        
        chart_type = params['chart_type']
        x = params['x_axis']
        ys = params['y_axis']
        output = params.get('output_path', 'excel_chart.png')

        if chart_type == "line":
            for y in ys:
                plt.plot(df[x], df[y], label=y)
        elif chart_type == "bar":
            df.plot(kind='bar', x=x, y=ys, ax=plt.gca())
        elif chart_type == "scatter":
            plt.scatter(df[x], df[ys[0]])
        elif chart_type == "heatmap":
            sns.heatmap(df.corr(), annot=True, cmap='coolwarm')
        
        plt.title(params.get('title', 'Excel 數據趨勢分析'))
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        
        return {"status": "success", "message": f"圖表已生成並儲存至: {os.path.abspath(output)}", "output_path": output}

    def _handle_edit(self, params):
        wb = openpyxl.load_workbook(params['file_path'])
        sheet = wb[params['sheet_name']] if params.get('sheet_name') else wb.active
        
        for edit in params['edits']:
            sheet[edit['cell']] = edit['value']
            
        wb.save(params['file_path'])
        return {"status": "success", "message": f"檔案已成功更新: {params['file_path']}"}
