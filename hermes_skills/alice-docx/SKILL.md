---
name: alice-docx
description: "Word 文件自動化工具包 — 讀取文件結構、插入文字、表格重建。合併自 2 個 Alice Word 技能。"
version: 1.0.0
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

## 注意

- 操作 1、2 需要 Word 已在桌面開啟目標文件
- 操作 3 (表格重建) 使用 python-docx，無需開啟 Word
- 建議先執行 word_live_get_structure 確認文件狀態再修改
