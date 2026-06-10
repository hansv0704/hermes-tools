---
name: alice-excel
description: "Excel 自動化工具包 — 即時編輯、篩選儲存、公式注入、工作表管理、動態配對、災害資料配對。合併自 7 個 Alice Excel 技能。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, excel, office, automation]
    source: "合併自 Alice Bot: excel_live, excel_filter_save, excel_formula_builder, excel_custom_processor, dynamic_excel_matcher, read_specific_excel_row, excel_sheet_lister"
---

# Excel 自動化工具包

## ⚠️ 強制規則：主人要求操作 Excel 時，你必須實際執行 terminal 命令。禁止只回文字說明而不執行。

合併 Alice 原有的 7 個 Excel 技能為單一入口。

## 觸發條件

- 主人要求操作 Excel 檔案（讀取、寫入、篩選、公式）
- GIS 災害資料配對
- 主人提及 Excel 相關任務

## 工作目錄

所有指令從此目錄執行：
```
C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953
```

## 操作 1：即時編輯 Excel (excel_live_edit)

直接操控開啟中的 Excel（COM 自動化）。支援：讀取儲存格、寫入、另存新檔。

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from excel_live_skill import ExcelLiveSkill
import json
skill = ExcelLiveSkill()
result = skill.execute('excel_live_edit', {
    'action': 'read',        # read | write | save_as
    'cell': 'A1',
    'value': '新資料'        # write 時需要
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 2：篩選並儲存 (filter_and_save_excel)

依條件篩選 Excel 並另存新檔。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from excel_filter_save_skill import ExcelFilterSaveSkill
import json
skill = ExcelFilterSaveSkill()
result = skill.execute('filter_and_save_excel', {
    'input_path': r'C:\path\to\input.xlsx',
    'output_path': r'C:\path\to\output.xlsx',
    'filters': {'column': 'A', 'value': '條件'}
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 3：注入公式 (inject_excel_formulas)

批次在 Excel 中寫入公式。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from excel_formula_builder_skill import ExcelFormulaBuilderSkill
import json
skill = ExcelFormulaBuilderSkill()
result = skill.execute('inject_excel_formulas', {
    'file_path': r'C:\path\to\file.xlsx',
    'sheet_name': 'Sheet1',
    'formulas': {'B2': '=SUM(A2:A10)', 'C2': '=AVERAGE(A2:A10)'}
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 4：災害資料配對 (match_disaster_data)

GIS 專業用途 — 根據座標/測站配對災害通報與監測資料。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from excel_custom_processor_skill import ExcelCustomProcessorSkill
import json
skill = ExcelCustomProcessorSkill()
result = skill.execute('match_disaster_data', {
    'file_path': r'C:\path\to\disaster_data.xlsx',
    'match_column': '測站名稱'
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 5：動態 Excel 配對 (execute_dynamic_excel_match)

兩個 Excel 之間依動態條件配對。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from dynamic_excel_matcher_skill import DynamicExcelMatcherSkill
import json
skill = DynamicExcelMatcherSkill()
result = skill.execute('execute_dynamic_excel_match', {
    'source_path': r'C:\path\to\source.xlsx',
    'target_path': r'C:\path\to\target.xlsx',
    'match_rules': {'source_col': 'A', 'target_col': 'B'}
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 6：讀取特定行 (read_specific_excel_row)

讀取 Excel 中特定行號的資料。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from read_specific_excel_row_skill import ReadSpecificExcelRowSkill
import json
skill = ReadSpecificExcelRowSkill()
result = skill.execute('read_specific_excel_row', {
    'file_path': r'C:\path\to\file.xlsx',
    'row_number': 5,
    'sheet_name': 'Sheet1'
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 7：列出工作表 (list_active_excel_sheets)

列出 Excel 檔案中所有工作表名稱。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from excel_sheet_lister_skill import ExcelSheetListerSkill
import json
skill = ExcelSheetListerSkill()
result = skill.execute('list_active_excel_sheets', {
    'file_path': r'C:\path\to\file.xlsx'
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 快速參考

| 需求 | 操作 | 技能檔 |
|:--|:--|:--|
| 操控開啟中的 Excel | excel_live_edit | excel_live_skill.py |
| 依條件篩選另存 | filter_and_save_excel | excel_filter_save_skill.py |
| 批次寫入公式 | inject_excel_formulas | excel_formula_builder_skill.py |
| GIS 災害資料配對 | match_disaster_data | excel_custom_processor_skill.py |
| 兩表動態配對 | execute_dynamic_excel_match | dynamic_excel_matcher_skill.py |
| 讀取特定行 | read_specific_excel_row | read_specific_excel_row_skill.py |
| 列工作表名稱 | list_active_excel_sheets | excel_sheet_lister_skill.py |

## 注意

- 操作 1 (excel_live_edit) 需要 Excel 已在桌面開啟
- GIS 災害配對 (match_disaster_data) 為主人專業用途，非一般 Excel 操作
- 所有路徑使用 raw string (r'...') 避免跳脫字元問題
