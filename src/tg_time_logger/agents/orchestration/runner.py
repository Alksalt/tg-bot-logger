from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.execution.loop import AgentLoop, AgentRequest
from tg_time_logger.agents.orchestration.intent_router import SKILL_DEFS, resolve_intent
from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.registry import ToolRegistry, build_default_registry
from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.service import compute_status


def _load_directive(path: Path) -> str:
    if path.exists():
        text = path.read_text().strip()
        if text:
            return text
    return "Be accurate, concise, and use tools only when needed."


def _load_skill_directive(path: Path) -> str | None:
    if path.exists():
        text = path.read_text().strip()
        return text if text else None
    return None


def build_agent_context_text(db: Database, user_id: int, now: datetime) -> str:
    view = compute_status(db, user_id, now)
    return (
        f"Level: {view.level} ({view.title})\n"
        f"XP total: {view.xp_total}, week: {view.xp_week}, to next: {view.xp_remaining_to_next}\n"
        f"Streak: {view.streak_current}, best: {view.streak_longest}\n"
        f"Week productive: {view.week.productive_minutes}m, week spent: {view.week.spent_minutes}m\n"
        f"Plan: {view.week_plan_done_minutes}/{view.week_plan_target_minutes}m\n"
        f"Fun remaining: {view.economy.remaining_fun_minutes}m\n"
        f"Active quests: {view.active_quests}"
    )


def run_llm_agent(
    *,
    db: Database,
    settings: Settings,
    user_id: int,
    now: datetime,
    question: str,
    tier_override: str | None = None,
) -> dict[str, Any]:
    cfg = db.get_app_config()
    if not db.is_feature_enabled("agent"):
        return {
            "ok": False,
            "answer": "Agent runtime is disabled by admin.",
            "model": "none",
            "steps": [],
        }

    model_cfg = load_model_config(settings.agent_models_path)
    requested_tier = tier_override or str(cfg.get("agent.default_tier", model_cfg.default_tier))
    directive = _load_directive(settings.agent_directive_path)
    context_text = build_agent_context_text(db, user_id, now)

    # Two-phase tool resolution: only load tools relevant to the question
    full_registry = build_default_registry()
    intent = resolve_intent(question)
    matched_tags = set(intent.tool_tags)
    matched_skills = list(intent.skills)

    # Merge skill-required tool tags + compose skill directive fragments
    directives_dir = settings.agent_directive_path.parent
    for skill_name in matched_skills:
        skill_def = SKILL_DEFS.get(skill_name)
        if skill_def:
            matched_tags.update(skill_def.required_tool_tags)
            skill_text = _load_skill_directive(directives_dir / skill_def.directive_file)
            if skill_text:
                directive += f"\n\n## Active Skill: {skill_name}\n{skill_text}"

    if matched_tags:
        registry = full_registry.filter_by_tags(matched_tags)
    else:
        registry = ToolRegistry()  # empty — agent answers from context only
    loaded_specs = registry.list_specs()
    loaded_tool_names = [spec["name"] for spec in loaded_specs]

    loop = AgentLoop(
        model_config=model_cfg,
        api_key=settings.openrouter_api_key,
        registry=registry,
        app_config=cfg,
    )
    req = AgentRequest(
        question=question,
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
    tool_steps = sum(1 for s in result.steps if s.get("type") == "tool")
    schema_errors = sum(1 for s in result.steps if s.get("type") == "schema_error")
    parse_errors = sum(1 for s in result.steps if s.get("type") == "parse_error")
    db.add_admin_audit(
        actor=f"user:{user_id}",
        action="agent.run",
        target="llm",
        payload={
            "status": result.status,
            "model": result.model_used,
            "tier": requested_tier,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "matched_tags": sorted(matched_tags),
            "matched_skills": matched_skills,
            "loaded_tools_count": len(loaded_tool_names),
            "loaded_tools": loaded_tool_names,
            "question_length": len(question),
            "steps": len(result.steps),
            "tool_steps": tool_steps,
            "schema_errors": schema_errors,
            "parse_errors": parse_errors,
        },
        created_at=now,
    )
    return {
        "ok": True,
        "answer": result.answer,
        "model": result.model_used,
        "steps": result.steps,
        "tier": requested_tier,
        "status": result.status,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "matched_tags": sorted(matched_tags),
        "matched_skills": matched_skills,
        "loaded_tools_count": len(loaded_tool_names),
        "loaded_tools": loaded_tool_names,
    }


def run_search_tool(
    *,
    db: Database,
    settings: Settings,
    user_id: int,
    now: datetime,
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    reg = build_default_registry()
    tool = reg.get("web_search")
    if not tool:
        return {"ok": False, "content": "web_search tool not found", "metadata": {}}
    ctx = ToolContext(user_id=user_id, now=now, db=db, settings=settings, config=db.get_app_config())
    result = tool.run({"query": query, "max_results": max_results}, ctx)
    db.add_admin_audit(
        actor=f"user:{user_id}",
        action="agent.search",
        target="web_search",
        payload={
            "ok": result.ok,
            "provider": result.metadata.get("provider"),
            "cached": result.metadata.get("cached"),
            "query_len": len(query),
        },
        created_at=now,
    )
    return {"ok": result.ok, "content": result.content, "metadata": result.metadata}
