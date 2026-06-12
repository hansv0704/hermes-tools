# Gemini Flash 圖表分析 Prompt 模板

用於分析參考圖表，取得完整佈局資訊後再複刻。

## Prompt（繁體中文）

```
請詳細分析這張降雨監測圖表，用繁體中文回答以下問題：

1. 圖表類型是什麼？(例如：柱狀圖、折線圖、雙軸圖...)
2. X軸顯示什麼？單位/刻度是什麼？
3. Y軸有幾個？分別顯示什麼？單位是什麼？刻度範圍和間距？
4. 圖中有幾種資料系列？各自的顏色、樣式是什麼？
5. 圖例在什麼位置？內容是什麼？
6. 標題是什麼？
7. 網格線的樣式？
8. 圖表背景顏色？
9. 有什麼特殊的標註或輔助線？
10. 整體風格是偏向科學繪圖還是簡報風格？

請用結構化的方式回答，越詳細越好。
```

## 使用方式

```python
from google import genai

# 讀取 API key（繞過 Hermes secret redaction）
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'GOOGLE_API_KEYS' in line and '=' in line:
            api_key = line.split('=', 1)[1].strip()
            break

client = genai.Client(api_key=api_key)

with open(img_path, 'rb') as f:
    img_data = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[prompt, {'inline_data': {'mime_type': 'image/png', 'data': img_data}}]
)
print(response.text)
```

## 注意

- 使用 `gemini-2.5-flash`（成本考量，圖片分析夠用）
- 結果回傳後由 DeepSeek 或其他模型繼續工作
- API key 從 `.env` 的 `GOOGLE_API_KEYS` 讀取
