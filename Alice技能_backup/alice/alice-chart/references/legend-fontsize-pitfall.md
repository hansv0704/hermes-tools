# 圖例字級陷阱

## 問題

使用 `ax1.legend(fontsize=30, ...)` 設定圖例字體大小時，
在標楷體（DFKai-SB）下，`fontsize` 參數**不一定生效**。
即使從 22pt 一路改到 30pt，圖例文字大小仍無明顯變化。

## 根因

Matplotlib 的 legend 在同時使用 `fontsize` 和 `prop` 參數時，
`prop` dict 可能覆蓋 `fontsize`。
此外，部分後端對標楷體這類傳統 TrueType 字型的字級處理可能存在相容性問題。

## 解決方案

**使用 `FontProperties` 直接指定字型物件**，避開參數衝突：

```python
import matplotlib.font_manager as fm

# ✅ 正確：FontProperties 直接綁定字型大小
legend_font = fm.FontProperties(fname='C:/Windows/Fonts/kaiu.ttf', size=38, weight='bold')
legend = ax1.legend(handles=..., prop=legend_font, ...)

# ❌ 錯誤：fontsize 可能不生效
legend = ax1.legend(handles=..., fontsize=38, prop={'weight': 'bold'}, ...)
```

## 驗證方式

不同版號（V5→V6→V7）之間，圖例文字必須有肉眼可見的大小差異。
若連續兩版圖例看起來一樣大，代表 fontsize 參數未被正確應用。
