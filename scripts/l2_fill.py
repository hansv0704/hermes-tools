"""L2 巡檢表自動填寫 v2.0 — 內建 Gemini 自動登入 + DOM 操控填寫"""
import os, sys, time, json, base64, requests
from playwright.sync_api import sync_playwright

USER_DATA = os.path.expandvars(r'%LOCALAPPDATA%\hermes\playwright_profile')
os.makedirs(USER_DATA, exist_ok=True)

L2_BASE = "https://ls.ardswc.gov.tw"
L2_LIST = f"{L2_BASE}/Response/EvaluateReport2List"
L2_ACCOUNT = 'hansv0704'
L2_PASSWORD = open(r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.l2_pwd').read().strip()

# 讀 Gemini key
G_KEY = open(r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.gemini_key_tmp').read().strip()
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'

def gemini_read_captcha(img_bytes):
    b64 = base64.b64encode(img_bytes).decode()
    r = requests.post(f"{GEMINI_URL}?key={G_KEY}", json={
        "contents": [{"parts": [
            {"text": "Read the captcha. Output ONLY the characters."},
            {"inline_data": {"mime_type": "image/png", "data": b64}}
        ]}]
    }, timeout=15)
    if r.status_code == 200:
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    return ''

def do_login(page):
    """自動登入 L2"""
    print('Logging in...', flush=True)
    page.goto(L2_LIST, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(2000)
    
    if 'Login' not in page.url:
        print('Already logged in', flush=True)
        return True
    
    for attempt in range(4):
        # 取得驗證碼
        cookies = page.context.cookies()
        s = requests.Session()
        for c in cookies:
            s.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
        captcha = s.get(f'{L2_BASE}/Handler/ValidateCodeHandler.ashx', timeout=10, verify=False).content
        
        code = gemini_read_captcha(captcha)
        print(f'  Captcha attempt {attempt+1}: "{code}"', flush=True)
        
        if len(code) < 2:
            page.locator('#VerifyCode').click()
            page.wait_for_timeout(800)
            continue
        
        page.locator('#Account').fill(L2_ACCOUNT)
        page.locator('#Passowrd').fill(L2_PASSWORD)
        page.locator('#VerifyCode').fill(code)
        page.locator('input[type="submit"]').click()
        page.wait_for_timeout(5000)
        
        if 'Login' not in page.url:
            print('Login OK!', flush=True)
            return True
        
        err = page.locator('.validation-summary-errors, .field-validation-error')
        if err.count() > 0:
            print(f'  Error: {err.first.text_content()[:100]}', flush=True)
    
    print('Login FAILED', flush=True)
    return False

def fill_reports(count=2, submit=True):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA, headless=False,
            viewport={"width": 1920, "height": 1080},
            args=["--disable-gpu", "--no-first-run", "--ignore-certificate-errors"]
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 先確保登入
        if not do_login(page):
            ctx.close()
            return
        
        # 列表頁：只收集「填寫時間為空」的 ReportID
        page.goto(L2_LIST, wait_until="networkidle")
        page.wait_for_timeout(2000)
        
        # 找表格所有列，檢查填寫時間欄位
        report_ids = []
        rows = page.locator('table tr').all()
        for row in rows:
            cells = row.locator('td').all()
            if len(cells) < 3:
                continue
            # 檢查是否有回報按鈕 + 填寫時間為空
            btn = row.locator('a:has-text("回報")')
            if btn.count() == 0:
                continue
            # 填寫時間通常在倒數第3-4欄，檢查內容
            fill_time = ''
            for cell in cells[-5:]:
                text = cell.inner_text().strip()
                if text == '' or text == '--' or '/' in text and len(text) < 20:
                    fill_time = text
                    break
            # 填寫時間為空 → 需要填寫
            if fill_time == '':
                href = btn.first.get_attribute('href')
                if href and 'ReportID=' in href:
                    rid = href.split('ReportID=')[-1].split('&')[0]
                    report_ids.append(rid)
        
        target = report_ids[:count] if count else report_ids
        print(f'未填寫: {len(report_ids)} 筆, 本次處理: {len(target)}', flush=True)
        if target:
            print(f'ReportIDs: {target}', flush=True)
        else:
            print('✅ 全部已填寫完畢', flush=True)
            ctx.close()
            return
        
        done = 0
        for rid in target:
            print(f'\n--- ReportID={rid} ---', flush=True)
            page.goto(f"{L2_BASE}/Response/CreateEvaluateReport2?ReportID={rid}",
                      wait_until="networkidle")
            page.wait_for_timeout(2000)
            
            # 檢查已送出
            btn = page.locator("#btnCheck")
            if btn.count() == 0 or not btn.is_visible():
                try:
                    page.evaluate('document.querySelector("#btnCheck").style.display="block"')
                    page.wait_for_timeout(300)
                except: pass
            if btn.count() == 0 or not btn.is_visible():
                print("  Skipped (already submitted)", flush=True)
                continue
            
            # 勾選
            try:
                section = page.locator("text=監測值連續趨勢").locator("..")
                section.get_by_label("正常").click()
            except:
                page.get_by_label("正常").first.click()
            print("  1. OK", flush=True)
            
            page.get_by_label("無").first.click()
            print("  2. OK", flush=True)
            
            page.get_by_label("儀器設備正常，現地監測值達注意：加強守視。").click()
            print("  3. OK", flush=True)
            
            if submit:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)
                btn.click()
                page.wait_for_timeout(2000)
                print("  SUBMITTED", flush=True)
            else:
                print("  DRY-RUN (not submitted)", flush=True)
            
            done += 1
        
        page.goto(L2_LIST, wait_until="networkidle")
        print(f'\nDONE: {done}/{len(target)}', flush=True)
        time.sleep(3)
        ctx.close()

if __name__ == "__main__":
    count = 0  # 0 = 全部未填寫的
    submit = True
    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            submit = False
        elif arg.isdigit():
            count = int(arg)
    fill_reports(count, submit)
