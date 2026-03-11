from __future__ import annotations

from datetime import date

from tg_time_logger.db import Entry
from tg_time_logger.gamification import format_minutes_hm
from tg_time_logger.service import StatusView

NEGATIVE_WARNING = "Fun remaining is negative. Log productive time to earn more."

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _bar(ratio: float, width: int = 20) -> str:
    filled = max(0, min(width, int(round(ratio * width))))
    return "\u2588" * filled + "\u2591" * (width - filled)


def _weekly_chart(daily_totals: dict[date, int]) -> list[str]:
    if not daily_totals:
        return []
    max_minutes = max(daily_totals.values()) if daily_totals else 1
    max_minutes = max(max_minutes, 1)
    chart_width = 8
    lines: list[str] = []
    for day_date in sorted(daily_totals.keys()):
        mins = daily_totals[day_date]
        if mins <= 0:
            continue
        day_name = DAY_NAMES[day_date.weekday()]
        bar_len = max(1, round(mins / max_minutes * chart_width))
        bar = "\u2588" * bar_len
        lines.append(f"{day_name} {bar} {format_minutes_hm(mins)}")
    return lines


def status_message(view: StatusView, username: str | None = None) -> str:
    header = f"\U0001f4ca Status \u2014 @{username}" if username else "\U0001f4ca Status"

    pct = view.xp_progress_ratio * 100
    progress = f"{_bar(view.xp_progress_ratio)} {pct:.1f}%"

    cat_parts = []
    for key in ("study", "build", "training"):
        mins = view.week_categories.get(key, 0)
        if mins > 0:
            cat_parts.append(f"{key.capitalize()} {format_minutes_hm(mins)}")
    week_cats = " \u00b7 ".join(cat_parts) if cat_parts else "none"

    job_mins = view.week_categories.get("job", 0)
    job_line = f"\n       Job {format_minutes_hm(job_mins)}" if job_mins > 0 else ""

    chart_lines = _weekly_chart(view.daily_totals)
    chart_block = "\n".join(chart_lines) if chart_lines else "No entries yet"

    lines = [
        header,
        "",
        f"Level {view.level} \u00b7 {view.title} \u00b7 {view.xp_current_level}/{view.xp_next_level} XP",
        progress,
        f"\U0001f525 Streak: {view.streak_current} days ({view.streak_multiplier:.1f}x)",
        "",
        f"Today: {format_minutes_hm(view.today.productive_minutes)} productive",
        f"Week:  {week_cats}{job_line}",
        "",
        chart_block,
        "",
        f"\U0001f4b0 Fun: {view.economy.remaining_fun_minutes}m remaining",
    ]

    if view.economy.remaining_fun_minutes < 0:
        lines.append(f"\u26a0\ufe0f {NEGATIVE_WARNING}")

    return "\n".join(lines)


def entry_removed_message(entry: Entry) -> str:
    note = f" | note: {entry.note}" if entry.note else ""
    kind = f"{entry.kind} ({entry.category})" if entry.kind == "productive" else entry.kind
    return (
        f"Undid entry: {kind} {format_minutes_hm(entry.minutes)} "
        f"at {entry.created_at.strftime('%Y-%m-%d %H:%M')}{note}"
    )
