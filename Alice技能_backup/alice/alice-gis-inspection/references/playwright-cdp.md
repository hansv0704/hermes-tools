# Playwright CDP 瀏覽器操控

## 啟動（背景模式）

```bash
python -c "
from playwright.sync_api import sync_playwright
import os, time
user_data = os.path.expandvars(r'%LOCALAPPDATA%\hermes\playwright_profile')
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=user_data, headless=False,
        args=['--remote-debugging-port=9222']
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto('TARGET_URL', wait_until='networkidle')
    # ... DOM 操作 ...
    time.sleep(300)  # 保持開啟
" &
```

## 常用操作

```python
# 填表單
page.fill('input[type=text]', 'value')
page.fill('input[type=password]', 'password')

# 點擊
page.click('text=回報')
page.click('button:has-text("送出")')

# 找元素
links = page.query_selector_all('a')
btn = page.query_selector('a:has-text("回報")')

# Radio button (用 label 文字)
page.click('label:has-text("正常")')

# 截圖
page.screenshot(path='screenshot.png')
```

## 注意

- 首次使用需登入（session 會持久化到 playwright_profile）
- Playwright Chromium 與使用者 Chrome 獨立，不衝突
- DOM 操控比 pyautogui 座標點擊可靠 100 倍
- 不依賴視窗焦點，背景也能操作
