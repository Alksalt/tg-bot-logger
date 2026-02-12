# Telegram Time Logger v3 (Gamified + AI Agent)

Telegram productivity bot with categories, XP/levels, streaks, quests, shop economy, savings, AI analytics (/llm), conversational coach (/coach), web search, and interactive help guides.

## Stack

- Python 3.11+
- `python-telegram-bot`
- SQLite (18 auto-migrations)
- `uv` for dependency/runtime management
- V3 agent runtime with tiered OpenRouter models (free/cheap/top_tier)
- Web search: Brave/Tavily/Serper with fallback + cache

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

## Environment

`.env` is auto-loaded.

```bash
TELEGRAM_BOT_TOKEN=<your_bot_token>
DATABASE_PATH=./data/app.db
TZ=Europe/Oslo
LLM_ENABLED=0
OPENAI_API_KEY=<key>
OPENROUTER_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
GOOGLE_API_KEY=<key>
BRAVE_SEARCH_API_KEY=<key>
TAVILY_API_KEY=<key>
SERPER_API_KEY=<key>
NOTION_API_KEY=<key>
NOTION_DATABASE_ID=<database_id>
NOTION_BACKUP_DIR=./data/notion_backups
NOTION_BACKEND=api
NOTION_MCP_URL=
NOTION_MCP_AUTH_TOKEN=
NOTION_MCP_TOOL_NAME=notion-create-pages
LLM_PROVIDER=openai
LLM_MODEL=gpt-5-mini
LLM_ROUTER_CONFIG=./llm_router.yaml
ADMIN_PANEL_TOKEN=<strong_random_token>
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8080
AGENT_MODELS_PATH=./agents/models.yaml
AGENT_DIRECTIVE_PATH=./agents/directives/llm_assistant.md
```

LLM model/provider defaults are read from `./llm_router.yaml`.
Default route is `openai:gpt-5-mini`.

## Run

```bash
uv run python bot.py
```

Admin panel:

```bash
uv run python admin.py
```

Open:
- `http://127.0.0.1:8080/?token=<ADMIN_PANEL_TOKEN>`
- If `ADMIN_PANEL_TOKEN` is empty, panel is open without auth (not recommended).
- Admin now shows `Search Provider Health` with request/success/fail/cache/rate-limit counters.

## Jobs

```bash
uv run python jobs.py sunday_summary
uv run python jobs.py reminders
uv run python jobs.py midweek
uv run python jobs.py check_quests
uv run python jobs.py notion_backup
```

## Commands

Core:
- `/log <duration> [study|build|training|job] [note]`
- `/spend <duration> [note]`
- `/status`
- `/week`
- `/undo`
- `/help [command]`
- `/rules`
- `/rules add <text>`
- `/rules remove <id>`
- `/rules clear`
- `/llm <question>`
- `/llm tier <free|open_source_cheap|top_tier> <question>`
- `/llm models`
- `/search <query>`
- `/lang`
- `/lang <en|uk>`
- `/start [study|build|training|job|spend] [note]`
- `/stop`

Coach (AI with memory):
- `/coach <message>`
- `/coach clear`
- `/coach memory`
- `/coach forget <id>`

Plan/reminders:
- `/plan set <duration>`
- `/plan show`
- `/reminders on|off`
- `/quiet_hours HH:MM-HH:MM`
- `/freeze`

Quests/shop/savings:
- `/quests`
- `/quests history`
- `/shop`
- `/shop add <emoji> "name" <cost_minutes_or_duration> [nok_value]`
- `/shop add <emoji> "name" <nok_value>nok`
- `/shop price <emoji> "name" <search query>`
- `/shop price <emoji> "name" <search query> --add` (confirm via button)
- `/shop remove <id>`
- `/shop budget <minutes|off>`
- `/redeem <item_id|item_name>`
- `/redeem history`
- `/save`
- `/save goal <target_duration> [name]`
- `/save fund <duration>`
- `/save sunday on 50|60|70`
- `/save sunday off`
- `/save auto <duration>`

Savings behavior:
- Save fund is locked from normal fun usage.
- Shop redemption spends from save fund first, then from remaining fun.
- If a redemption is fully covered by save fund, remaining fun does not decrease.

Price conversion:
- Default: `1 NOK = 3 fun min` (tunable via admin key `economy.nok_to_fun_minutes`).
- `/shop price ...` uses web search and suggests a command with converted cost.
- `/shop price ... --add` creates a pending add; press **Confirm add** button to save item.

Notion backup:
- `uv run python jobs.py notion_backup` writes per-user JSON snapshots to `NOTION_BACKUP_DIR`.
- Backend switch:
  - `NOTION_BACKEND=api` uses Notion REST API (`NOTION_API_KEY` + `NOTION_DATABASE_ID`)
  - `NOTION_BACKEND=mcp` uses JSON-RPC MCP endpoint (`NOTION_MCP_URL`, optional `NOTION_MCP_AUTH_TOKEN`)
  - `NOTION_BACKEND=auto` tries MCP first, then REST API fallback
- MCP tool name defaults to `notion-create-pages` (override with `NOTION_MCP_TOOL_NAME`).
- The Notion database must have at least one **Title** property.

Cron example (daily backup):

```cron
# Every day at 02:10 (server local time; set server TZ=Europe/Oslo)
10 2 * * * cd /path/to/tg-time-logger && uv run python jobs.py notion_backup >> logs/notion_backup.log 2>&1
```

Duration formats: `90m`, `1.5h`, `1h20m`, `45`

Streak rule: at least `120m` productive in a day is required to count as a streak day.

## Migrations

Migrations run automatically when `Database(...)` initializes (bot or jobs). Existing data is upgraded in place.

18 migrations covering: entries with category/xp/fun/deep-work, level-ups, streaks, quests, shop, redemptions, savings, LLM usage, user rules, app config, audit log, search cache, user profiles, user language, notion config, admin audit, coach messages, and coach memory.

## V3 Agent Layout

- `agents/directives/` human SOP specs.
- `agents/execution/` deterministic runtime logic.
- `agents/orchestration/` thin wiring layer.
- `agents/tools/` tool implementations/registry.
- `TOOLS.md` tool manifest.

## Quest Generation

- Every week the system creates exactly:
  - 1 easy quest
  - 1 medium quest
  - 1 hard quest
- Quest is selected randomly from curated pools (10 per difficulty), with anti-repeat preference.
- If LLM is enabled, one additional bonus quest can be generated from previous-week stats and then validated before insertion.

## Test

```bash
uv run pytest
```
