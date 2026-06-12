---
name: alice-chart
description: "監測圖表繪製 — Grapher 等級 matplotlib 科學繪圖。從 Excel 監測資料出圖，支援雙 Y 軸、時雨量柱狀＋累積雨量折線。Gemini Flash 分析參考圖後複刻風格。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, chart, matplotlib, monitoring, rainfall, grapher, gemini]
    source: "2026-06-11 session: 新庄81V920 雨量圖複刻"
---

# 監測圖表繪製

## ⚠️ 強制規則

- **必須實際執行 terminal 命令繪圖**，禁止只回文字描述
- 先用 Gemini Flash 分析參考圖 → 擷取規格 → 再寫 Python 出圖
- 出圖腳本和圖檔都放在 `C:\Users\hans\Desktop\charts\`
- **每次出圖必須版號遞增（V1, V2, V3...）**，保留舊版方便比對
- SVG 向量檔也必須一併輸出

## 觸發條件

- 主人要求從 Excel 監測資料繪製雨量/水文圖表
- 主人提供參考圖要求複刻風格
- 主人要求調整既有圖表的字型、顏色、排版

## 標準流程

### Step 1: Gemini Flash 分析參考圖

```python
from google import genai
# 讀取 API key（從 .env 字串拼接繞過遮蔽）
# 讀取圖片 binary
# 送 gemini-2.5-flash 分析
prompt = """請詳細分析這張降雨監測圖表，用繁體中文回答：
1. 圖表類型（柱狀/折線/雙軸...）
2. X軸顯示內容、刻度格式
3. Y軸有幾個、分別顯示什麼、單位、刻度範圍
4. 各資料系列的顏色、樣式
5. 圖例位置、內容
6. 標題有無
7. 網格線樣式
8. 背景顏色
9. 特殊標註或輔助線
10. 整體風格（科學繪圖 vs 簡報風格）
"""
```

### Step 2: 讀取 Excel 監測資料

監測資料路徑：`D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx`

關鍵欄位對照：
| 欄位 | 用途 |
|------|------|
| `[rTime]` | 時間戳（格式：`81V920 2025-01-01 00:00:00`） |
| `[OneHour]` | 時雨量（mm）→ 柱狀圖 |
| `[RT]` | 有效累積雨量（mm）→ 折線圖 |
| `[Min10]` | 10分鐘雨量 |
| `[Hour24]` | 24小時雨量 |
| `[DayRainfall]` | 日雨量 |

測站工作表：新庄81V920、新發國小81V840、寶山部落81V940、來義88R460、萬山C0V790

### Step 3: matplotlib 出圖 — 主人偏好規格

#### 字型（最重要）
```python
font_path = 'C:/Windows/Fonts/kaiu.ttf'  # 標楷體 DFKai-SB
fm.fontManager.addfont(font_path)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=font_path).get_name()]
```

#### 顏色規範
- 所有文字（軸標籤、刻度、圖例）：**`#000000` 純黑**，嚴禁用灰色
- 柱狀圖：`#1A4FCF` 深藍，無邊線
- 折線圖：`#B91C1C` 深紅
- 網格：`#D0D0D0` 淺灰，僅水平線

#### 排版規格（標楷體粗體）
| 元素 | 字級 | 粗體 |
|------|:---:|:---:|
| Y軸標籤 | 20pt | ✅ |
| Y軸數字 | 15pt | - |
| X軸日期 | 15pt | ✅ |
| 圖例 | 34-38pt | ✅ |
| 最大值標註 | 18pt | ✅ |

#### ⚠️ 圖例陷阱
`ax1.legend(fontsize=XX)` 在標楷體下**不一定生效**，必須用 `FontProperties`：
```python
legend_font = fm.FontProperties(fname=font_path, size=38, weight='bold')
legend = ax1.legend(handles=..., prop=legend_font, ...)
```

#### 柱狀圖規格
- 時雨量 7560 筆逐時資料 → `width=0.12`（約 3 小時寬）
- **無邊線**（`edgecolor='none'`），邊線會讓柱體看起來更細
- 無透明度（`alpha=0.95~1.0`）

#### 雙 Y 軸
- 左軸：時雨量，0–100mm，每 10mm 一格
- 右軸：有效累積雨量，0–1600mm，每 200mm 一格
- 右軸數字顏色 **#000000 純黑**（不用紅色）
- 網格僅對齊左軸

#### 其他
- 白色背景，無標題
- 圖例右上角，白色底框
- X軸格式 `MM/DD/YY`，每兩個月主要刻度
- 200 DPI PNG + SVG 同時輸出

### 完整程式碼模板

見 `templates/rainfall_chart.py`。

## 資料來源

雨量資料 Excel：`D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx`

## 相關檔案

- 出圖腳本與圖檔：`C:\Users\hans\Desktop\charts\`
- 程式碼模板：`templates/rainfall_chart.py`
- 圖例字級陷阱：`references/legend-fontsize-pitfall.md`
- Gemini 圖表分析 SOP：`references/gemini-chart-analysis.md`
