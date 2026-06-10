# 🧠 Alice 核心 — 專案總覽
> **最後更新**：2026-06-02 08:10

## 🎯 專案目標
Alice 全能私人秘書 AI，具備：
- Telegram 聊天互動
- GIS 監控
- 投資代理人（獨立系統）
- 遊戲開發 (GameStudio)
- n8n 自動化

## 📂 核心檔案

| 檔案 | 用途 |
|:--|:--|
| `main.py` | 主入口 |
| `agent.py` | Alice 代理人核心 |
| `handlers.py` | Telegram 指令處理 |
| `memory.py` | 記憶系統 |
| `config.py` | 系統配置 |
| `tools.py` | 工具註冊 |

## 🔑 子系統

| 系統 | 狀態 | 獨立性 |
|:--|:--|:--|
| Telegram Bot | 🟢 運行中 | 核心 |
| GIS 監控 | 🟢 運行中 | 獨立循環 |
| 投資代理人 | 🟡 開發中 | 獨立 Flask |
| n8n 自動化 | 🟢 運行中 | 獨立服務 |
| GameStudio | 🟢 可用 | 獨立 APP |
| LiveCodeStudio | 🟢 可用 | 獨立 APP |
