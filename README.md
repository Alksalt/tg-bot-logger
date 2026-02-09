# Telegram Time Logger v2 (Gamified)

Telegram productivity bot with categories, XP/levels, streaks, quests, shop redemptions, savings goals, and weekly wheel bonuses.

## Stack

- Python 3.12+
- `python-telegram-bot`
- SQLite (schema migrations via `schema_migrations`)
- `uv` for dependency/runtime management
- Optional multi-provider LLM routing (OpenAI/Anthropic/Google; OpenAI wired by default)

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
ANTHROPIC_API_KEY=<key>
GOOGLE_API_KEY=<key>
LLM_PROVIDER=openai
LLM_MODEL=gpt-5-mini
LLM_ROUTER_CONFIG=./llm_router.yaml
```

LLM model/provider defaults are read from `/Users/alt/Library/CloudStorage/OneDrive-Personal/automations/tg-time-logger/llm_router.yaml`.
Default route is `openai:gpt-5-mini`.

## Run

```bash
uv run python bot.py
```

## Jobs

```bash
uv run python jobs.py sunday_summary
uv run python jobs.py reminders
uv run python jobs.py midweek
uv run python jobs.py check_quests
```

## Commands

Core:
- `/log <duration> [study|build|training|job] [note]`
- `/spend <duration> [note]`
- `/status`
- `/week`
- `/undo`
- `/start [study|build|training|job] [note]`
- `/stop`

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
- `/shop add <emoji> "name" <cost_minutes> [nok_value]`
- `/shop remove <id>`
- `/shop budget <minutes|off>`
- `/redeem <item_id|item_name>`
- `/redeem history`
- `/save`
- `/save <target_duration> <name>`
- `/save deposit <duration>`
- `/save auto <duration>`
- `/save cancel <id>`
- `/save complete <id>`

Duration formats: `90m`, `1.5h`, `1h20m`, `45`

## Migrations

Migrations run automatically when `Database(...)` initializes (bot or jobs). Existing data is upgraded in place.

This v2 upgrade adds:
- category/xp/fun/deep-work columns on entries
- level-up events
- streaks and streak freezes
- quests
- shop and redemptions
- weekly wheel spins
- savings goals

## Test

```bash
uv run pytest
```
