---
name: alice-n8n
description: "n8n 自動化工作流連接 — 觸發 n8n Webhook、查詢工作流狀態。n8n 運行於 localhost:5678。"
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [alice, n8n, automation, workflow, webhook]
    source: "移植自 Alice Bot n8n_connector_skill.py"
---

# n8n 自動化工作流連接

## ⚠️ 強制規則：主人要求操作 n8n 時，你必須實際執行 curl/terminal 命令。禁止只回文字說明。

主人的 n8n 自動化伺服器運行在 `http://localhost:5678`。

## 觸發條件

- 主人要求觸發某個 n8n 工作流
- 需要查詢 n8n 狀態
- 與 n8n 相關的任何操作

## 架構

```
Hermes → terminal → n8n_connector_skill.py → HTTP → localhost:5678
```

## 可用操作

### 觸發 Webhook 工作流

```bash
cd "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"
python -c "
import sys; sys.path.insert(0, 'skills')
from n8n_connector_skill import N8NConnectorSkill
skill = N8NConnectorSkill()
result = skill.execute('trigger_webhook', {
    'webhook_path': '/webhook/my-workflow',
    'data': {'key': 'value'}
}, {})
print(result)
"
```

### 列出活躍 Webhook

```bash
python -c "
import sys; sys.path.insert(0, 'skills')
from n8n_connector_skill import N8NConnectorSkill
skill = N8NConnectorSkill()
result = skill.execute('list_webhooks', {}, {})
print(result)
"
```

### 檢查 n8n 健康狀態

```bash
curl -s http://localhost:5678/healthz
```

## 快速測試

```bash
# 確認 n8n 是否運行
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz
# 應回傳 200
```

## 環境變數

- `N8N_API_KEY` — n8n API 金鑰（可選，在 Alice .env 中）

## 注意事項

- n8n 是獨立 APP，透過 `啟動 N8N 伺服器.bat` 啟動
- 如果 n8n 未運行，先啟動再觸發
- Webhook path 需與 n8n 工作流中的設定一致

## 相關檔案

- 原始碼：`skills/n8n_connector_skill.py`
- n8n 啟動：`啟動 N8N 伺服器.bat`
- n8n 伺服器管理：`skills/n8n_server_skill.py`
