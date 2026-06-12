# 多電腦同步設定

## 架構
- 工具程式碼 (.py) → Git → GitHub (hansv0704/hermes-tools)
- 技能定義 (SKILL.md) → Git → GitHub
- 記憶 (USER.md/MEMORY.md) → MEGA 雲端同步 (cron 每 30min)
- API key (.env) → 每台電腦手動設定

## 新電腦安裝
1. 安裝 Hermes + Python 3.11+ + Git
2. `git clone https://github.com/hansv0704/hermes-tools.git`
3. 執行 `新電腦安裝.bat`
4. `python scripts/sync_memory.py pull`
5. `hermes -p alice gateway run`
