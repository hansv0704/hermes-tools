#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
{測站名稱} {年份}年 時雨量＋有效累積雨量 雙軸圖 — Grapher 風格
字體：標楷體 (DFKai-SB)
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

# ═══ 字型：標楷體 ═══
font_path = 'C:/Windows/Fonts/kaiu.ttf'
fm.fontManager.addfont(font_path)
font_name = fm.FontProperties(fname=font_path).get_name()
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# ═══ 讀取資料 ═══
DATA_PATH = r'D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx'
SHEET_NAME = '{SHEET_NAME}'   # e.g. 新庄81V920
YEAR = {YEAR}                  # e.g. 2025

df = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)
df['rTime'] = pd.to_datetime(df['[rTime]'])
df_year = df[df['rTime'].dt.year == YEAR].sort_values('rTime').reset_index(drop=True)

times = df_year['rTime']
hourly_rain = df_year['[OneHour]']     # 時雨量
cum_effective = df_year['[RT]']        # 有效累積雨量

# ═══ 配色 ═══
BLUE_BAR   = '#1A4FCF'
DARK_RED   = '#B91C1C'
GRID_COLOR = '#D0D0D0'

# ═══ 繪圖 ═══
fig, ax1 = plt.subplots(figsize=(22, 8), facecolor='white')
fig.subplots_adjust(left=0.09, right=0.91, top=0.95, bottom=0.11)

# ── 時雨量柱狀（粗體效果：加寬、無邊線）──
ax1.bar(times, hourly_rain, width=0.12, color=BLUE_BAR,
        edgecolor='none', linewidth=0, zorder=3, alpha=0.95)

# 標最大時雨量
max_idx = hourly_rain.idxmax()
max_time, max_val = times.iloc[max_idx], hourly_rain.iloc[max_idx]
ax1.annotate(f'{max_val:.0f} mm', xy=(max_time, max_val),
             xytext=(max_time + pd.Timedelta(hours=60), max_val + 6),
             fontsize=18, fontweight='bold', color=BLUE_BAR,
             arrowprops=dict(arrowstyle='->', color=BLUE_BAR, lw=1.2))

ax1.set_ylabel('時雨量 (mm)', fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax1.set_ylim(0, 100)
ax1.yaxis.set_major_locator(ticker.MultipleLocator(10))
ax1.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)

# ── 有效累積雨量折線 ──
ax2 = ax1.twinx()
ax2.plot(times, cum_effective, color=DARK_RED, linewidth=1.4, zorder=5)

ax2.set_ylabel('有效累積雨量 (mm)', fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax2.set_ylim(0, 1600)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(200))
ax2.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)

# ── X軸 ──
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

# ── 網格（僅水平）──
ax1.grid(axis='y', color=GRID_COLOR, linewidth=0.6, alpha=0.8, zorder=0)
ax1.set_axisbelow(True)

# ── 邊框 ──
for ax_obj in [ax1, ax2]:
    ax_obj.spines['top'].set_visible(False)
    ax_obj.spines['right'].set_visible(False)
    ax_obj.spines['left'].set_color('#AAAAAA')
    ax_obj.spines['left'].set_linewidth(0.8)
    ax_obj.spines['bottom'].set_color('#AAAAAA')
    ax_obj.spines['bottom'].set_linewidth(0.8)

# ── 圖例（FontProperties 確保標楷體粗體正確渲染）──
legend_font = fm.FontProperties(fname=font_path, size=38, weight='bold')
legend_elements = [
    Patch(facecolor=BLUE_BAR, edgecolor='none', label='時雨量'),
    Line2D([0], [0], color=DARK_RED, linewidth=4.0, label='有效累積雨量'),
]
legend = ax1.legend(
    handles=legend_elements, loc='upper right',
    frameon=True, framealpha=1.0, edgecolor='#BBBBBB',
    facecolor='white', prop=legend_font,
    borderpad=1.0, handlelength=2.5, handletextpad=1.0,
)
legend.get_frame().set_linewidth(0.5)

# ═══ 輸出 ═══
OUTPUT_DIR = r'C:\Users\hans\Desktop\charts'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 找下一個版號
import glob
existing = glob.glob(os.path.join(OUTPUT_DIR, f'{SHEET_NAME}_{YEAR}_V*.png'))
next_v = len(existing) + 1

for fmt, ext in [('png', 'png'), ('svg', 'svg')]:
    fpath = os.path.join(OUTPUT_DIR, f'{SHEET_NAME}_{YEAR}_V{next_v}.{ext}')
    fig.savefig(fpath, dpi=200 if ext=='png' else None,
                format=ext, facecolor='white', edgecolor='none',
                bbox_inches='tight', pad_inches=0.3)
    print(f'✅ {fpath}')

plt.close('all')
