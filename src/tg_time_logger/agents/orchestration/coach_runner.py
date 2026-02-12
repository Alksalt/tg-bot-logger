from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.execution.loop import AgentLoop, AgentRequest
from tg_time_logger.agents.orchestration.runner import build_agent_context_text
from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.registry import build_default_registry
from tg_time_logger.config import Settings
from tg_time_logger.db import Database

_COACH_DIRECTIVE_FILE = "coach.md"
_HISTORY_TURNS = 8
_HISTORY_KEEP_DB = 20
_MEMORY_CONTEXT_LIMIT = 15
_COACH_TOOL_TAGS = frozenset({
    "data", "stats", "history",
    "analytics", "insights",
    "memory", "coach",
})


def _load_coach_directive(directives_dir: Path) -> str:
    path = directives_dir / _COACH_DIRECTIVE_FILE
    if path.exists():
        text = path.read_text().strip()
        if text:
            return text
    return (
        "You are a supportive, data-driven personal productivity coach. "
        "Use conversation history and user memories to give personalized advice."
    )


def _build_conversation_history_text(db: Database, user_id: int) -> str:
    messages = db.list_coach_messages(user_id, limit=_HISTORY_TURNS)
    if not messages:
        return ""
    lines = ["Recent conversation:"]
    for msg in messages:
        prefix = "You" if msg.role == "assistant" else "User"
        text = msg.content[:240]
        if len(msg.content) > 240:
            text += "..."
        lines.append(f"{prefix}: {text}")
    return "\n".join(lines)


def _build_memory_context_text(db: Database, user_id: int) -> str:
    memories = db.list_coach_memories(user_id, limit=_MEMORY_CONTEXT_LIMIT)
    if not memories:
        return ""
    lines = ["Known about user:"]
    for mem in memories:
        tag_text = f" [{mem.tags}]" if mem.tags else ""
        text = mem.content[:200]
        lines.append(f"- ({mem.category}{tag_text}) {text}")
    return "\n".join(lines)


def run_coach_agent(
    *,
    db: Database,
    settings: Settings,
    user_id: int,
    now: datetime,
    message: str,
    tier_override: str | None = None,
) -> dict[str, Any]:
    """Run the coach agent with conversation context and memory."""
    cfg = db.get_app_config()
    if not db.is_feature_enabled("agent"):
        return {
            "ok": False,
            "answer": "Agent runtime is disabled by admin.",
            "model": "none",
            "steps": [],
        }

    # 1. Save user message to conversation history
    db.add_coach_message(user_id, "user", message, now)

    # 2. Load model config and directive
    model_cfg = load_model_config(settings.agent_models_path)
    requested_tier = tier_override or str(
        cfg.get("agent.default_tier", model_cfg.default_tier)
    )
    directives_dir = settings.agent_directive_path.parent
    directive = _load_coach_directive(directives_dir)

    # 3. Build enriched context: stats + memories + conversation history
    stats_text = build_agent_context_text(db, user_id, now)
    memory_text = _build_memory_context_text(db, user_id)
    history_text = _build_conversation_history_text(db, user_id)

    context_parts = [stats_text]
    if memory_text:
        context_parts.append(memory_text)
    if history_text:
        context_parts.append(history_text)
    context_text = "\n\n".join(context_parts)

    # 4. Build filtered registry with coach-relevant tools
    full_registry = build_default_registry()
    registry = full_registry.filter_by_tags(set(_COACH_TOOL_TAGS))
    loaded_specs = registry.list_specs()
    loaded_tool_names = [spec["name"] for spec in loaded_specs]

    # 5. Run agent loop
    loop = AgentLoop(
        model_config=model_cfg,
        api_key=settings.openrouter_api_key,
        registry=registry,
        app_config=cfg,
        api_keys={
            "openai": settings.openai_api_key,
            "google": settings.google_api_key,
            "anthropic": settings.anthropic_api_key,
        },
    )
    req = AgentRequest(
        question=message,
        context_text=context_text,
        directive_text=directive,
        requested_tier=requested_tier,
        allow_tier_escalation=True,
    )
    tool_ctx = ToolContext(
        user_id=user_id,
        now=now,
        db=db,
        settings=settings,
        config=cfg,
    )
    result = loop.run(req, tool_ctx)

    # 6. Save assistant response
    answer = result.answer.strip()
    if answer:
        db.add_coach_message(user_id, "assistant", answer, now)

    # 7. Prune old messages
    db.prune_coach_messages(user_id, keep=_HISTORY_KEEP_DB)

    # 8. Audit log
    tool_steps = sum(1 for s in result.steps if s.get("type") == "tool")
    db.add_admin_audit(
        actor=f"user:{user_id}",
        action="agent.coach",
        target="coach",
        payload={
            "status": result.status,
            "model": result.model_used,
            "tier": requested_tier,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "loaded_tools": loaded_tool_names,
            "steps": len(result.steps),
            "tool_steps": tool_steps,
            "question_length": len(message),
        },
        created_at=now,
    )

    return {
        "ok": True,
        "answer": answer,
        "model": result.model_used,
        "steps": result.steps,
        "tier": requested_tier,
        "status": result.status,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "loaded_tools": loaded_tool_names,
    }
