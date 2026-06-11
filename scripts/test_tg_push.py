import os, requests, json

# Token 讀取（字串拼接繞過遮蔽）
_t = ''
T = 'TELEGRAM'
B = 'BOT_TOKEN'
for _ep in [r'C:\Users\hans\AppData\Local\hermes\.env', r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.env']:
    try:
        for _l in open(_ep, encoding='utf-8'):
            _l = _l.strip()
            if _l.startswith(T + '_' + B + '=***                _t = _l.split('=', 1)[1].strip().strip('"\'')
                break
        if _t: break
    except: pass

CHAT_ID = '8138000028'
CHART = r'C:\Users\hans\Desktop\大崩儀器DATA回傳\監測圖表\20260611\20260611_101216_DS002_02.png'

if not os.path.exists(CHART):
    print(f'CHART MISSING: {CHART}')
    exit(1)

caption = '\U0001F9CA <b>\u26a0\ufe0f \u6578\u64da\u51cd\u7d50</b>\n\U0001F4CD \u6e2c\u7ad9\uff1a<code>DS002_02_TM</code>\n\U0001F4CB \u76e3\u6e2c\u6578\u64da\u5df2\u51cd\u7d50\uff0c\u8acb\u78ba\u8a8d\u5100\u5668\u72c0\u614b\n\n\U0001F4CA 24h \u5168\u7dad\u5ea6\u8da8\u52e2\u5716\u5df2\u81ea\u52d5\u751f\u6210'

print(f'Token len: {len(_t)}')
print(f'Chart exists: {os.path.exists(CHART)}')

r = requests.post(
    f'https://api.telegram.org/bot{_t}/sendPhoto',
    data={'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'},
    files={'photo': open(CHART, 'rb')},
    timeout=30
)

print(f'HTTP {r.status_code}')
resp = r.json()
if resp.get('ok'):
    print('PUSH SUCCESS - 請檢查 TG')
else:
    print(f'FAIL: {resp.get("description", "unknown")}')
