"""
L2 巡檢表自動填寫 v1.0
使用 Playwright DOM 操控，精準點擊 radio button
用法：
  python l2_fill.py           → 填寫第一筆（不送出）
  python l2_fill.py --submit  → 填寫並送出
  python l2_fill.py --verify  → 驗證上次填寫結果
"""
import os, sys, time
from playwright.sync_api import sync_playwright

USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\hermes\playwright_profile")
L2_LIST = "https://ls.ardswc.gov.tw/Response/EvaluateReport2List"
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def fill_form(submit=False):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA, headless=False,
            viewport={"width": 1920, "height": 1080}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 1. 到列表頁
        page.goto(L2_LIST, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # 2. 取得第一筆回報的 ReportID
        btn = page.locator('a:has-text("回報")').first
        if btn.count() == 0:
            print("❌ 找不到回報按鈕")
            return False

        href = btn.get_attribute("href")
        report_id = href.split("ReportID=")[-1] if "ReportID=" in href else "?"
        print(f"📋 ReportID: {report_id}")

        # 3. 開表單
        page.goto(f"https://ls.ardswc.gov.tw{href}", wait_until="networkidle")
        page.wait_for_timeout(2000)

        # 4. 勾選
        page.get_by_label("正常").first.click()
        print("  ✅ 1. 正常")
        page.get_by_label("無").first.click()
        print("  ✅ 2. 無")
        page.get_by_label("儀器設備正常，現地監測值達注意：加強守視。").click()
        print("  ✅ 3. 儀器設備正常")

        # 5. 送出
        if submit:
            try:
                page.locator('button:has-text("建立"), input[type=submit][value*=建立]').first.click()
                page.wait_for_timeout(2000)
                print("  📤 已送出")
            except:
                print("  ⚠️ 找不到建立按鈕")

        # 6. 截圖
        ts = time.strftime("%Y%m%d_%H%M%S")
        ss_path = os.path.join(SCREENSHOT_DIR, f"l2_{report_id}_{ts}.png")
        page.screenshot(path=ss_path)
        print(f"📸 {ss_path}")
        return True

def verify_last():
    """用 Gemini 驗證最新截圖"""
    import base64
    from google import genai

    # 找最新截圖
    pngs = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.startswith("l2_") and f.endswith(".png")])
    if not pngs:
        print("❌ 無截圖")
        return
    path = os.path.join(SCREENSHOT_DIR, pngs[-1])
    print(f"驗證: {pngs[-1]}")

    # 讀 key
    key = ""
    for ep in [os.path.expandvars(r"%LOCALAPPDATA%\hermes\.env")]:
        try:
            for line in open(ep, encoding="utf-8"):
                if "GOOGLE" in line and "API_KEYS" in line:
                    key = line.split("=", 1)[1].strip().split(",")[0].strip('"\'').strip()
                    break
        except: pass
        if key: break

    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    client = genai.Client(api_key=key)
    r = client.models.generate_content(model="gemini-2.5-flash", contents=[
        "檢查L2表單三個選項是否已勾選：正常、無、儀器設備正常。只回答已勾選或未勾選",
        {"inline_data": {"mime_type": "image/png", "data": img}}
    ])
    print(f"結果: {r.text}")

if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify_last()
    else:
        submit = "--submit" in sys.argv
        fill_form(submit)
