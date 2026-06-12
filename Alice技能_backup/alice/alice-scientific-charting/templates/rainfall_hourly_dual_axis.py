#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐時雨量雙軸圖 — 監測報告標準模板（Grapher 風格）
左軸：時雨量柱狀 ([OneHour])，右軸：有效累積雨量折線 ([RT])
字型：標楷體 DFKai-SB（粗體，純黑）
產出：PNG (200 DPI) + SVG → C:\Users\hans\Desktop\charts\

用法：修改底部的 INPUT_PATH、SHEET_NAME、YEAR、STATION_ID、OUTPUT_NAME
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

# ══════════════════════════════════════════════
# 設定區
# ══════════════════════════════════════════════
INPUT_PATH  = r'D:\萬山、寶山、來義等五處大規模崩塌地區監測計畫\監測資料\自動化監測\雨量資料.xlsx'
SHEET_NAME  = '新庄81V920'
YEAR        = 2025
STATION_ID  = '新庄81V920'
OUTPUT_NAME = '新庄81V920_2025_時雨量_有效累積'

# ══════════════════════════════════════════════
# 字型：標楷體 DFKai-SB（強制，主人否決 Noto Sans TC）
# ══════════════════════════════════════════════
FONT_PATH = 'C:/Windows/Fonts/kaiu.ttf'
fm.fontManager.addfont(FONT_PATH)
font_name = fm.FontProperties(fname=FONT_PATH).get_name()  # 'DFKai-SB'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# ══════════════════════════════════════════════
# 讀取資料
# ══════════════════════════════════════════════
df = pd.read_excel(INPUT_PATH, sheet_name=SHEET_NAME)
df['rTime'] = pd.to_datetime(df['[rTime]'])
df_year = df[df['rTime'].dt.year == YEAR].sort_values('rTime').reset_index(drop=True)

times         = df_year['rTime']
hourly_rain   = df_year['[OneHour]']   # 時雨量 → 藍色柱狀
cum_effective = df_year['[RT]']        # 有效累積雨量 → 深紅折線

print(f'資料: {len(df_year)} 小時 | 時雨量 {hourly_rain.min():.0f}~{hourly_rain.max():.0f} mm'
      f' | 累積 {cum_effective.min():.0f}~{cum_effective.max():.0f} mm')

# ══════════════════════════════════════════════
# 配色（Grapher 風格 / 標楷體純黑粗體）
# ══════════════════════════════════════════════
BLUE_BAR   = '#2563EB'     # 時雨量柱狀
DARK_RED   = '#B91C1C'     # 有效累積折線
GRID_COLOR = '#D0D0D0'     # 水平網格

# ══════════════════════════════════════════════
# 繪圖
# ══════════════════════════════════════════════
fig, ax1 = plt.subplots(figsize=(22, 8), facecolor='white')
fig.subplots_adjust(left=0.09, right=0.91, top=0.95, bottom=0.11)

# ── 左軸：時雨量柱狀（粗邊線確保可見） ──
ax1.bar(times, hourly_rain, width=0.08, color=BLUE_BAR,
        edgecolor='#1D4ED8', linewidth=0.55, zorder=3)

# 標最大時雨量
max_idx = hourly_rain.idxmax()
max_time, max_val = times.iloc[max_idx], hourly_rain.iloc[max_idx]
ax1.annotate(f'{max_val:.0f} mm', xy=(max_time, max_val),
             xytext=(max_time + pd.Timedelta(hours=60), max_val + 6),
             fontsize=18, fontweight='bold', color='#1D4ED8',
             arrowprops=dict(arrowstyle='->', color='#1D4ED8', lw=1.2))

ax1.set_ylabel('時雨量 (mm)', fontsize=20, fontweight='bold', color='#000000', labelpad=8)
ax1.set_ylim(0, 100)
ax1.yaxis.set_major_locator(ticker.MultipleLocator(10))
ax1.tick_params(axis='y', labelsize=15, colors='#000000', width=0.8)

# ── 右軸：有效累積雨量折線 ──
ax2 = ax1.twinx()
ax2.plot(times, cum_effective, color=DARK_RED, linewidth=1.4, zorder=5)

ax2.set_ylabel('有效累積雨量 (mm)', fontsize=20, fontweight='bold', color=DARK_RED, labelpad=8)
ax2.set_ylim(0, 1600)
ax2.yaxis.set_major_locator(ticker.MultipleLocator(200))
ax2.tick_params(axis='y', labelsize=15, colors=DARK_RED, width=0.8)

# ── X軸：MM/DD/YY 雙月主刻度 ──
start = pd.Timestamp(f'{YEAR}-01-01')
end   = times.max()
ax1.set_xlim(start, end + pd.Timedelta(days=5))

major_ticks = pd.date_range(start, end, freq='2MS')
ax1.set_xticks(major_ticks)
ax1.set_xticklabels([d.strftime('%m/%d/%y') for d in major_ticks],
                    fontsize=15, fontweight='bold', color='#000000')

minor_ticks = pd.date_range(start, end, freq='MS')
ax1.set_xticks(minor_ticks, minor=True)
ax1.tick_params(axis='x', which='minor', length=4, color='#CCCCCC', width=0.6)

# ── 網格：僅水平 ──
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

# ── 圖例：右上角，大字粗體純黑 ──
legend_elements = [
    Patch(facecolor=BLUE_BAR, edgecolor='#1D4ED8', linewidth=0.4, label='時雨量'),
    Line2D([0], [0], color=DARK_RED, linewidth=2.5, label='有效累積雨量'),
]
legend = ax1.legend(
    handles=legend_elements, loc='upper right',
    frameon=True, framealpha=1.0, edgecolor='#BBBBBB',
    fontsize=22, facecolor='white',
    borderpad=0.9, handlelength=2.2, handletextpad=0.9,
    labelcolor='#000000', prop={'weight': 'bold'}
)
legend.get_frame().set_linewidth(0.5)

# ══════════════════════════════════════════════
# 輸出
# ══════════════════════════════════════════════
output_dir = r'C:\Users\hans\Desktop\charts'
os.makedirs(output_dir, exist_ok=True)

for fmt, ext in [('png', 'png'), ('svg', 'svg')]:
    fpath = os.path.join(output_dir, f'{OUTPUT_NAME}.{ext}')
    fig.savefig(fpath, dpi=200 if ext == 'png' else None,
                format=ext, facecolor='white', edgecolor='none',
                bbox_inches='tight', pad_inches=0.3)
    print(f'✅ {fpath}')

print(f'{YEAR}年 最大時雨量 {max_val:.0f} mm, 有效累積 {cum_effective.max():.0f} mm')
plt.close('all')
