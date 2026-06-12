---
name: alice-docx
description: "Word 文件自動化工具包 — 讀取文件結構、插入文字、表格重建。合併自 2 個 Alice Word 技能。"
version: 1.1.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, word, docx, office, automation]
    source: "合併自 Alice Bot: word_editor_skill.py, word_table_rebuild_skill.py"
---

# Word 文件自動化工具包

## ⚠️ 強制規則：主人要求操作 Word 文件時，你必須實際執行 terminal 命令。禁止只回文字說明而不執行。

合併 Alice 原有的 2 個 Word 技能。

## 觸發條件

- 主人要求操作 Word 文件
- 主人需要讀取/修改 Word 文件結構
- 主人需要重建 Word 表格

## 工作目錄

```
C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953
```

## 操作 1：讀取文件結構 (word_live_get_structure)

讀取目前開啟中 Word 文件的結構（段落、表格、標題）。

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from word_editor_skill import WordEditorSkill
import json
skill = WordEditorSkill()
result = skill.execute('word_live_get_structure', {}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 2：插入文字 (word_live_insert_text)

在開啟中的 Word 文件指定位置插入文字。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from word_editor_skill import WordEditorSkill
import json
skill = WordEditorSkill()
result = skill.execute('word_live_insert_text', {
    'text': '要插入的內容',
    'position': 'end'        # start | end | cursor | after_paragraph:N
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 操作 3：表格重建 (word_table_rebuild)

根據來源資料重建 Word 文件中的表格。用於從 Excel/CSV 更新 Word 表格。

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from word_table_rebuild_skill import WordTableRebuildSkill
import json
skill = WordTableRebuildSkill()
result = skill.execute('word_table_rebuild', {
    'source_path': r'C:\path\to\source.xlsx',
    'target_docx': r'C:\path\to\target.docx',
    'table_index': 0,         # 第幾個表格（0-based）
    'source_sheet': 'Sheet1'
}, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 快速參考

| 需求 | 操作 | 技能檔 |
|:--|:--|:--|
| 讀取 Word 結構 | word_live_get_structure | word_editor_skill.py |
| 插入文字 | word_live_insert_text | word_editor_skill.py |
| 重建表格 | word_table_rebuild | word_table_rebuild_skill.py |

## 操作 4：用 python-docx 從零建立表格 (create_table)

直接以 python-docx 建立全新表格，無需 Word 開啟。用於產生新報表、模板。

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
# 建立文件 → 加入表格 → 設定格式 → 存檔
doc = Document()
table = doc.add_table(rows=6, cols=8)
table.style = 'Table Grid'
# ... 填入資料、設定字型/底色/欄寬 ...
doc.save('output.docx')
print('OK')
"
```

## 正式報告格式基準 ⚠️ 重要

主人的正式報告（如期中/期末報告書）必須嚴格遵循以下格式，**禁止使用自訂裝飾風格**（如深藍表頭、交替行色等）。

### 格式範本

以 `115年度萬山、寶山、來義等五處大規模崩塌地區監測計畫_工作執行計畫書_期中參考版.docx` 為唯一格式基準。

### 字型規範

| 文字類型 | 字型 | 說明 |
|:--|:--|:--|
| 中文 | **標楷體** | 內文、標題、表頭 |
| 英文/數字 | **Times New Roman** | 含單位、座標、數值 |

> 同一儲存格內中英數字混排時，須在 run 級別分開設定字型，或設定西文字型為 Times New Roman、東亞字型為標楷體。

### 表格屬性

| 屬性 | 值 |
|:--|:--|
| 表頭底色 | `#F2F2F2`（淺灰） |
| 表頭文字 | 黑色、**無粗體** |
| 邊框 | 黑色 4pt 實線（`sz=4, color=000000, val=single`） |
| 垂直對齊 | 置中 |
| 交替行色 | ❌ 不使用 |
| 表格樣式 | `Table Grid` 或 `Normal Table` |

### python-docx 實作要點

```python
# 字型：中文標楷體 + 英數 Times New Roman
run.font.name = 'Times New Roman'  # 西文字型
rPr = run._element.get_or_add_rPr()
rFonts = OxmlElement('w:rFonts')
rFonts.set(qn('w:eastAsia'), '標楷體')  # 東亞字型
rPr.insert(0, rFonts)

# 表頭底色
from docx.oxml.ns import qn
shading = OxmlElement('w:shd')
shading.set(qn('w:fill'), 'F2F2F2')
shading.set(qn('w:val'), 'clear')
cell._tc.get_or_add_tcPr().append(shading)

# 邊框
from docx.oxml import parse_xml
borders = parse_xml(
    f'<w:tcBorders xmlns:w="...">'
    f'<w:top w:val="single" w:sz="4" w:color="000000"/>'
    f'<w:left w:val="single" w:sz="4" w:color="000000"/>'
    f'<w:bottom w:val="single" w:sz="4" w:color="000000"/>'
    f'<w:right w:val="single" w:sz="4" w:color="000000"/>'
    f'</w:tcBorders>'
)
```

### 常見錯誤（禁止）

- ❌ 使用深藍色或彩色表頭
- ❌ 表頭文字加粗體
- ❌ 使用交替行底色
- ❌ 英數字使用標楷體（必須 Times New Roman）
- ❌ 未對標正式報告範本格式

## 注意

- 操作 1、2 需要 Word 已在桌面開啟目標文件
- 操作 3、4 使用 python-docx，無需開啟 Word（**優先使用**）
- 建議先讀取文件結構確認狀態再修改
- 正式報告作業時，務必先分析範本文件格式，再依基準操作
