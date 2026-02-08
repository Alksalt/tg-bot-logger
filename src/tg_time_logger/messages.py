from __future__ import annotations

from tg_time_logger.db import Entry, PlanTarget
from tg_time_logger.economy import format_minutes_hm
from tg_time_logger.service import StatusView


def status_message(view: StatusView) -> str:
    e = view.economy
    return "\n".join(
        [
            "Status",
            f"Today: productive {format_minutes_hm(view.today.productive_minutes)}, spent {format_minutes_hm(view.today.spent_minutes)}",
            f"This week: productive {format_minutes_hm(view.week.productive_minutes)}, spent {format_minutes_hm(view.week.spent_minutes)}",
            f"All-time: productive {format_minutes_hm(view.all_time.productive_minutes)}, spent {format_minutes_hm(view.all_time.spent_minutes)}",
            f"Fun earned: {format_minutes_hm(e.earned_fun_minutes)} (base {format_minutes_hm(e.base_fun_minutes)} + bonus {format_minutes_hm(e.bonus_fun_minutes)})",
            f"Milestone blocks: {e.bonus_blocks} x 10h",
            f"Fun left: {format_minutes_hm(e.fun_left_minutes)}",
        ]
    )


def week_message(view: StatusView, plan: PlanTarget | None, by_category: dict[str, int]) -> str:
    lines = [
        "Week",
        f"Productive: {format_minutes_hm(view.week.productive_minutes)}",
        f"Spent: {format_minutes_hm(view.week.spent_minutes)}",
        f"Fun left (all-time): {format_minutes_hm(view.economy.fun_left_minutes)}",
        "Category totals: "
        + ", ".join(f"{k} {format_minutes_hm(v)}" for k, v in by_category.items()),
    ]
    if plan:
        lines.append("Plan target:")
        for category in ("work", "study", "learn"):
            target = getattr(plan, f"{category}_minutes")
            done = by_category.get(category, 0)
            remaining = max(target - done, 0)
            lines.append(
                f"- {category}: {format_minutes_hm(done)} / {format_minutes_hm(target)} (remaining {format_minutes_hm(remaining)})"
            )
    return "\n".join(lines)


def entry_removed_message(entry: Entry) -> str:
    cat = f" {entry.category}" if entry.category else ""
    note = f" | note: {entry.note}" if entry.note else ""
    return (
        f"Undid entry: {entry.entry_type}{cat} {format_minutes_hm(entry.minutes)}"
        f" at {entry.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{note}"
    )
