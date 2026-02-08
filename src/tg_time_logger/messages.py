from __future__ import annotations

from tg_time_logger.db import Entry
from tg_time_logger.economy import format_minutes_hm
from tg_time_logger.service import StatusView

NEGATIVE_WARNING = "⚠️ Limit reached. Fun remaining is negative. Log productive time to earn more."


def _fun_remaining_lines(fun_left_minutes: int) -> list[str]:
    if fun_left_minutes < 0:
        return [f"Fun remaining (all-time): {format_minutes_hm(-1)}", NEGATIVE_WARNING]
    return [f"Fun remaining (all-time): {format_minutes_hm(fun_left_minutes)}"]


def status_message(view: StatusView) -> str:
    e = view.economy
    lines = [
        "Status",
        *_fun_remaining_lines(e.fun_left_minutes),
        f"Today: productive {format_minutes_hm(view.today.productive_minutes)}, spent {format_minutes_hm(view.today.spent_minutes)}",
        f"This week: productive {format_minutes_hm(view.week.productive_minutes)}, spent {format_minutes_hm(view.week.spent_minutes)}",
        f"All-time: productive {format_minutes_hm(view.all_time.productive_minutes)}, spent {format_minutes_hm(view.all_time.spent_minutes)}",
        f"Fun earned: {format_minutes_hm(e.earned_fun_minutes)} (base {format_minutes_hm(e.base_fun_minutes)} + bonus {format_minutes_hm(e.bonus_fun_minutes)})",
        f"Milestone blocks: {e.bonus_blocks} x 10h",
    ]
    return "\n".join(lines)


def week_message(view: StatusView) -> str:
    lines = [
        "Week",
        f"Productive: {format_minutes_hm(view.week.productive_minutes)}",
        f"Spent: {format_minutes_hm(view.week.spent_minutes)}",
        *_fun_remaining_lines(view.economy.fun_left_minutes),
    ]
    return "\n".join(lines)


def entry_removed_message(entry: Entry) -> str:
    note = f" | note: {entry.note}" if entry.note else ""
    return (
        f"Undid entry: {entry.kind} {format_minutes_hm(entry.minutes)}"
        f" at {entry.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{note}"
    )
