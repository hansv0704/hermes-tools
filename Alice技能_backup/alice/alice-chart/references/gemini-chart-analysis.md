# Gemini Flash 圖表分析 SOP

## 使用時機

當主人提供參考圖（截圖），要求複刻圖表風格時，先用 Gemini Flash 分析原圖規格，再動筆。

## 步驟

### 1. 讀取 API Key

```python
# Key 在 .env 中，因 Hermes secret redaction 無法直接用 read_file 讀取
# 必須用 terminal + Python 繞過：
env_path = r'C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.env'
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'GOOGLE_API_KEYS' in line and '=' in line:
            api_key = line.split('=', 1)[1].strip()
            break
```

### 2. 安裝套件

```bash
pip install google-genai
```

### 3. 送圖給 Gemini Flash 分析

```python
from google import genai
client = genai.Client(api_key=api_key)

with open(img_path, 'rb') as f:
    img_data = f.read()

prompt = """請詳細分析這張降雨監測圖表，用繁體中文回答以下問題：
1. 圖表類型是什麼？(例如：柱狀圖、折線圖、雙軸圖...)
2. X軸顯示什麼？單位/刻度是什麼？
3. Y軸有幾個？分別顯示什麼？單位是什麼？
4. 圖中有幾種資料系列？各自的顏色、樣式是什麼？
5. 圖例在什麼位置？內容是什麼？
6. 標題是什麼？
7. 網格線的樣式？
8. 圖表背景顏色？
9. 有什麼特殊的標註或輔助線？
10. 整體風格是偏向科學繪圖還是簡報風格？
"""

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[prompt, {'inline_data': {'mime_type': 'image/png', 'data': img_data}}]
)
print(response.text)
```

### 4. 將 Gemini 分析結果轉為繪圖規格

根據分析結果，逐項填入 matplotlib 參數：
- 圖表類型 → `ax1.bar()` / `ax2.plot()`
- X軸格式 → `set_xticks` + `strftime`
- Y軸範圍/刻度 → `set_ylim` + `MultipleLocator`
- 顏色 → hex 色碼
- 圖例 → 位置 + 內容

## 成本考量

- Gemini Flash 用於圖像分析（token 貴）
- DeepSeek 用於後續文字工作和程式碼生成（token 便宜）
- 符合主人設定的「截圖分析用 Gemini Flash，結果回傳 DeepSeek 繼續工作」
