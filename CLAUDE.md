# CLAUDE.md — Project Guide for AI Agents

## What This Project Is

Telegram productivity bot that tracks time, gamifies work with XP/levels/streaks, runs an economy (productive time earns fun minutes), and has an AI agent layer for analytics and coaching. Single-user focused, self-hosted, SQLite-backed.

## Quick Commands

```bash
uv run pytest                    # run all tests (~144 tests)
uv run pytest tests/test_X.py -v # run one test file
uv run python bot.py             # start the bot
uv run python admin.py           # start admin panel
uv run python jobs.py <job_name> # run a scheduled job
```

## Project Structure

```
bot.py / admin.py / jobs.py          # entry points
src/tg_time_logger/
  telegram_bot.py                    # handler registration (the wiring point)
  commands_core.py                   # /log, /spend, /status, /week, /undo, /plan, /start, /stop, /llm, /search, /lang, /rules, /reminders, /quiet_hours, /freeze
  commands_coach.py                  # /coach (AI coach with memory)
  commands_help.py                   # /help with paginated guide system
  commands_quests.py                 # /quests
  commands_shop.py                   # /shop, /redeem, /save
  commands_shared.py                 # shared helpers: touch_user, get_db, get_settings, build_keyboard
  config.py                         # Settings dataclass from env vars
  db.py                             # Database class with 18 migrations, all DB methods
  db_models.py                      # frozen dataclasses for all DB entities
  db_converters.py                  # sqlite3.Row → dataclass converters
  db_constants.py                   # default config values
  service.py                        # core business logic (add_productive_entry, compute_status)
  gamification.py                   # XP/level formulas, fun rates, titles
  duration.py                       # parse_duration_to_minutes (90m, 1.5h, 1h20m)
  i18n.py                           # t(key, lang) + localize(lang, en, uk) — languages: en, uk
  messages.py                       # status_message, week_message formatters
  help_guides.py                    # guide page content, COMMAND_DESCRIPTIONS, HELP_TOPICS, GUIDE_PAGES
  shop.py / savings.py              # shop + savings logic
  shop_pricing.py                   # NOK-to-minutes conversion, web price extraction
  quests.py                         # quest generation + validation
  llm_router.py                     # legacy LLM routing (OpenAI/Anthropic/Google)
  llm_parser.py                     # free-form text → log entry via LLM
  llm_messages.py                   # level-up messages via LLM
  notion_backup.py                  # Notion snapshot backup
  jobs_runner.py                    # scheduled job implementations
  time_utils.py                     # timezone-aware now, week boundaries
  admin_app.py                      # FastAPI admin panel
  logging_setup.py                  # logging config

  agents/                           # V3 agent runtime
    execution/
      config.py                     # ModelConfig from agents/models.yaml, tier definitions
      llm_client.py                 # call_openrouter(), JSON response parsing
      loop.py                       # AgentLoop: max 6 steps, 4 tool calls, tier escalation
    orchestration/
      runner.py                     # run_llm_agent() — /llm entry point
      coach_runner.py               # run_coach_agent() — /coach entry point
      intent_router.py              # regex-based tool tag + skill resolution
    tools/
      base.py                       # Tool protocol, ToolContext, ToolResult
      registry.py                   # ToolRegistry with tag-based filtering
      db_query.py                   # DbQueryTool — SQL queries against user data
      insights.py                   # InsightsTool — derived coaching metrics
      memory.py                     # MemoryManageTool — save/list/delete coach memories
      search.py                     # WebSearchTool — Brave/Tavily/Serper fallback
      quest_propose.py              # QuestProposeTool — create quests via agent
      notion_mcp.py                 # NotionMcpTool — backup snapshots
      utils.py                      # shared tool utilities

agents/                             # top-level agent config (NOT under src/)
  models.yaml                       # tiered model policy (free / open_source_cheap / top_tier)
  directives/
    llm_assistant.md                # base directive for /llm agent
    coach.md                        # dedicated directive for /coach agent
    skills/                         # lazy-loaded skill fragments for /llm
      coach.md                      # coaching skill (triggered by "advice", "recommend")
      quest_builder.md              # quest creation skill
      research.md                   # multi-step research skill

tests/                              # pytest, plain functions + classes, tmp_path fixtures
```

## Architecture Patterns

### Handler Registration
All command handlers follow the same pattern: create a `register_*_handlers(app)` function, call it in `telegram_bot.py`. Order matters: `register_unknown_handler` must be last.

