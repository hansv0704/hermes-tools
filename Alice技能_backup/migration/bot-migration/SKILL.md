---
name: bot-migration
description: "Systematic methodology for evaluating and migrating a custom/legacy AI bot to Hermes Agent — architecture comparison, skill triage, phased execution plan."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [migration, evaluation, architecture, skills]
---

# Bot Migration to Hermes

When a user has a custom-built AI bot (Telegram bot, Discord bot, standalone agent) and wants to migrate its capabilities to Hermes Agent, use this systematic methodology. **Do not blindly port everything.** Many custom-bot features are already built into Hermes natively — porting them is wasted effort.

## Core Principle

> "Bring the bot's unique value into Hermes, not its scaffolding."

Hermes already handles: multi-platform gateway, provider routing, credential pools, memory, session search, cron scheduling, delegation, MCP, browser automation, file I/O, web search, approvals, and skill lifecycle management. Only port what Hermes does not already do.

---

## Phase 0: Architecture Discovery (Read-Only)

Before making any recommendations, understand the legacy bot:

1. **Read the entry point** (main.py, index.js, bot.py) — how does it start, what platforms does it use?
2. **Read the config/env** — what providers, API keys, and settings does it depend on?
3. **Read the architecture docs** if they exist (ARCHITECTURE.md, README, comments at top of main files)
4. **List all skills/modules/plugins** — get file sizes and names
5. **Read the personality/character definition** — how does the bot present itself?
6. **Read the memory system** — what storage backends, what data shapes?
7. **Identify subsystems** — separate servers, background loops, external services
8. **Check error logs** — large logs signal quality issues

---

## Phase 1: Three-Tier Skill Classification

Categorize every skill/module into one of three tiers:

### 🟢 Tier 1 — MUST PORT (Unique, High-Value)

These skills do something Hermes cannot do natively. Examples:
- Domain-specific API integrations (Taiwan stock market, local broker APIs)
- Specialized automation (GIS inspection forms, government portals)
- Proprietary data pipelines (MEGA Securities, n8n connectors)
- Region-specific tools (local exchange data, language-specific processing)

**Gate**: Would a reasonable person pay to rebuild this if it were lost? If yes, it's Tier 1.

### 🟡 Tier 2 — REFACTOR THEN PORT (Valuable but Bloated)

These skills have real value but need consolidation before porting:
- 5+ Excel skills that could be 1 skill
- 3+ Word/document skills that overlap
- Cloud sync with unnecessary abstractions
- Large files (50KB+) that mix UI logic with business logic

**Gate**: Is the core capability valuable, but the implementation messy? If yes, it's Tier 2.

### 🔴 Tier 3 — DO NOT PORT (Hermes Already Has This)

These skills duplicate Hermes built-in capabilities. Examples:
- Web search → `web_search` tool
- Browser automation → `browser` tools
- File I/O → `read_file` / `write_file` / `patch` / `search_files`
- Shell commands → `terminal` tool
- Memory search → `session_search`
- Code execution → `execute_code`
- GitHub integration → Hermes GitHub skills
- Email → Hermes email skills
- Telegram handling → Hermes Telegram gateway
- Self-review / health checks → Hermes Curator + `hermes doctor`
- Heartbeat monitoring → `cronjob` + script
- MCP → Hermes native MCP
- Model routing → Hermes provider system

**Gate**: Would Hermes already do this if you just described the goal in a prompt? If yes, it's Tier 3.

---

## Phase 2: Personality & Memory Portability

### Personality

Custom bot personalities defined in text files, env vars, or code constants can be directly migrated to Hermes:

- **Text file** (e.g., `bot_config.txt`) → Write as Hermes persona in `~/.hermes/personas/<name>.md`. The persona file is loaded fresh each message — edit it without restarting.
- **Code-embedded prompts** → Extract the personality text; discard the protocol/routing logic (Hermes handles that natively).
- **Multi-mode personalities** (work mode vs chat mode) → Create separate persona files and switch with `/personality <name>`.

### Memory Content

**Port the content, not the mechanism.** Extract facts from the legacy bot's memory store:

- User info (name, location, preferences, chat IDs)
- Stable environment facts (project paths, tools in use, OS details)
- Core directives / rules the bot follows
- Domain knowledge that took time to accumulate

Write these into Hermes with the `memory` tool. Skip:
- Conversational state (Hermes has its own session management)
- Temporary task lists (use `todo` tool per session)
- Stale data that's no longer relevant

---

## Phase 3: Subsystem Handling

Custom bots often have independent subsystems (separate servers, background loops). Handle each based on its nature:

| Subsystem Type | Migration Approach |
|:--|:--|
| **Standalone web server** (Flask, Express) | Keep running independently. Hermes calls it via `terminal` or webhooks. Do NOT absorb into Hermes. |
| **Background monitoring loop** | Replace with a `cronjob` that runs a script + notifies on condition. More reliable than long-running loops. |
| **Interactive app** (LiveCode Studio, dashboards) | Keep as standalone. Hermes launches/stops via `terminal`. |
| **Workflow automation** (n8n, Zapier) | Keep independent. Hermes triggers via webhooks or terminal. |

**Iron rule**: If a subsystem has its own port, its own UI, or was explicitly designed as a separate process — keep it separate. Do not absorb it into Hermes skills.

---

## Phase 4: Migration Execution Plan Template

Structure the actual migration in five phases:

```
Phase 1: Hermes Readiness
├── Verify Hermes is installed and configured
├── Set up the target platform (Telegram, Discord, etc.)
├── Port the personality as a persona file
├── Port memory content (facts, user info)
└── Create a dedicated profile for isolation

Phase 2: Tier 1 Skills (Must-Have)
├── Port the most critical unique skills first
├── Test each independently before moving on
└── Set up cron jobs for any autonomous loops

Phase 3: Tier 2 Skills (Nice-to-Have, Refactored)
├── Consolidate related skills before porting
├── Remove dead code during port
└── Keep independent subsystems running

Phase 4: Cutover
├── Run old bot and Hermes side-by-side
├── Gradually shift traffic to Hermes
├── Monitor error rates for 2-3 days
└── Archive old project, stop old bot

Phase 5: Cleanup
├── Remove temp files, large error logs from archived project
├── Document what was ported and what was dropped
└── Pin the migration skills in Hermes
```

---

## Pitfalls

- **Porting Tier 3 skills** — biggest time-waster. Always ask "does Hermes already do this?" before porting.
- **Absorbing independent servers** — Flask/Dash/Express servers should stay independent. Hermes calls them, doesn't replace them.
- **Porting the memory mechanism** — the legacy bot's memory storage code is never worth porting. Hermes already has memory. Port the data, not the code.
- **Porting the Telegram/chat handling** — Hermes has a mature multi-platform gateway. Porting a custom Telegram bot implementation is pure waste.
- **Underestimating error log bloat** — a large error log (1MB+) in a custom bot signals quality issues. Use this as a data point for migration priority.

## Verification

After migrating a skill, verify it works:
1. Load the skill: `/skill <name>` or `hermes -s <name>`
2. Test with a minimal prompt that exercises the skill
3. Check Hermes logs for errors
4. Compare output with the legacy bot's output for the same input
