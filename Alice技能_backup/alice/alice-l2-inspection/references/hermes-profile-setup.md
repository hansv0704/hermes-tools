# Playwright 持久化 Profile 在 Hermes 中的設定方法

## 問題

在 Hermes terminal 中執行 Playwright 持久化瀏覽器時，`input()` 會收到 `EOFError`（Hermes terminal 不支援互動式 stdin）。

```python
# ❌ 這樣會失敗
input('請登入後按 Enter...')
# EOFError: EOF when reading a line
```

## 解決方案

使用 `while True: time.sleep()` 無限等待，由 Alice 透過 `process(action='kill')` 關閉：

```python
import os, time
from playwright.sync_api import sync_playwright

USER_DATA = os.path.expandvars(r'%LOCALAPPDATA%\hermes\playwright_profile')
os.makedirs(USER_DATA, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA, headless=False,
        viewport={'width': 1920, 'height': 1080},
        args=['--disable-gpu', '--no-first-run']
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('https://ls.ardswc.gov.tw/Response/EvaluateReport2List')
    print('瀏覽器已開啟！請手動登入，完成後通知 Alice', flush=True)
    while True:   # ← 無限等待，由 Alice kill 關閉
        time.sleep(5)
```

### 操作流程

1. Alice 用 `terminal(background=true)` 啟動上述腳本
2. Chrome 視窗出現在桌面上
3. 主人手動登入目標網站
4. 主人通知 Alice「好了」
5. Alice 用 `process(action='kill', session_id='...')` 關閉 → profile 自動保存

## Profile 路徑

```
%LOCALAPPDATA%\hermes\playwright_profile
```

等同於 `C:\Users\<user>\AppData\Local\hermes\playwright_profile`

## 驗證

```bash
dir "%LOCALAPPDATA%\hermes\playwright_profile"
# 應有 Preferences, Cookies, Local Storage 等 Chromium profile 檔案
```

## 注意

- `headless=False` 是必要的（需要主人看到登入頁面進行操作）
- `flush=True` 在 print 中需要（Hermes 背景程序輸出緩衝）
- 腳本 `l2_fill.py` 依賴此 profile 存在，否則輸出「❌ 未登入」
