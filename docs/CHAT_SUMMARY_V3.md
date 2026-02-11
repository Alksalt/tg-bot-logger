# Chat Summary (Context Compression)

## Product State

- Telegram time logger is functional and actively used.
- Commands, economy, quests, timers, admin panel, and scheduled jobs are already implemented.
- User requested progression into V3 agent platform.

## Decisions Agreed

- Use agentic loops + reasoning.
- Prefer free OpenRouter models first, then cheap open/open-source, then top tier.
- Keep easy model-tier switching.
- Implement web search as a real tool (not only for shop prices):
  - Brave
  - Tavily
  - Serper
  - provider fallback + cache + dedupe.
- Keep a dedicated `agents/` structure with:
  - directive/spec
  - deterministic execution
  - thin orchestration.
- Server-first deployment.
- Build extensible tool architecture so more tools can be added later (Notion MCP, mail, maps, APIs).
- Keep a `TOOLS.md` manifest for token-efficient tool usage.
- Ukrainian support considered for later phase.

## Current Request

1. Backup current structure and push backup.
2. Plan V3 architecture.
3. Summarize chat to reduce future context load.
4. Build V3 scaffold now.
