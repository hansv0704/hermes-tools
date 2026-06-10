---
name: alice-taiwan-market
description: "台灣股市數據查詢 — TWSE/TPEX 個股歷史、指數、市場總覽、漲幅排行。基於 yfinance + pandas。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, stock, taiwan, finance]
    source: "移植自 Alice Bot taiwan_market_skill.py"
---

# 台灣股市數據查詢

## ⚠️ 強制規則：主人詢問台股時，你必須實際執行 terminal 命令取得數據，再根據真實數據回答。禁止憑記憶或幻覺回答股價。

提供台股上市 (TWSE) 及上櫃 (TPEX) 的股價查詢。

## 觸發條件

- 主人查詢台股個股（如「2330 台積電」「查一下 6180」）
- 主人想看大盤指數（「加權指數多少」「櫃買指數」）
- 主人問市場概況（「今天台股怎樣」）
- 主人問漲幅排行（「今天漲最多的」）

## 可用工具

### 1. 查詢個股歷史 (get_tw_stock_history)

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from taiwan_market_skill import TaiwanMarketSkill
skill = TaiwanMarketSkill()
result = skill.execute('get_tw_stock_history', {
    'symbol': '2330',
    'start': '2026-05-01',
    'end': '2026-06-10',
    'interval': '1d'
}, {})
print(result)
"
```

### 2. 查詢個股基本資訊 (get_tw_stock_info)

```bash
python -c "..." # symbol='2330', market='TWSE' 或 'TPEX'
```

### 3. 查詢指數 (get_tw_index)

```bash
python -c "..." # index='TAIEX'|'TPEX'|'TAIWAN50', period='1mo'|'3mo'|'6mo'|'1y'|'5y'
```

### 4. 市場總覽 (get_tw_market_overview)

```bash
python -c "..." # 無參數，直接呼叫
```

### 5. 漲幅排行 (get_tw_top_movers)

```bash
python -c "..." # top_n=10, move_type='gainers'|'losers'|'volume'
```

### 6. 搜尋股票 (search_tw_stocks)

```bash
python -c "..." # query='台積電' 或 '2330'
```

## 快速指令模板

複製以下模板，替換 `FUNCTION` 和 `ARGS`：

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953" && python -c "
import sys; sys.path.insert(0, 'skills')
from taiwan_market_skill import TaiwanMarketSkill
import json
skill = TaiwanMarketSkill()
result = skill.execute('FUNCTION', ARGS, {})
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

## 代碼格式

- 上市 (TWSE)：`2330.TW`
- 上櫃 (TPEX)：`6180.TWO`
- 加權指數：`^TWII`
- 櫃買指數：`^TWOII`

## 依賴

- `yfinance` — Yahoo Finance 數據
- `pandas` — 數據處理

## 相關檔案

- 原始碼：`skills/taiwan_market_skill.py`