### Database
- SQLite with numbered migrations (currently 18) in `db.py`
- Migrations auto-run on `Database.__init__`
- All models are frozen dataclasses in `db_models.py`
- Row-to-model converters in `db_converters.py`
- All DB methods on the `Database` class in `db.py`

### Agent Runtime (V3)
Two entry points share the same `AgentLoop`:
- `/llm` → `runner.py:run_llm_agent()` — stateless, intent-routed tool filtering + skill composition
- `/coach` → `coach_runner.py:run_coach_agent()` — stateful with conversation history + long-term memory

Agent loop constraints:
- Max 6 steps, max 4 tool calls per request
- 1800 input tokens/step, 420 output tokens/step, 6000 total budget
- Tier escalation: free → open_source_cheap → top_tier (if enabled)
- All LLM calls go through OpenRouter API

Tool system:
- `Tool` protocol: `name`, `description`, `tags`, `run(args, ctx) → ToolResult`
- `ToolRegistry` with `filter_by_tags(set)` for per-request tool selection
- Tags determine which tools load: intent router resolves question → tag sets
- Skills add extra directive text + required tool tags based on keyword matching

### Economy
- Productive time (study/build/training/job) earns fun minutes at category-specific rates
- Fun time (`/spend`) costs fun minutes
- Shop items cost fun minutes, savings fund locks minutes for expensive items
- XP progression: quadratic scaling, level titles, level-up bonuses

### i18n
- Two approaches: `t(key, lang)` for dictionary-based, `localize(lang, en, uk)` for inline
- Languages: `en` (English), `uk` (Ukrainian)
- Help/guide content is English-only

### Help System
- `/help` → overview of all 21 commands
- `/help <topic>` → brief help + Guide button
- Guide button opens paginated walkthrough (edit_message_text + InlineKeyboard)
- 7 guides, 39 total pages, callback format: `guide:<topic>:<page>`

## Key Conventions

- **Frozen dataclasses** for all data models
- **No ORM** — raw SQL with parameterized queries
- **All times UTC-aware** via `zoneinfo` (default TZ: Europe/Oslo)
- **Tests**: plain pytest, no mocking frameworks (use monkeypatch), `tmp_path` for DB isolation
- **Settings**: single `Settings` dataclass from environment variables
- **Imports**: `from __future__ import annotations` in every file
- **Bot data**: `app.bot_data["db"]` and `app.bot_data["settings"]` set in `build_application()`
- **Rate limits**: 10 LLM requests/day shared between /llm and /coach, 30s cooldown

## Adding a New Command

1. Create `commands_<name>.py` with async handler + `register_<name>_handlers(app)`
2. Wire in `telegram_bot.py` (before `register_unknown_handler`)
3. Add entry to `COMMAND_DESCRIPTIONS` and `HELP_TOPICS` in `help_guides.py`
4. Add `TOPIC_ALIASES` entries if the command belongs to an existing guide
5. Add tests

## Adding a New Agent Tool

1. Create `agents/tools/<name>.py` implementing the `Tool` protocol
2. Register in `registry.py:build_default_registry()`
3. Choose tags that match intent router rules (or add new rules in `intent_router.py`)
4. Add tests in `tests/test_agent_data_tools.py` or a new test file

## Adding a New DB Migration

1. Add migration N+1 in `db.py` `_MIGRATIONS` list (currently at index 17 = migration 18)
2. Add model to `db_models.py`, converter to `db_converters.py`
3. Add methods to `Database` class in `db.py`
4. Migrations auto-run — no manual steps needed

## Environment Variables

Required: `TELEGRAM_BOT_TOKEN`, `DATABASE_PATH`
Agent features: `OPENROUTER_API_KEY`, `AGENT_MODELS_PATH`, `AGENT_DIRECTIVE_PATH`
Search: `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY` (at least one)
Optional: `NOTION_API_KEY`, `ADMIN_PANEL_TOKEN`, `TZ` (default: Europe/Oslo)

## Test Patterns

```python
# DB test pattern — use tmp_path for isolation
def test_something(tmp_path):
    db = Database(tmp_path / "app.db")
    # ... test with fresh DB

# Agent tool test pattern
def _ctx(db, tmp_path):
    return ToolContext(user_id=1, now=datetime(...), db=db, settings=_settings(tmp_path), config={})

# Monkeypatch agent loop for runner tests
def fake_run(self, req, ctx):
    return AgentRunResult(answer="...", model_used="test", steps=[], prompt_tokens=0, completion_tokens=0, status="ok")
monkeypatch.setattr("tg_time_logger.agents.execution.loop.AgentLoop.run", fake_run)
```
