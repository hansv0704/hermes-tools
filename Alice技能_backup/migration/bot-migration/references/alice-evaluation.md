# Alice Bot Migration — Worked Example

> Real evaluation of a custom Telegram bot (~50 skills, dual AI engines, 5 subsystems) for Hermes migration. Demonstrates the three-tier classification methodology from SKILL.md.

## Bot Profile

- **Name**: Alice (艾莉絲)
- **Type**: Telegram bot with dual Gemini + DeepSeek engines
- **Skills**: ~50 Python modules in `skills/` directory
- **Subsystems**: Investment Agent (Flask, port 5002), GIS Monitor, n8n (port 5678), GameStudio (port 5003), LiveCode Studio
- **Memory**: Short/medium/long JSON + FTS5 SQLite + Qdrant vector + DuckDB facts
- **Personality**: Professional female secretary persona, Traditional Chinese, data-driven, "外冷內熱" (cool exterior, warm interior)
- **Key user values**: GIS monitoring tools and Taiwan stock market are critical; wants careful evaluation

## Tier 1 Classification Results (Must Port)

| Skill | Size | Rationale |
|:--|:--|:--|
| gis_inspection_reply_skill.py | 14.7KB | Automates GIS inspection forms via pyautogui. v4.0 with vision coordinate + keyboard + CDP modes. Core work tool. |
| taiwan_market_skill.py | 15.7KB | TWSE/TPEX data via yfinance. Taiwan-specific, no Hermes equivalent. |
| mega_speedy_skill.py | 57.5KB | Mega Securities API (Taiwan broker). Proprietary integration. |
| brokerage_engine.py | 18.9KB | Taiwan brokerage abstraction layer. |
| n8n_connector_skill.py | 6.9KB | User's existing automation pipeline connector. |
| gis_alert_skill | heartbeat | GIS anomaly detection + Telegram push. Critical monitoring. |

## Tier 2 Classification Results (Refactor, Then Port)

| Group | Files | Consolidation Plan |
|:--|:--|:--|
| Excel (8 files) | excel_live_skill, excel_filter_save, excel_formula_builder, dynamic_excel_matcher, excel_custom_processor, excel_sheet_lister, read_specific_excel_row, pipeline_middleware | Merge into 1 `alice-excel` skill |
| Word (2 files) | word_editor_skill (32.5KB), word_table_rebuild_skill (15.5KB) | Merge into 1 `alice-docx` skill |
| Cloud | cloud_sync_skill.py (6.7KB) | Keep MEGA sync core, drop unnecessary abstractions |
| Data | data_hub_skill.py (20.5KB) | Keep DuckDB query core only |
| LiveCode Studio | live_code_studio_skill.py (60.5KB) | Keep as standalone app; Hermes launches via terminal |

## Tier 3 Classification Results (Do Not Port — Hermes Has It)

| Legacy Skill | Hermes Replacement |
|:--|:--|
| playwright_browser_skill.py | `browser` tools (native CDP) |
| search_skill.py | `web_search` tool |
| memory_search_skill.py | `session_search` (FTS5) |
| self_review_skill.py | Curator system |
| heartbeat_skill.py | `cronjob` + `hermes doctor` |
| os_control_skill.py | `terminal` tool |
| mcp_skill.py | Native MCP Server/Client |
| github_integration_skill.py, github_mcp_skill.py | Hermes GitHub skills |
| gmail_skill.py | Hermes email skill (himalaya) |
| learning_skill.py, skill_builder_skill.py | Hermes skill system itself |
| system_recovery_skill.py | `hermes backup` / profiles |
| telegram_skill.py | Native Telegram gateway |
| brain_orchestrator_skill.py | `delegate_task` + kanban |
| deepseek_vision_bridge_skill.py | `vision` tool |
| code_search_skill.py | `search_files` tool |
| syntax_navigator_skill.py | Handled internally by Hermes |
| self_awareness_skill.py | Persona system |
| decision_logger_skill.py | Session transcripts |
| tech_scout_skill.py, diff_skill.py, external_patcher_skill.py, file_overwriter_skill.py | `patch` + `search_files` tools |

## Personality Migration

Source: `bot_config.txt` — Traditional Chinese, professional secretary persona, data-driven tone, proactive suggestion style. Directly portable to Hermes persona file. Key traits to preserve:

- Professional but warm tone (不像對上級，像有默契的夥伴)
- Traditional Chinese output
- Proactive: always ask about next potential need before ending
- Data-driven: prefer lists, tables, charts for analysis
- Emotional restraint: show loyalty through task completion, not words

## Memory Content to Port

From Alice's memory stores:
- User name: 顥宇, Telegram ID: 8138000028
- Location: 台南市仁德區
- Occupation: GIS expert / developer / investor
- Tools: ArcMap, Google Earth Pro, VS Code, Python 3.13
- GIS project path: C:\Users\hans\Desktop\大崩儀器DATA回傳
- Core iron rules: Investment Agent ≠ Telegram (separate systems); paper/live trading isolation

## Subsystem Handling

| Subsystem | Approach |
|:--|:--|
| Investment Agent (Flask, :5002) | Keep independent. Hermes calls via webhook/terminal. Follow iron rule: do not absorb. |
| GIS Monitor (background loop) | Replace with cronjob + script. More reliable than long-running loop. |
| n8n (:5678) | Keep independent. Hermes triggers via webhook. |
| GameStudio (:5003) | Keep independent. Hermes launches/stops via terminal. |
| LiveCode Studio | Keep as standalone app. Hermes triggers via terminal. |
