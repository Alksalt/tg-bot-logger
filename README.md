# Telegram Time Tracker MVP (Python + SQLite)

Production-ready MVP for a Telegram bot that tracks productive time, fun spending, and a deterministic fun-points economy.

## Features

Implemented in required order:
1. `/log`, `/spend`, `/status`, `/week`, `/undo` + inline keyboard quick-add buttons
2. Sunday summary job (`python jobs.py sunday_summary`)
3. Reminders job (`python jobs.py reminders`): inactivity + daily goal
4. Plan targets (`/plan set`, `/plan show`) + midweek job (`python jobs.py midweek`)
5. Start/stop timer sessions (`/start [note]`, `/stop`)
6. Optional LLM parsing of free-form text (GPT-5 mini) with strict local validation

## Business rules

- Timezone: Europe/Oslo (`TZ=Europe/Oslo`)
- Base fun: `productive_minutes * (20/60)` -> integer minutes via floor (`productive_minutes // 3`)
- Milestones: every completed 10h all-time productive block gives `+180` fun minutes
- Bonus blocks: `floor(total_productive_minutes / 600)`
- Earned fun: `base_fun_minutes + bonus_fun_minutes`
- Fun left: `earned_fun_minutes - spent_fun_minutes`
- Bonus is computed from all-time productive totals, so no double-counting

## Project layout

- `/bot.py` bot launcher (`python bot.py` or `python -m bot`)
- `/jobs.py` cron-friendly jobs launcher
- `/src/tg_time_logger/` core package
- `/tests/` pytest suite
- `/data/app.db` SQLite DB (default)

## Setup (uv)

```bash
uv sync --extra dev
cp .env.example .env
```

## Environment variables

Use `.env` (auto-loaded by the app) or shell exports.

Example `.env`:

```bash
TELEGRAM_BOT_TOKEN=<your_bot_token>
DATABASE_PATH=./data/app.db
TZ=Europe/Oslo
LLM_ENABLED=0
OPENAI_API_KEY=<key>
```

## Run locally

```bash
uv run python bot.py
# or
uv run python -m bot
```

## Commands

- `/log <duration> [note]`
- `/spend <duration> [note]`
- `/status`
- `/week`
- `/undo`
- `/plan set 10h`
- `/plan show`
- `/reminders on`
- `/reminders off`
- `/quiet_hours 22:00-08:00`
- `/start [note]`
- `/stop`

Duration formats: `90m`, `1.5h`, `1h20m`, `45`

## Inline keyboard

- `+15m Productive`, `+30m Productive`, `+60m Productive`
- `-15m Fun`, `-30m Fun`, `-60m Fun`
- `Status`, `Week`, `Undo last`

## Scheduled jobs (cron-friendly)

```bash
uv run python jobs.py sunday_summary
uv run python jobs.py reminders
uv run python jobs.py midweek
```

### Example cron

```cron
# Sunday summary at 19:00 Oslo time
0 19 * * 0 cd /path/to/tg-time-logger && /opt/homebrew/bin/uv run python jobs.py sunday_summary

# Reminders every 15 minutes (job checks time thresholds + deduplicates)
*/15 * * * * cd /path/to/tg-time-logger && /opt/homebrew/bin/uv run python jobs.py reminders

# Midweek progress every 15 minutes on Wednesday (deduplicated per week)
*/15 * * * 3 cd /path/to/tg-time-logger && /opt/homebrew/bin/uv run python jobs.py midweek
```

## Sample interactions

- `/log 1h20m Deep focus` -> logs 80 productive minutes and returns updated totals + fun remaining
- `/spend 45m Movie break` -> logs fun spending and returns updated fun remaining
- `/plan set 10h` -> stores current week productive target
- `/start Deep focus` then `/stop` -> logs elapsed productive minutes

## Tests

```bash
uv run pytest
```

Covered:
- duration parsing
- fun rules + milestone boundaries (`599m`, `600m`, `1200m`)
- Oslo week boundaries (Mon-Sun)
- reminder trigger decision logic

## Migration

Schema migration runs automatically on startup (bot and jobs) via `schema_migrations`.

This update adds `entries.kind` and migrates existing rows:
- `work/study/learn -> productive`
- `spend -> spend`

Safe manual run path:

```bash
uv run python jobs.py reminders
```

This initializes the DB and applies pending migrations without requiring bot polling.

## Notes

- SQLite schema uses simple versioned migrations and soft-delete undo.
- Data model is multi-user by Telegram user ID.
- Jobs send messages to users who have interacted with the bot (stored user/chat profile).
