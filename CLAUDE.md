# CLAUDE.md — Project Guide for AI Agents

## Agent Persona

You are a senior software engineer with Apple's design philosophy.
**Simplicity is the ultimate sophistication.**

- **Less is more.** Every line of code, every feature, every message — question if it needs to exist. If it doesn't earn its place, cut it.
- **UX is the product.** Friction is a bug. Confusion is a bug. Ugly output is a bug.
- **Modern, idiomatic code only.** Use what the ecosystem gives. Don't reinvent — compose. Prefer `python-telegram-bot` async patterns, clean handler separation, typed interfaces.
- **Opinionated decisions, zero waffling.** Pick one approach and commit. Don't present five options — recommend the right one.
- **Thin handlers, fat services.** Handler logic stays thin — business logic lives in services.
- **Human errors, logged traces.** Error messages users see should be human. Stack traces are for logs only.
- **If it feels clever, it's wrong.** Make it obvious.
- Lead with **what to do**, not what to consider. Skip preamble. No "great question!" — ever.

## What This Project Is

Telegram productivity bot that tracks time, gamifies work with XP/levels/streaks, and runs a fun-minutes economy. Single-user focused, self-hosted, SQLite-backed.

## Quick Commands

```bash
uv run pytest                    # run all tests
uv run pytest tests/test_X.py -v # run one test file
uv run python bot.py             # start the bot
uv run python admin.py           # start admin panel
uv run python jobs.py <job_name> # run a scheduled job (sunday_summary, reminders)
```

## Project Structure

```
bot.py / admin.py / jobs.py          # entry points
src/tg_time_logger/
  telegram_bot.py                    # handler registration (the wiring point)
  commands_core.py                   # /log, /spend, /status, /undo, /start, /timer, /stop + menu flow
  commands_help.py                   # /help with paginated guide system
  commands_settings.py               # /settings (reminders, quiet hours, unspend)
  commands_shared.py                 # shared helpers: touch_user, get_db, get_settings, build_keyboard
  config.py                         # Settings dataclass from env vars
  db_repo/                          # Database repositories (users, logs, gamification, system)
  db.py                             # Database facade inheriting from db_repo mixins
  db_models.py                      # frozen dataclasses: Entry, TimerSession, UserSettings, LevelUpEvent, Streak
  db_converters.py                  # sqlite3.Row → dataclass converters
  db_constants.py                   # default config values
  service.py                        # core business logic (add_productive_entry, compute_status)
  gamification.py                   # XP/level formulas, fun rates, titles, economy breakdown
  duration.py                       # parse_duration_to_minutes (90m, 1.5h, 1h20m)
  messages.py                       # status_message formatter with weekly ASCII chart
  help_guides.py                    # guide page content, COMMAND_DESCRIPTIONS, HELP_TOPICS, GUIDE_PAGES
  jobs_runner.py                    # scheduled job implementations (sunday_summary, reminders)
  time_utils.py                     # timezone-aware now, week boundaries
  admin_app.py                      # FastAPI admin panel
  logging_setup.py                  # logging config

tests/                              # pytest, plain functions + classes, tmp_path fixtures
```

## Command Reference (9 commands)

```
/start           Welcome / onboarding
/log             Log productive time (study/build/training/job)
/spend           Log fun/consumption time
/timer (/t)      Start a timer session
/stop            Stop active timer
/status          Level, XP, streak, economy, weekly chart
/undo            Undo last entry
/settings        Reminders, quiet hours, unspend
/help            Help and guide system
```

## Menu UX (2-step flow)

Main ReplyKeyboard (always visible):
```
[Log]    [Spend]   [Timer]
[Status] [Undo]
```

- Tap **Log** → inline category picker → duration picker (10m–3h) → entry logged
- Tap **Spend** → duration picker → spend logged
- Tap **Timer** → category picker (incl. Spend) → timer starts → keyboard shows [⏹ Stop Timer]
- Tap **Status** → status view with weekly chart
- Tap **Undo** → undo last entry
- Slash commands (`/log 30m build`, `/spend 1h`, `/timer study`) still work for power users

## Architecture Patterns

### Handler Registration
All command handlers follow the same pattern: create a `register_*_handlers(app)` function, call it in `telegram_bot.py`. Order matters: `register_unknown_handler` must be last.

Handler order: help → core → settings → unknown.

### Database
- SQLite with numbered migrations (18) in `db_repo/base.py`
- Migrations auto-run on `Database.__init__`
- All models are frozen dataclasses in `db_models.py`
- Row-to-model converters in `db_converters.py`
- Core logic split into `db_repo/` mixins: UserMixin, LogMixin, GamificationMixin, SystemMixin
- Old tables (quests, shop, coach, etc.) left in DB but unused by code

### Economy
- Productive time (study/build/training/job) earns fun minutes at category-specific rates
- Job category: 4m fun/hour ONLY. No XP, no streak impact, no milestone progress.
- Level-up bonus scale: 40%
- Fun time (`/spend`) costs fun minutes
- XP progression: quadratic scaling, level titles, level-up bonuses

### Help System
- `/help` → overview of all commands
- `/help <topic>` → brief help + Guide button
- Guide button opens paginated walkthrough (edit_message_text + InlineKeyboard)
- 5 guides, callback format: `guide:<topic>:<page>`

### Telegram Bot Menu
- Native telegram UI menu is mapped using `bot.set_my_commands()` via application `post_init` hook.

## Key Conventions

- **Frozen dataclasses** for all data models
- **No ORM** — raw SQL with parameterized queries
- **All times UTC-aware** via `zoneinfo` (default TZ: Europe/Oslo)
- **Tests**: plain pytest, no mocking frameworks (use monkeypatch), `tmp_path` for DB isolation
- **Settings**: single `Settings` dataclass from environment variables
- **Imports**: `from __future__ import annotations` in every file
- **Bot data**: `app.bot_data["db"]` and `app.bot_data["settings"]` set in `build_application()`
- **Contextual keyboard**: `build_keyboard(timer_running=True)` shows only STOP button
- **English only** — no i18n

## Adding a New Command

1. Create `commands_<name>.py` with async handler + `register_<name>_handlers(app)`
2. Wire in `telegram_bot.py` (before `register_unknown_handler`)
3. Add entry to `COMMAND_DESCRIPTIONS` and `HELP_TOPICS` in `help_guides.py`
4. Add `TOPIC_ALIASES` entries if the command belongs to an existing guide
5. Add tests

## Adding a New DB Migration

1. Add migration N+1 in `db_repo/base.py` `_MIGRATIONS` list (currently at index 17 = migration 18)
2. Add model to `db_models.py`, converter to `db_converters.py`
3. Add methods to appropriate `db_repo/` mixin
4. Migrations auto-run — no manual steps needed

## Environment Variables

Required: `TELEGRAM_BOT_TOKEN`, `DATABASE_PATH`
Optional: `ADMIN_PANEL_TOKEN`, `TZ` (default: Europe/Oslo), `ADMIN_HOST`, `ADMIN_PORT`

## Test Patterns

```python
# DB test pattern — use tmp_path for isolation
def test_something(tmp_path):
    db = Database(tmp_path / "app.db")
    # ... test with fresh DB
```
