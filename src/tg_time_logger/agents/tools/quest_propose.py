from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.quests import ALLOWED_CONDITION_TYPES, _validate_llm_quest, _weekly_stats
from tg_time_logger.time_utils import week_range_for

_MAX_ACTIVE_QUESTS = 5


class QuestProposeTool(Tool):
    name = "quest_propose"
    description = (
        "Validate and insert a new quest. "
        "Args: {\"title\": str, \"description\": str, \"quest_type\": str, "
        "\"difficulty\": \"easy|medium|hard\", "
        "\"condition\": {\"type\": \"<condition_type>\", ...}}. "
        f"Allowed condition types: {', '.join(sorted(ALLOWED_CONDITION_TYPES))}."
    )
    tags = ("quest", "gamification")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        title = str(args.get("title", "")).strip()
        if not title:
            return ToolResult(
                ok=False,
                content="Missing required field: title.",
                metadata={"action": "quest_propose"},
            )

        # 1. Check active quest count
        active = ctx.db.list_active_quests(ctx.user_id, ctx.now)
        if len(active) >= _MAX_ACTIVE_QUESTS:
            return ToolResult(
                ok=False,
                content=f"Too many active quests ({len(active)}/{_MAX_ACTIVE_QUESTS}). Complete or wait for some to expire.",
                metadata={"action": "quest_propose", "active_count": len(active)},
            )

        # 2. Check title not in recent quests (14 days)
        week = week_range_for(ctx.now)
        recent_titles = ctx.db.list_recent_quest_titles(
            ctx.user_id, since=week.start - timedelta(days=14)
        )
        if title in recent_titles:
            return ToolResult(
                ok=False,
                content=f"Quest title '{title}' was used in the last 14 days. Choose a different title.",
                metadata={"action": "quest_propose", "duplicate_title": title},
            )

        # 3. Get user stats and validate via existing quest validation
        prev_start = week.start - timedelta(days=7)
        stats = _weekly_stats(ctx.db, ctx.user_id, prev_start, week.start)
        rng = random.Random(f"{ctx.user_id}:{ctx.now.date().isoformat()}")
        validated = _validate_llm_quest(args, stats, rng)
        if validated is None:
            return ToolResult(
                ok=False,
                content=(
                    "Quest validation failed. Ensure: title and description are non-empty, "
                    f"condition.type is one of {', '.join(sorted(ALLOWED_CONDITION_TYPES))}, "
                    "and condition has the required fields for its type."
                ),
                metadata={"action": "quest_propose"},
            )

        # 4. Insert quest
        expires_at = week.end - timedelta(seconds=1)
        quest = ctx.db.insert_quest(
            user_id=ctx.user_id,
            title=validated["title"],
            description=validated["description"],
            quest_type=validated["quest_type"],
            difficulty=validated["difficulty"],
            reward_fun_minutes=validated["reward"],
            condition=validated["condition"],
            expires_at=expires_at,
            created_at=ctx.now,
        )

        return ToolResult(
            ok=True,
            content=(
                f"Quest created: [{validated['difficulty']}] {validated['title']} — "
                f"{validated['description']} "
                f"(reward: {validated['reward']}m fun, expires {expires_at.date().isoformat()})"
            ),
            metadata={
                "action": "quest_propose",
                "quest_id": quest.id,
                "title": validated["title"],
                "difficulty": validated["difficulty"],
                "reward": validated["reward"],
            },
        )
