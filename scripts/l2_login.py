"""L2 自動登入 v3 — 用 Gemini REST API 辨識驗證碼"""
import os, sys, time, json, base64, requests
from playwright.sync_api import sync_playwright

USER_DATA = os.path.expandvars(r'%LOCALAPPDATA%\hermes\playwright_profile')
os.makedirs(USER_DATA, exist_ok=True)

L2_ACCOUNT = 'hansv0704'
L2_PASSWORD = open(r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.l2_pwd').read().strip()

# Gemini REST API key
KEY_FILE = r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.gemini_key_tmp'
G_KEY = open(KEY_FILE).read().strip()

GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'

def gemini_ocr(image_bytes):
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    body = {
        "contents": [{
            "parts": [
                {"text": "Read ONLY the captcha characters from this login image. Reply with ONLY the characters (4-6 alphanumeric). If unreadable, reply UNREADABLE."},
                {"inline_data": {"mime_type": "image/png", "data": img_b64}}
            ]
        }]
    }
    
    r = requests.post(
        f"{GEMINI_URL}?key={G_KEY}",
        json=body,
        timeout=15
    )
    
    if r.status_code != 200:
        print(f'Gemini API error: {r.status_code} {r.text[:200]}', flush=True)
        return 'UNREADABLE'
    
    resp = r.json()
    try:
        text = resp['candidates'][0]['content']['parts'][0]['text']
        return text.strip()
    except:
        return 'UNREADABLE'

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA, headless=False,
        viewport={'width': 1920, 'height': 1080},
        args=['--disable-gpu', '--no-first-run', '--ignore-certificate-errors']
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    print('Navigating to L2...', flush=True)
    page.goto('https://ls.ardswc.gov.tw/Response/EvaluateReport2List', 
              wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    
    if 'Login' not in page.url and 'EvaluateReport' in page.url:
        print('Already logged in!', flush=True)
        ctx.close()
        exit(0)
    
    print('On login page, solving captcha...', flush=True)
    
    for attempt in range(3):
        print(f'--- Attempt {attempt+1}/3 ---', flush=True)
        
        captcha_url = 'https://ls.ardswc.gov.tw/Handler/ValidateCodeHandler.ashx'
        cookies = page.context.cookies()
        
        session = requests.Session()
        for c in cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
        
        resp = session.get(captcha_url, timeout=10, verify=False)
        
        code = gemini_ocr(resp.content)
        print(f'Gemini reads: "{code}"', flush=True)
        
        if code == 'UNREADABLE' or len(code) < 2:
            print('Retrying captcha...', flush=True)
            page.locator('#VerifyCode').click()
            page.wait_for_timeout(500)
            continue
        
        page.locator('#Account').fill(L2_ACCOUNT)
        page.locator('#Passowrd').fill(L2_PASSWORD)
        page.locator('#VerifyCode').fill(code)
        page.wait_for_timeout(300)
        
        page.locator('input[type="submit"]').click()
        page.wait_for_timeout(5000)
        
        current_url = page.url
        if 'Login' not in current_url:
            print('LOGIN SUCCESS!', flush=True)
            break
        else:
            error = page.locator('.validation-summary-errors, .field-validation-error')
            if error.count() > 0:
                print(f'Error: {error.first.text_content()[:200]}', flush=True)
            else:
                print('Wrong captcha?', flush=True)
    else:
        print('FAILED after 3 attempts', flush=True)
    
    ctx.close()
    print('Done', flush=True)
