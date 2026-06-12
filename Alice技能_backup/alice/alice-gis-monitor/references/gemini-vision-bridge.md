# Gemini Vision Bridge 模式

## 架構

```
DeepSeek（主模型，便宜處理文字）
    ↓ 需要看圖時
Gemini 2.5 Flash（視覺分析，最便宜）
    ↓ 回傳文字
DeepSeek（繼續工作）
```

## 使用方式

```bash
python scripts/gemini_vision.py "用繁體中文描述這個畫面"
```

## 程式碼核心

```python
from PIL import ImageGrab
from google import genai
import base64

# 1. 截圖
path = 'screenshots/ss.png'
ImageGrab.grab().save(path)

# 2. 讀取 API key（從 .env 避開遮蔽）
key = ''
for line in open('.env', encoding='utf-8'):
    if 'GOOGLE' in line and 'API_KEYS' in line:
        key = line.split('=',1)[1].strip().split(',')[0].strip('"\'')

# 3. Gemini 分析
with open(path,'rb') as f:
    img = base64.b64encode(f.read()).decode()
client = genai.Client(api_key=key)
r = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[prompt, {'inline_data':{'mime_type':'image/png','data':img}}]
)
print(r.text)  # 回傳給主模型
```

## 成本

- Gemini 2.5 Flash: ~$0.075/1M tokens（截圖分析）
- DeepSeek: ~$0.14/1M tokens（文字工作）
- 比全用 Gemini Pro 省 ~70%

## 截圖管理

- 目錄: `screenshots/`
- 自動清理 7 天前舊檔
- 不提交到 Git（.gitignore）
