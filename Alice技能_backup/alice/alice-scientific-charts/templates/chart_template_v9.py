#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
監測圖表模板 — Grapher 風格
V9 定稿：新庄81V920 2025年 時雨量＋有效累積雨量 雙軸圖

可直接修改 SHEET_NAME / YEAR / COL_HOURLY / COL_CUM 套用至其他測站
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
import os

# ═══════════════════════════════════════
#  設定區 — 修改這裡套用其他測站
# ═══════════════════════════════════════
DATA_PATH   = r'D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx'
SHEET_NAME  = '新庄81V920'          # 測站工作表
YEAR        = 2025                   # 年份
COL_HOURLY  = '[OneHour]'           # 時雨量欄位
COL_CUM     = '[RT]'                # 有效累積雨量欄位
OUTPUT_DIR  = r'C:\Users\hans\Desktop\charts'
VERSION     = 1                      # 版號
LABEL_LEFT  = '時雨量 (mm)'          # 左Y軸標籤
LABEL_RIGHT = '有效累積雨量 (mm)'    # 右Y軸標籤
YLEFT_MAX   = 100                    # 左Y軸上限
YLEFT_STEP  = 10                     # 左Y軸刻度間距
YRIGHT_MAX  = 1600                   # 右Y軸上限
YRIGHT_STEP = 200                    # 右Y軸刻度間距
FIG_WIDTH   = 22                     # 圖寬 (英吋)
FIG_HEIGHT  = 8                      # 圖高 (英吋)

# ═══════════════════════════════════════
#  字型
# ═══════════════════════════════════════
FONT_PATH = 'C:/Windows/Fonts/kaiu.ttf'
fm.fontManager.addfont(FONT_PATH)
FONT_NAME = fm.FontProperties(fname=FONT_PATH).get_name()
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [FONT_NAME] + plt.rcParams['font.sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# ═══════════════════════════════════════
#  配色
# ═══════════════════════════════════════
BLUE_BAR = '#2563EB'
DARK_RED = '#B91C1C'

# ═══════════════════════════════════════
#  讀取資料
# ═══════════════════════════════════════
df = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)
df['rTime'] = pd.to_datetime(df['[rTime]'])
df_year = df[df['rTime'].dt.year == YEAR].sort_values('rTime').reset_index(drop=True)

times = df_year['rTime']
hourly_rain = df_year[COL_HOURLY]
cum_effective = df_year[COL_CUM]

print(f"資料: {len(df_year)} 小時 | 時雨量 {hourly_rain.min():.0f}~{hourly_rain.max():.0f} mm | 累積 {cum_effective.min():.0f}~{cum_effective.max():.0f} mm")

# ═══════════════════════════════════════
#  繪圖
# ═══════════════════════════════════════
fig, ax1 = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor='white')
fig.subplots_adjust(left=0.09, right=0.91, top=0.95, bottom=0.11)

# --- 時雨量柱狀 ---
ax1.bar(times, hourly_rain, width=0.08, color=BLUE_BAR,
        edgecolor='#1D4ED8', linewidth=0.25, zorder=3)

ax1.set_ylabel(LABEL_LEFT, fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax1.set_ylim(0, YLEFT_MAX)
ax1.yaxis.set_major_locator(ticker.MultipleLocator(YLEFT_STEP))
ax1.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)

# --- 有效累積雨量折線 ---
ax2 = ax1.twinx()
ax2.plot(times, cum_effective, color=DARK_RED, linewidth=1.4, zorder=5)

ax2.set_ylabel(LABEL_RIGHT, fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax2.set_ylim(0, YRIGHT_MAX)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(YRIGHT_STEP))
ax2.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)

# --- X軸 ---
ax1.set_xlim(pd.Timestamp(f'{YEAR}-01-01'), pd.Timestamp(f'{YEAR}-11-20'))
major_ticks = pd.date_range(f'{YEAR}-01-01', f'{YEAR}-11-01', freq='2MS')
ax1.set_xticks(major_ticks)
ax1.set_xticklabels(
    [d.strftime('%m/%d/%y') for d in major_ticks],
    fontsize=15, fontweight='bold', color='#000000'
)
minor_ticks = pd.date_range(f'{YEAR}-01-01', f'{YEAR}-11-01', freq='MS')
ax1.set_xticks(minor_ticks, minor=True)
ax1.tick_params(axis='x', which='minor', length=4, color='#CCCCCC', width=0.6)

# --- 邊框：四邊全留，黑色 ---
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

# --- 圖例 ---
legend_font = fm.FontProperties(fname=FONT_PATH, size=20, weight='bold')
legend_elements = [
    Patch(facecolor=BLUE_BAR, edgecolor='none', label=LABEL_LEFT),
    Line2D([0], [0], color=DARK_RED, linewidth=4.0, label=LABEL_RIGHT),
]
legend = ax1.legend(
    handles=legend_elements, loc='upper right',
    frameon=True, framealpha=1.0, edgecolor='#000000',
    facecolor='white', prop=legend_font,
    borderpad=0.6, handlelength=2.0, handletextpad=0.6,
)
legend.get_frame().set_linewidth(0.8)

# ═══════════════════════════════════════
#  輸出
# ═══════════════════════════════════════
os.makedirs(OUTPUT_DIR, exist_ok=True)

for fmt, ext in [('png', 'png'), ('svg', 'svg')]:
    fpath = os.path.join(OUTPUT_DIR, f'{SHEET_NAME}_{YEAR}_V{VERSION}.{ext}')
    fig.savefig(fpath, dpi=200 if ext == 'png' else None,
                format=ext, facecolor='white', edgecolor='none',
                bbox_inches='tight', pad_inches=0.3)
    print(f'✅ {fpath}')

plt.close('all')
print('\n完成！')
