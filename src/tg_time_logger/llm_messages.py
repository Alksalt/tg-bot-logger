from __future__ import annotations

from dataclasses import dataclass

from tg_time_logger.gamification import get_title
from tg_time_logger.llm_router import LlmRoute, call_text


@dataclass(frozen=True)
class LlmContext:
    enabled: bool
    route: LlmRoute


def _call(ctx: LlmContext, prompt: str, max_tokens: int) -> str | None:
    if not ctx.enabled:
        return None
    return call_text(ctx.route, prompt, max_tokens=max_tokens)


def level_up_message(
    ctx: LlmContext,
    level: int,
    total_hours: float,
    bonus: int,
    xp_remaining: int,
    top_category: str,
) -> str:
    prompt = (
        "You are a motivational gaming coach. The user just leveled up in their productivity tracker.\n\n"
        f"Facts:\n- New level: {level}\n- Title: {get_title(level)}\n"
        f"- Total productive hours: {total_hours:.1f}\n- Bonus earned: {bonus} fun minutes\n"
        f"- XP to next level: {xp_remaining}\n- Their most logged category this week: {top_category}\n\n"
        "Write a short (2-3 sentences) enthusiastic congratulations message. "
        "Be specific to their level and progress. Reference their top activity. Use 1-2 emojis."
    )
    text = _call(ctx, prompt, max_tokens=150)
    if text:
        return text
    return (
        f"🎉 LEVEL UP! You reached Level {level} — {get_title(level)}!\n\n"
        f"+{bonus} fun minutes earned!\n"
        f"You've logged {total_hours:.1f}h productive time. Next level in {xp_remaining} XP. Keep pushing! 💪"
    )


def weekly_summary_message(ctx: LlmContext, facts: str) -> str:
    prompt = (
        "You are a productivity coach analyzing a player's weekly performance in a gamified time tracker.\n\n"
        f"Weekly data:\n{facts}\n\n"
        "Write a personalized 3-5 sentence weekly summary with one highlight and one actionable suggestion. "
        "Use at most 3 emojis."
    )
    text = _call(ctx, prompt, max_tokens=300)
    if text:
        return text
    return "Solid week. Keep the momentum by scheduling one long deep-work block early in the week and protecting your streak."


def short_event_message(ctx: LlmContext, event_prompt: str, fallback: str) -> str:
    text = _call(ctx, event_prompt, max_tokens=150)
    return text or fallback
