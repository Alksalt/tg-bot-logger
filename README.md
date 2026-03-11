# Telegram Time Logger

Productivity bot that tracks time, gamifies work with XP/levels/streaks, and runs a fun-minutes economy. Single-user, self-hosted, SQLite-backed.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
# Set TELEGRAM_BOT_TOKEN and DATABASE_PATH in .env
```

## Run

```bash
uv run python bot.py             # start the bot
uv run python admin.py           # admin panel (http://127.0.0.1:8080)
uv run python jobs.py reminders  # scheduled reminders
uv run python jobs.py sunday_summary
```

## Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome / onboarding |
| `/log` | Log productive time (study/build/training/job) |
| `/spend` | Log fun/consumption time |
| `/timer` (`/t`) | Start a timer session |
| `/stop` | Stop active timer |
| `/status` | Level, XP, streak, economy, weekly chart |
| `/undo` | Undo last entry |
| `/settings` | Reminders, quiet hours |
| `/help` | Help and guide system |

Duration formats: `90m`, `1.5h`, `1h20m`, `45`

## Test

```bash
uv run pytest
```

## Environment

Required: `TELEGRAM_BOT_TOKEN`, `DATABASE_PATH`
Optional: `TZ` (default: Europe/Oslo), `ADMIN_PANEL_TOKEN`, `ADMIN_HOST`, `ADMIN_PORT`
