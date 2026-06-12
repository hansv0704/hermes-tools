# 參考圖像素逆向分析

當主人提供參考圖表截圖，但 OCR（Tesseract）未安裝或圖片分析失敗時，
可以用 PIL + numpy 直接分析像素來推斷圖表佈局。

## 適用場景

1. 參考圖是截圖（PNG），無法用 vision_analyze 讀取
2. 需要自動推斷圖表類型（柱狀/折線/散布）和主要顏色
3. Tesseract 未安裝（Windows 預設無）

## 核心技巧

### 1. 找圖表主色區域

```python
from PIL import Image
import numpy as np

img = Image.open(ref_path)
arr = np.array(img)  # shape: (H, W, 4) for RGBA PNG

# 條件遮罩 — 藍色柱狀圖範例
blue_mask = (arr[:,:,0] < 50) & (arr[:,:,1] < 100) & (arr[:,:,2] > 200) & (arr[:,:,3] == 255)
blue_rows, blue_cols = np.where(blue_mask)
print(f'Chart area: row [{blue_rows.min()}, {blue_rows.max()}], col [{blue_cols.min()}, {blue_cols.max()}]')
```

### 2. 密度熱力圖推斷資料分佈

```python
grid_h, grid_w = 20, 40  # 格數
cell_h = height // grid_h
cell_w = width // grid_w

for gy in range(grid_h):
    row_str = ''
    for gx in range(grid_w):
        y1, y2 = gy * cell_h, min((gy+1) * cell_h, height)
        x1, x2 = gx * cell_w, min((gx+1) * cell_w, width)
        density = blue_mask[y1:y2, x1:x2].sum()
        row_str += ' ' if density==0 else '.' if density<10 else '+' if density<50 else '*' if density<200 else '#'
    # 縱向 cluster 代表柱狀圖月份，橫向 density 變化代表數值大小
```

### 3. 判斷圖表類型

- **柱狀圖**：彩色像素形成垂直條帶、有規律間隔、集中在圖表下半部
- **折線圖**：彩色像素沿水平方向呈細線狀分佈
- **散布圖**：彩色點分散無規律、無連續區塊
- **全灰階**：只有黑色文字/線條（純文字表格或線圖）

### 4. 擷取主要顏色

```python
colored_mask = (arr[:,:,0] != arr[:,:,1]) | (arr[:,:,1] != arr[:,:,2])
colored_pixels = arr[colored_mask & (arr[:,:,3]==255)]
unique_colors = np.unique(colored_pixels[:, :3], axis=0)
# 排序找出主色
```

## 已知限制

- 解析度太低（< 400px 寬）時 cluster 辨識困難
- 若圖表使用半透明疊加，白色背景會混入主色
- 全灰階圖表無法區分不同資料序列
- 此為 fallback，非首選方案。優先使用 vision_analyze 或 Tesseract OCR
