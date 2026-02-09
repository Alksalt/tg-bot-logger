from __future__ import annotations

from tg_time_logger.db import Entry
from tg_time_logger.gamification import format_minutes_hm
from tg_time_logger.service import StatusView

NEGATIVE_WARNING = "⚠️ Limit reached. Fun remaining is negative. Log productive time to earn more."

CATEGORY_LABELS = {
    "study": "📚 Study",
    "build": "🔨 Build",
    "training": "🏋️ Training",
    "job": "💼 Job",
}


def _bar(ratio: float, width: int = 20) -> str:
    filled = max(0, min(width, int(round(ratio * width))))
    return "█" * filled + "░" * (width - filled)


def _fun_remaining_lines(value: int) -> list[str]:
    if value < 0:
        return [f"Remaining: {format_minutes_hm(-1)}", NEGATIVE_WARNING]
    return [f"Remaining: {format_minutes_hm(value)}"]


def status_message(view: StatusView, username: str | None = None) -> str:
    header = f"📊 Status — @{username}" if username else "📊 Status"
    lines = [
        header,
        "",
        f"⚡ Level {view.level} — {view.title}",
        f"📊 XP: {view.xp_current_level:,} / {view.xp_next_level:,} (to Level {view.level + 1})",
        f"{_bar(view.xp_progress_ratio)} {view.xp_progress_ratio * 100:.1f}%",
        f"🔥 Streak: {view.streak_current} days ({view.streak_multiplier:.1f}x XP) | Best: {view.streak_longest}",
        "",
        "📅 This week (Mon–Sun):",
    ]

    for key in ("study", "build", "training", "job"):
        minutes = view.week_categories.get(key, 0)
        fun = (minutes * (15 if key == "study" else 4 if key == "job" else 20)) // 60
        lines.append(f"  {CATEGORY_LABELS[key]}: {format_minutes_hm(minutes)} → +{fun} fun")

    lines.extend(
        [
            f"  📊 Total: {format_minutes_hm(view.week.productive_minutes)} | XP: +{view.xp_week}",
            "",
            "💰 Fun Economy:",
            (
                f"  Earned: {view.economy.base_fun_minutes} (base) + "
                f"{view.economy.milestone_bonus_minutes} (10h milestone) + "
                f"{view.economy.level_bonus_minutes} (lvl bonus) + "
                f"{view.economy.quest_bonus_minutes} (quest) + "
                f"{view.economy.wheel_bonus_minutes} (wheel)"
            ),
            f"  Spent: -{view.economy.spent_fun_minutes} min",
            f"  Saved: -{view.economy.saved_fun_minutes} min",
            *_fun_remaining_lines(view.economy.remaining_fun_minutes),
            "",
            f"⚔️ Active Quests: {view.active_quests}",
        ]
    )
    return "\n".join(lines)


def week_message(view: StatusView) -> str:
    lines = [
        "📅 Week",
        f"Productive: {format_minutes_hm(view.week.productive_minutes)}",
        f"Spent: {format_minutes_hm(view.week.spent_minutes)}",
        f"XP this week: {view.xp_week}",
        f"Deep work sessions (90m+): {view.deep_sessions_week}",
        *_fun_remaining_lines(view.economy.remaining_fun_minutes),
    ]
    return "\n".join(lines)


def entry_removed_message(entry: Entry) -> str:
    note = f" | note: {entry.note}" if entry.note else ""
    kind = f"{entry.kind} ({entry.category})" if entry.kind == "productive" else entry.kind
    return (
        f"Undid entry: {kind} {format_minutes_hm(entry.minutes)}"
        f" at {entry.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{note}"
    )
