# TOOLS.md

Tool manifest for the V3 agent runtime. Keep this short to reduce token usage in prompts.

## Active tools

1. `web_search`
- Purpose: fetch current web information.
- Inputs: `query` (string), `max_results` (optional int, default 5).
- Providers with fallback: Brave -> Tavily -> Serper.
- Behavior: cached + deduped query responses (SQLite cache).

1. `notion_mcp`
- Purpose: create local backup snapshots that are ready for Notion sync.
- Inputs: `mode="backup_now"`, optional `user_id`.
- Behavior: writes JSON snapshot under `NOTION_BACKUP_DIR`; remote sync remains scaffold-only.

## Scaffolded (not implemented yet)

2. `mail_api`
- Future mail automation tool (draft/send/status).

3. `maps_api`
- Future geocoding/routing lookup tool.

4. `custom_http_api`
- Future generic API connector for app integrations.

## Usage policy

- Prefer deterministic local data before external tools.
- Use tools only when needed.
- Deduplicate repeated queries in one run.
- Keep tool output summarized and link-focused.
