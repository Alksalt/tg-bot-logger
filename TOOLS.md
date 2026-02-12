# TOOLS.md

Tool manifest for the V3 agent runtime.

## Active Tools

1. `db_query`
- Purpose: query user's tracked data (hours, entries, totals, comparisons).
- Actions: `week_totals`, `recent_entries`, `daily_breakdown`, `category_breakdown`, `note_keyword_sum`.
- Tags: `data`, `stats`, `history`.

2. `insights`
- Purpose: derived coaching metrics (consistency, patterns, streaks, bottlenecks).
- Actions: `consistency`, `category_trends`, `deep_work_rate`, `streak_analysis`.
- Tags: `analytics`, `insights`.

3. `memory_manage`
- Purpose: save, list, or delete long-term user memories for the coach.
- Actions: `save` (category + content), `list` (optional category filter), `delete` (by ID).
- Categories: preference, goal, fact, context.
- Tags: `memory`, `coach`. Only loaded by `/coach`, invisible to `/llm`.

4. `web_search`
- Purpose: fetch current web information.
- Inputs: `query` (string), `max_results` (optional int, default 5).
- Providers with fallback: Brave -> Tavily -> Serper.
- Tags: `search`, `web`.

5. `quest_propose`
- Purpose: create new quests via the agent.
- Inputs: `title`, `difficulty`, `condition_type`, `condition_value`, `reward_minutes`.
- Tags: `quest`, `gamification`.

6. `notion_mcp`
- Purpose: create local backup snapshots for Notion sync.
- Inputs: `mode="backup_now"`, optional `user_id`.
- Tags: `notion`, `backup`.

## Scaffolded (not implemented)

7. `mail_api` — future mail automation. Tags: `communication`, `mail`.
8. `maps_api` — future geocoding/routing. Tags: `maps`, `location`.
9. `custom_http_api` — future generic API connector. Tags: `http`, `api`.

## Usage Policy

- Prefer deterministic local data before external tools.
- Use tools only when needed.
- Deduplicate repeated queries in one run.
- Keep tool output summarized and link-focused.
