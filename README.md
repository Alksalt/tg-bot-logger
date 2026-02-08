# Telegram Time Tracker MVP (Python + SQLite)

Production-ready MVP for a Telegram bot that tracks productive time, fun spending, and a deterministic fun-points economy.

## Features

Implemented in required order:
1. `/log`, `/spend`, `/status`, `/week`, `/undo` + inline keyboard quick-add buttons
2. Sunday summary job (`python jobs.py sunday_summary`)
3. Reminders job (`python jobs.py reminders`): inactivity + daily goal
4. Plan targets (`/plan set`, `/plan show`) + midweek job (`python jobs.py midweek`)
5. Start/stop timer sessions (`/start <category>`, `/stop`)
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

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
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
python bot.py
# or
python -m bot
```

## Commands

- `/log <work|study|learn> <duration> [note]`
- `/spend <duration> [note]`
- `/status`
- `/week`
- `/undo`
- `/plan set work 10h study 5h learn 3h`
- `/plan show`
- `/reminders on`
- `/reminders off`
- `/quiet_hours 22:00-08:00`
- `/start <work|study|learn> [note]`
- `/stop`

Duration formats: `90m`, `1.5h`, `1h20m`, `45`

## Inline keyboard

- `+15m Work`, `+30m Work`, `+60m Work`
- `+15m Study`, `+30m Study`, `+60m Study`
- `+15m Learn`, `+30m Learn`, `+60m Learn`
- `Status`, `Week`, `Undo last`

## Scheduled jobs (cron-friendly)

```bash
python jobs.py sunday_summary
python jobs.py reminders
python jobs.py midweek
```

### Example cron

```cron
# Sunday summary at 19:00 Oslo time
0 19 * * 0 cd /path/to/tg-time-logger && /path/to/.venv/bin/python jobs.py sunday_summary

# Reminders every 15 minutes (job checks time thresholds + deduplicates)
*/15 * * * * cd /path/to/tg-time-logger && /path/to/.venv/bin/python jobs.py reminders

# Midweek progress every 15 minutes on Wednesday (deduplicated per week)
*/15 * * * 3 cd /path/to/tg-time-logger && /path/to/.venv/bin/python jobs.py midweek
```

## Sample interactions

- `/log work 1h20m Deep focus` -> logs 80 productive minutes and returns updated totals + fun left
- `/spend 45m Movie break` -> logs fun spending and returns updated fun left
- `/plan set work 10h study 5h learn 3h` -> stores current week targets
- `/start study reading` then `/stop` -> logs elapsed productive minutes in study category

## Tests

```bash
pytest
```

Covered:
- duration parsing
- fun rules + milestone boundaries (`599m`, `600m`, `1200m`)
- Oslo week boundaries (Mon-Sun)
- reminder trigger decision logic

## Notes

- SQLite schema uses simple versioned migrations and soft-delete undo.
- Data model is multi-user by Telegram user ID.
- Jobs send messages to users who have interacted with the bot (stored user/chat profile).
