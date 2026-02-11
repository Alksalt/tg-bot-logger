from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.db_constants import STREAK_MINUTES_REQUIRED
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, format_minutes_hm
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import week_range_for


def _safe_int(raw: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    return max(min_value, min(max_value, value))


def _as_local(dt: datetime, tz) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _daterange(start: date, end_exclusive: date) -> list[date]:
    days: list[date] = []
    current = start
    while current < end_exclusive:
        days.append(current)
        current += timedelta(days=1)
    return days


def _consistency_section(ctx: ToolContext, target_minutes: int) -> tuple[str, dict[str, Any]]:
    end_exclusive = ctx.now.date() + timedelta(days=1)
    start_date = end_exclusive - timedelta(days=30)
    totals = ctx.db.daily_totals(
        user_id=ctx.user_id,
        kind="productive",
        start_date=start_date,
        end_date_exclusive=end_exclusive,
    )
    days = _daterange(start_date, end_exclusive)
    hits = sum(1 for d in days if totals.get(d, 0) >= target_minutes)
    score = (hits / len(days)) * 100.0 if days else 0.0
    line = (
        f"Consistency (30d): {score:.1f}% "
        f"({hits}/{len(days)} days at >= {target_minutes}m productive)"
    )
    return line, {"hits": hits, "days": len(days), "score": score, "target_minutes": target_minutes}


def _pattern_section(ctx: ToolContext) -> tuple[str, dict[str, Any]]:
    end_exclusive = ctx.now.date() + timedelta(days=1)
    start_date = end_exclusive - timedelta(days=84)
    totals = ctx.db.daily_totals(
        user_id=ctx.user_id,
        kind="productive",
        start_date=start_date,
        end_date_exclusive=end_exclusive,
    )
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_totals = {name: 0 for name in weekday_names}
    for day, minutes in totals.items():
        weekday_totals[weekday_names[day.weekday()]] += minutes
    best_weekday = max(weekday_totals, key=lambda k: weekday_totals[k])

    bucket_totals = {"morning": 0, "afternoon": 0, "evening": 0, "night": 0}
    cutoff = ctx.now - timedelta(days=84)
    entries = ctx.db.list_recent_entries(ctx.user_id, limit=1000)
    for entry in entries:
        created_at = _as_local(entry.created_at, ctx.now.tzinfo)
        if entry.kind != "productive" or created_at < cutoff:
            continue
        hour = created_at.hour
        if 5 <= hour < 12:
            bucket_totals["morning"] += entry.minutes
        elif 12 <= hour < 18:
            bucket_totals["afternoon"] += entry.minutes
        elif 18 <= hour < 24:
            bucket_totals["evening"] += entry.minutes
        else:
            bucket_totals["night"] += entry.minutes
    best_bucket = max(bucket_totals, key=lambda k: bucket_totals[k])
    line = (
        "Patterns (12w): "
        f"best weekday {best_weekday} ({format_minutes_hm(weekday_totals[best_weekday])}), "
        f"best daypart {best_bucket} ({format_minutes_hm(bucket_totals[best_bucket])})"
    )
    return line, {"best_weekday": best_weekday, "best_daypart": best_bucket}


def _velocity_section(ctx: ToolContext, category: str | None = None) -> tuple[str, dict[str, Any]]:
    current_start = week_range_for(ctx.now).start
    previous_start = current_start - timedelta(days=7)
    previous_end = current_start
    categories = [category] if category else list(PRODUCTIVE_CATEGORIES)
    rows: list[tuple[str, int, int, int]] = []
    for cat in categories:
        if cat not in PRODUCTIVE_CATEGORIES:
            continue
        current = ctx.db.sum_minutes(
            ctx.user_id,
            "productive",
            start=current_start,
            end=ctx.now,
            category=cat,
        )
        previous = ctx.db.sum_minutes(
            ctx.user_id,
            "productive",
            start=previous_start,
            end=previous_end,
            category=cat,
        )
        rows.append((cat, current, previous, current - previous))
    if not rows:
        return "Category velocity: no data.", {"rows": 0}

    top_up = max(rows, key=lambda row: row[3])
    top_down = min(rows, key=lambda row: row[3])
    all_parts = [f"{cat}: {format_minutes_hm(cur)} vs {format_minutes_hm(prev)} ({format_minutes_hm(delta)})" for cat, cur, prev, delta in rows]
    line = (
        "Category velocity (this week vs last): "
        f"up {top_up[0]} {format_minutes_hm(top_up[3])}, "
        f"down {top_down[0]} {format_minutes_hm(top_down[3])}. "
        + "; ".join(all_parts)
    )
    return line, {"rows": len(rows), "top_up": top_up[0], "top_down": top_down[0]}


def _streak_risk_section(ctx: ToolContext) -> tuple[str, dict[str, Any]]:
    streak = ctx.db.get_streak(ctx.user_id, ctx.now)
    today_minutes = ctx.db.productive_minutes_for_date(ctx.user_id, ctx.now.date())
    missing = max(STREAK_MINUTES_REQUIRED - today_minutes, 0)
    if missing <= 0:
        risk = "low"
    elif ctx.now.hour >= 21:
        risk = "high"
    elif ctx.now.hour >= 18:
        risk = "medium"
    else:
        risk = "low"
    line = (
        f"Streak risk: {risk} (current {streak.current_streak}, best {streak.longest_streak}, "
        f"today {format_minutes_hm(today_minutes)}, missing {format_minutes_hm(missing)} to protect streak)"
    )
    return line, {"risk": risk, "missing_minutes": missing, "current_streak": streak.current_streak}


def _economy_health_section(ctx: ToolContext) -> tuple[str, dict[str, Any]]:
    start = ctx.now - timedelta(days=14)
    earned = ctx.db.sum_fun_earned_entries(ctx.user_id, start=start, end=ctx.now)
    spent = ctx.db.sum_minutes(ctx.user_id, "spend", start=start, end=ctx.now)
    net = earned - spent
    ratio = None if spent <= 0 else (earned / spent)
    status = compute_status(ctx.db, ctx.user_id, ctx.now)
    ratio_text = "n/a" if ratio is None else f"{ratio:.2f}x"
    line = (
        "Economy health (14d): "
        f"earn {format_minutes_hm(earned)}, burn {format_minutes_hm(spent)}, net {format_minutes_hm(net)}, "
        f"earn/burn {ratio_text}, remaining all-time {format_minutes_hm(status.economy.remaining_fun_minutes)}"
    )
    return line, {"earned": earned, "spent": spent, "net": net, "ratio": ratio}


class InsightsTool(Tool):
    name = "insights"
    description = (
        "Compute derived analytics from tracker data. "
        "Args: {\"focus\": \"consistency|patterns|velocity|streak|economy\" (optional), "
        "\"target_minutes\": int (optional), \"category\": str (optional)}"
    )
    tags = ("analytics", "insights")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        focus = str(args.get("focus", "")).strip().lower()
        target_minutes = _safe_int(args.get("target_minutes", 120), default=120, min_value=1, max_value=720)
        category_raw = str(args.get("category", "")).strip().lower()
        category = category_raw if category_raw else None

        sections: dict[str, tuple[str, dict[str, Any]]] = {
            "consistency": _consistency_section(ctx, target_minutes),
            "patterns": _pattern_section(ctx),
            "velocity": _velocity_section(ctx, category=category),
            "streak": _streak_risk_section(ctx),
            "economy": _economy_health_section(ctx),
        }

        if focus and focus in sections:
            line, payload = sections[focus]
            return ToolResult(
                ok=True,
                content=line,
                metadata={"focus": focus, "details": payload},
            )
        if focus and focus not in sections:
            return ToolResult(
                ok=False,
                content=f"Unknown focus '{focus}'. Use one of: {', '.join(sections.keys())}",
                metadata={"focus": focus},
            )

        ordered = ["consistency", "patterns", "velocity", "streak", "economy"]
        lines = ["Insights snapshot:"]
        metadata: dict[str, Any] = {}
        for key in ordered:
            line, payload = sections[key]
            lines.append(f"- {line}")
            metadata[key] = payload
        return ToolResult(ok=True, content="\n".join(lines), metadata=metadata)
