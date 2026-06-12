#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
降雨日雨量分布圖 — Grapher 風格模板
用法：修改底部的 INPUT_PATH、SHEET_NAME、OUTPUT_NAME、YEAR 即可

產出：PNG (200 DPI) + SVG 向量圖 → C:\Users\hans\Desktop\charts\
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import os, sys

# ══════════════════════════════════════════════
# 設定區 — 修改這裡
# ══════════════════════════════════════════════
INPUT_PATH  = r'D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx'
SHEET_NAME  = '新庄81V920'        # Excel 工作表名稱
TIME_COL    = '[rTime]'           # 時間欄位名稱
RAIN_COL    = '[OneHour]'         # 雨量欄位（逐時）
YEAR        = 2025                # 篩選年份
STATION_ID  = '新庄81V920'        # 測站代碼（圖表標題用）
OUTPUT_NAME = '新庄81V920_2025_日雨量'  # 輸出檔名（不含副檔名）

# ══════════════════════════════════════════════
# 字型設定
# ══════════════════════════════════════════════
FONT_PATH = 'C:/Windows/Fonts/NotoSansTC-VF.ttf'
fm.fontManager.addfont(FONT_PATH)
prop = fm.FontProperties(fname=FONT_PATH)
plt.rcParams['font.family'] = prop.get_name()
plt.rcParams['axes.unicode_minus'] = False

# ══════════════════════════════════════════════
# 讀取與處理
# ══════════════════════════════════════════════
df = pd.read_excel(INPUT_PATH, sheet_name=SHEET_NAME)
df['rTime'] = pd.to_datetime(df[TIME_COL])
df_year = df[(df['rTime'].dt.year == YEAR) & (df[RAIN_COL] >= 0)].copy()
df_year['date'] = df_year['rTime'].dt.date

daily = df_year.groupby('date').agg(
    daily_rain=(RAIN_COL, 'sum'),
).reset_index()
daily['date'] = pd.to_datetime(daily['date'])
daily = daily.sort_values('date').reset_index(drop=True)
daily['cum_rain'] = daily['daily_rain'].cumsum()

# ══════════════════════════════════════════════
# 繪圖
# ══════════════════════════════════════════════
BLUE_BAR   = '#1A5FDC'
RED_LINE   = '#DC267F'
GRID_COLOR = '#D9D9D9'
BG_COLOR   = '#FFFFFF'

fig, ax1 = plt.subplots(figsize=(18, 8), facecolor=BG_COLOR)
fig.subplots_adjust(left=0.07, right=0.93, top=0.92, bottom=0.1)

# 日雨量柱狀
ax1.bar(daily['date'], daily['daily_rain'], width=0.9,
        color=BLUE_BAR, edgecolor='white', linewidth=0.1, alpha=0.95)

# 右軸：累積雨量
ax2 = ax1.twinx()
ax2.plot(daily['date'], daily['cum_rain'], color=RED_LINE, linewidth=1.5, alpha=0.9, zorder=10)
ax2.fill_between(daily['date'], 0, daily['cum_rain'], color=RED_LINE, alpha=0.08)

# 軸標籤
ax1.set_ylabel('日雨量 (mm)', fontsize=12, fontweight='bold', color='#333333')
ax2.set_ylabel('累積雨量 (mm)', fontsize=12, fontweight='bold', color=RED_LINE)

# 標題
fig.suptitle(f'{STATION_ID}  {YEAR} 年日雨量分布圖',
             fontsize=16, fontweight='bold', y=0.98, color='#1A1A1A')

# X軸：月份刻度
start = pd.Timestamp(f'{YEAR}-01-01')
end   = daily['date'].max()
ax1.set_xlim(start, end)
month_starts = pd.date_range(start, end, freq='MS')
ax1.set_xticks(month_starts)
ax1.set_xticklabels([f'{d.month}月' for d in month_starts],
                    fontsize=10, color='#555555')

# 次要刻度（每週一）
mondays = pd.date_range(start, end, freq='W-MON')
ax1.set_xticks(mondays, minor=True)
ax1.tick_params(axis='x', which='minor', length=4, color='#CCCCCC', width=0.5)

# Y軸格式化
ax1.yaxis.set_major_locator(ticker.MaxNLocator(10))
ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
ax1.tick_params(axis='y', labelsize=10, colors='#555555')

ax2.yaxis.set_major_locator(ticker.MaxNLocator(8))
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
ax2.tick_params(axis='y', labelsize=10, colors=RED_LINE)

# 網格
ax1.grid(axis='y', color=GRID_COLOR, linewidth=0.5, alpha=0.7)
ax1.grid(axis='x', which='major', color=GRID_COLOR, linewidth=0.3, alpha=0.4)
ax1.set_axisbelow(True)

# 圖例
legend_elements = [
    Patch(facecolor=BLUE_BAR, edgecolor='white', linewidth=0.3, label='日雨量'),
    Line2D([0], [0], color=RED_LINE, linewidth=1.8, label='累積雨量'),
]
ax1.legend(handles=legend_elements, loc='upper left', frameon=True,
           framealpha=0.95, edgecolor='#DDDDDD', fontsize=10, facecolor='white')

# 邊框
for ax_obj in [ax1, ax2]:
    for spine in ax_obj.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color('#BBBBBB')
    ax_obj.spines['top'].set_visible(False)

# 標註最大日雨量
max_idx = daily['daily_rain'].idxmax()
max_date = daily.loc[max_idx, 'date']
max_val  = daily.loc[max_idx, 'daily_rain']
ax1.annotate(
    f'{max_val:.0f} mm\n{max_date.strftime("%m/%d")}',
    xy=(max_date, max_val),
    xytext=(max_date + pd.Timedelta(days=5), max_val + 15),
    fontsize=9, fontweight='bold', color=BLUE_BAR,
    arrowprops=dict(arrowstyle='->', color=BLUE_BAR, lw=1.2,
                    connectionstyle='arc3,rad=0.2'),
    bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
              edgecolor=BLUE_BAR, alpha=0.9)
)

# ══════════════════════════════════════════════
# 輸出
# ══════════════════════════════════════════════
output_dir = r'C:\Users\hans\Desktop\charts'
os.makedirs(output_dir, exist_ok=True)

png_path = os.path.join(output_dir, f'{OUTPUT_NAME}.png')
svg_path = os.path.join(output_dir, f'{OUTPUT_NAME}.svg')

fig.savefig(png_path, dpi=200, facecolor=BG_COLOR, edgecolor='none',
            bbox_inches='tight', pad_inches=0.3)
fig.savefig(svg_path, format='svg', facecolor=BG_COLOR, edgecolor='none',
            bbox_inches='tight', pad_inches=0.3)

print(f'✅ PNG: {png_path}')
print(f'✅ SVG: {svg_path}')
print(f'資料: {len(daily)} 天, 最大日雨量 {max_val:.1f} mm, 累積 {daily["cum_rain"].max():.1f} mm')
plt.close('all')
