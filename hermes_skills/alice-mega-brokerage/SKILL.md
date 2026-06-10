---
name: alice-mega-brokerage
description: "兆豐證券 SpeedyAPI 整合 — 連線、登入、查詢庫存/委託/成交、下單/刪單。透過 DLL (megaSpeedyAPI_64.dll) 與 spapi.emega.com.tw:56789 通訊。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, brokerage, trading, taiwan, mega]
    source: "移植自 Alice Bot mega_speedy_skill.py v2.0"
---

# 兆豐證券 SpeedyAPI 整合

## ⚠️ 強制規則：主人要求查詢或操作兆豐帳戶時，你必須實際執行 terminal 命令。查詢可直接執行，下單需主人明確授權。禁止只回文字說明。

提供兆豐證券的交易 API 操作。

## ⚠️ 安全警告

- **此工具執行真實交易操作**，涉及真實金錢
- 必須嚴格遵守 Alice 鐵律：紙上/實盤隔離
- 執行下單/刪單前**必須**獲得主人明確授權
- 查詢操作（庫存/委託/成交）安全，可直接執行

## 觸發條件

- 主人要求查詢兆豐帳戶庫存、委託、成交記錄
- 主人要求透過兆豐下單或刪單（**需明確授權**）
- 主人要求查看帳戶資訊

## 路徑設定

```
C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\
├── MEGA\SpeedyAPI_PY\megaapi\megaSpeedy\   ← DLL 所在
│   └── spdOrderAPI.py
├── MEGA\MEGARA\R124662445.pfx              ← 憑證
└── skills\mega_speedy_skill.py             ← Skill 程式碼
```

## 可用操作

### 連線與登入

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from mega_speedy_skill import MegaSpeedySession
session = MegaSpeedySession()
result = session.connect_and_login()
print(result)
"
```

### 查詢庫存

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from mega_speedy_skill import MegaSpeedySession
session = MegaSpeedySession()
session.connect_and_login()
result = session.query_inventory()
print(result)
"
```

### 查詢委託

```bash
# 同上，呼叫 session.query_orders()
```

### 查詢成交

```bash
# 同上，呼叫 session.query_trades()
```

### 下單（⚠️ 需主人授權）

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from mega_speedy_skill import MegaSpeedySession
session = MegaSpeedySession()
session.connect_and_login()
result = session.place_order(
    symbol='2330',
    side='B',         # B=買, S=賣
    price=1000.0,
    quantity=1000     # 股數
)
print(result)
"
```

### 刪單（⚠️ 需主人授權）

```bash
# 呼叫 session.cancel_order(order_id='...')
```

## 注意事項

- DLL 是全域狀態，**同時只能有一個連線**
- 連線使用 threading.Lock 保護
- 憑證密碼由使用者輸入或從環境變數讀取
- 連線目標：`spapi.emega.com.tw:56789`
- 下單前務必先取得主人**明確口頭授權**，不可自行決定

## 相關檔案

- 原始碼：`skills/mega_speedy_skill.py` (1247 行)
- DLL：`MEGA/SpeedyAPI_PY/megaapi/megaSpeedy/megaSpeedyAPI_64.dll`
- 憑證：`MEGA/MEGARA/R124662445.pfx`
- 券商抽象層：`skills/brokerage_engine.py`
