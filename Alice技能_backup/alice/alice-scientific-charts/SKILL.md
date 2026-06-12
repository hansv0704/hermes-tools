---
name: alice-scientific-charts
description: "大崩報告雨量圖標準模板 — Grapher 等級雙Y軸混合圖（時雨量bar + 有效累積雨量line）。標楷體純黑粗體、四邊黑框無網格、右上圖例。"
version: 1.0.0
category: alice
---

# 大崩報告雨量圖標準模板 (V9 定稿)

## ⚠️ 強制規則

1. **繪圖前先用 Gemini Flash 分析參考圖**，確認目標規格再動手
2. **核心欄位**：時雨量 = `[OneHour]`（柱狀），有效累積雨量 = `[RT]`（折線）
3. **唯一變動**：X軸範圍、Y軸上限依各測站資料特性調整；其餘設定**不變**
4. **輸出帶版號**：`{測站}_2025_V{N}.png`，舊版不覆蓋方便比對
5. **腳本放 charts/**，不要丟桌面

## 標準設定（不可變動）

### 字型
```python
font_path = 'C:/Windows/Fonts/kaiu.ttf'
fm.fontManager.addfont(font_path)
font_name = fm.FontProperties(fname=font_path).get_name()
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
```

### 配色
```python
BLUE_BAR   = '#2563EB'   # 時雨量柱狀
DARK_RED   = '#B91C1C'   # 有效累積雨量折線
```

### 畫布
```python
fig, ax1 = plt.subplots(figsize=(22, 8), facecolor='white')
fig.subplots_adjust(left=0.09, right=0.91, top=0.95, bottom=0.11)
```

### 時雨量柱狀（左軸）
```python
ax1.bar(times, hourly_rain, width=0.08, color=BLUE_BAR,
        edgecolor='#1D4ED8', linewidth=0.25, zorder=3)

ax1.set_ylabel('時雨量 (mm)', fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax1.set_ylim(0, <依資料>)
ax1.yaxis.set_major_locator(ticker.MultipleLocator(<依資料>))
ax1.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)
```

### 有效累積雨量折線（右軸）
```python
ax2 = ax1.twinx()
ax2.plot(times, cum_effective, color=DARK_RED, linewidth=1.4, zorder=5)

ax2.set_ylabel('有效累積雨量 (mm)', fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax2.set_ylim(0, <依資料>)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(<依資料>))
ax2.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)
```

### X軸
```python
ax1.set_xlim(pd.Timestamp('<起始>'), pd.Timestamp('<結束>'))
major_ticks = pd.date_range('<起始>', '<結束-月>', freq='2MS')
ax1.set_xticks(major_ticks)
ax1.set_xticklabels(
    [d.strftime('%m/%d/%y') for d in major_ticks],
    fontsize=15, fontweight='bold', color='#000000'
)
```

### 邊框（四邊全留，純黑，無內部網格）
```python
for spine_name in ['left', 'bottom', 'top']:
    ax1.spines[spine_name].set_visible(True)
    ax1.spines[spine_name].set_color('#000000')
    ax1.spines[spine_name].set_linewidth(0.8)
ax1.spines['right'].set_visible(False)

for spine_name in ['right', 'top']:
    ax2.spines[spine_name].set_visible(True)
    ax2.spines[spine_name].set_color('#000000')
    ax2.spines[spine_name].set_linewidth(0.8)
ax2.spines['left'].set_visible(False)
ax2.spines['bottom'].set_visible(False)
# 不呼叫 ax1.grid() — 無內部網格
```

### 圖例（右上角，標楷體 20pt 粗體，黑框）
```python
legend_font = fm.FontProperties(fname=font_path, size=20, weight='bold')
legend_elements = [
    Patch(facecolor=BLUE_BAR, edgecolor='none', label='時雨量'),
    Line2D([0], [0], color=DARK_RED, linewidth=4.0, label='有效累積雨量'),
]
legend = ax1.legend(
    handles=legend_elements, loc='upper right',
    frameon=True, framealpha=1.0, edgecolor='#000000',
    facecolor='white', prop=legend_font,
    borderpad=0.6, handlelength=2.0, handletextpad=0.6,
)
legend.get_frame().set_linewidth(0.8)
```

### 輸出
```python
output_dir = r'C:\Users\hans\Desktop\charts'
for fmt, ext in [('png', 'png'), ('svg', 'svg')]:
    fpath = os.path.join(output_dir, f'{測站名}_{年份}_V{版號}.{ext}')
    fig.savefig(fpath, dpi=200 if ext=='png' else None,
                format=ext, facecolor='white', edgecolor='none',
                bbox_inches='tight', pad_inches=0.3)
```

## 測站工作表對照

| 測站 | Excel 工作表 | 資料欄位 |
|------|-------------|---------|
| 新庄 81V920 | `新庄81V920` | [OneHour], [RT] |
| 新發國小 81V840 | `新發國小81V840` | [OneHour], [RT] |
| 寶山部落 81V940 | `寶山部落81V940` | [OneHour], [RT] |
| 來義 88R460 | `來義88R460` | [OneHour], [RT] |
| 萬山 C0V790 | `萬山C0V790` | [OneHour], [RT] |

資料路徑：`D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx`

## ⚠️ 教訓

- 圖例字體大小用 `FontProperties(size=N)` 直接指定，`fontsize` + `prop` dict 組合會失效
- `fill_between` 在密集時序資料中反而比 `bar` 更細，不要用
- 右Y軸用黑色不是深紅色（主人偏好）
- Gemini Flash 先用來看圖，不要憑空猜規格
