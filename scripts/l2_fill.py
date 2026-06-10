"""
L2 巡檢表自動填寫 v1.1 — 實戰驗證版
Playwright DOM 操控，精準點擊，自動滾動送出

用法：
  python l2_fill.py              → 填寫前兩筆未填表單並送出
  python l2_fill.py 3            → 填寫前三筆
  python l2_fill.py --dry-run    → 只填不送出
"""
import os, sys, time
from playwright.sync_api import sync_playwright

USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\hermes\playwright_profile")
L2_BASE = "https://ls.ardswc.gov.tw"
L2_LIST = f"{L2_BASE}/Response/EvaluateReport2List"

def fill_reports(count=2, submit=True):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA, headless=False,
            viewport={"width": 1920, "height": 1080},
            args=["--disable-gpu", "--no-first-run"]
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 1. 列表頁
        page.goto(L2_LIST, wait_until="networkidle")
        page.wait_for_timeout(2000)
        if "Login" in page.url:
            print("❌ 未登入"); return

        # 2. 收集 ReportID
        btns = page.locator('a:has-text("回報")')
        report_ids = []
        for i in range(min(btns.count(), 10)):
            href = btns.nth(i).get_attribute("href")
            if href and "ReportID=" in href:
                report_ids.append(href.split("ReportID=")[-1].split("&")[0])

        target = report_ids[:count]
        print(f"📋 預計填寫 {len(target)} 筆: {target}")

        done = 0
        for rid in target:
            print(f"\n--- ReportID={rid} ---")
            page.goto(f"{L2_BASE}/Response/CreateEvaluateReport2?ReportID={rid}",
                      wait_until="networkidle")
            page.wait_for_timeout(2000)

            # 檢查是否已送出
            btn = page.locator("#btnCheck")
            if btn.count() == 0 or not btn.is_visible():
                try:
                    page.evaluate('document.querySelector("#btnCheck").style.display="block"')
                    page.wait_for_timeout(300)
                except: pass
            if btn.count() == 0 or not btn.is_visible():
                print("  ⏭️ 已送出，跳過")
                continue

            # 勾選 1 — 正常（精準定位）
            try:
                section = page.locator("text=監測值連續趨勢").locator("..")
                section.get_by_label("正常").click()
            except:
                page.get_by_label("正常").first.click()
            print("  1. 正常 ✅")

            # 勾選 2 — 無
            page.get_by_label("無").first.click()
            print("  2. 無 ✅")

            # 勾選 3 — 儀器設備正常
            page.get_by_label("儀器設備正常，現地監測值達注意：加強守視。").click()
            print("  3. 儀器設備正常 ✅")

            # 送出
            if submit:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                btn.click()
                page.wait_for_timeout(2000)
                print("  📤 已送出")
            else:
                print("  ⏸️ 未送出 (--dry-run)")

            done += 1

        # 回到列表頁
        page.goto(L2_LIST, wait_until="networkidle")
        print(f"\n✅ 完成 {done}/{len(target)} 筆")
        time.sleep(5)

if __name__ == "__main__":
    count = 2
    submit = True
    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            submit = False
        elif arg.isdigit():
            count = int(arg)
    fill_reports(count, submit)
