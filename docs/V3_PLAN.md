# V3.0 Plan (Agent Platform)

## Goals

- Build an agentic `/llm` runtime with looped reasoning and tool use.
- Use free OpenRouter models first, then cheap open-source, then top tier.
- Add provider-fallback web search (Brave, Tavily, Serper) with cache + dedupe.
- Keep architecture simple and reproducible:
  - `Directive` = human SOP/spec.
  - `Execution` = deterministic code.
  - `Orchestration` = thin runner with no business logic.
- Keep server-first deployment model.

## Proposed Structure

- `agents/directives/` human-readable SOPs for agents.
- `agents/execution/` deterministic runtime components:
  - model routing
  - loop engine
  - tool contracts
  - search clients
  - caching logic
- `agents/orchestration/` thin entrypoint functions:
  - convert request/context into runtime inputs
  - call loop
  - return final answer + trace
- `agents/tools/` tool implementations and registry.
- `agents/models.yaml` tiered model policy.
- `TOOLS.md` tool manifest and usage policy.

## Model Policy

- Tier 1 (`free`) from `OPENROUTER_MODELS.md`.
- Tier 2 (`open_source_cheap`) from `MODELS.md` and OpenRouter low-cost open models.
- Tier 3 (`top_tier`) from `MODELS.md`.
- Runtime fallback:
  - try models within tier order
  - fail over tier-by-tier only when requested
  - easy tier switch via config.

## Search Policy

- Unified search tool API with provider fallback:
  - Brave -> Tavily -> Serper.
- Per-query dedupe + TTL cache in SQLite.
- Return concise snippets + links for token efficiency.

## Incremental Milestones

1. Agent skeleton + `/llm` integration.
2. Search tool with fallback + cache + dedupe.
3. Tiered model router + reasoning toggles.
4. Tool registry extensibility (Notion MCP scaffold, mail/maps placeholders).
5. Prompt/trace observability and guardrails.

## Out of Scope (for this pass)

- Full Notion sync implementation.
- Full MCP protocol server integration.
- Multilingual UX polish (Ukrainian) beyond architecture readiness.
