from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, format_minutes_hm
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import week_range_for

_SUPPORTED_ACTIONS = (
    "weekly_breakdown",
    "category_trend",
    "recent_entries",
    "quest_history",
    "economy_breakdown",
    "note_keyword_sum",
)


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


def _format_weekly_breakdown(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    weeks = _safe_int(args.get("weeks_back", 2), default=2, min_value=1, max_value=8)
    this_week = week_range_for(ctx.now)
    lines = [f"Weekly breakdown ({weeks} week{'s' if weeks != 1 else ''}, newest first):"]
    for i in range(weeks):
        week_start = this_week.start - timedelta(days=7 * i)
        week_end = week_start + timedelta(days=7)
        end_bound = ctx.now if i == 0 else week_end
        productive = ctx.db.sum_minutes(ctx.user_id, "productive", start=week_start, end=end_bound)
        spent = ctx.db.sum_minutes(ctx.user_id, "spend", start=week_start, end=end_bound)
        xp = ctx.db.sum_xp(ctx.user_id, start=week_start, end=end_bound)
        label_end = (week_end - timedelta(days=1)).date().isoformat()
        lines.append(
            f"- {week_start.date().isoformat()} to {label_end}: "
            f"productive {format_minutes_hm(productive)}, spent {format_minutes_hm(spent)}, XP {xp}"
        )
    return ToolResult(ok=True, content="\n".join(lines), metadata={"action": "weekly_breakdown", "weeks": weeks})


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_month(dt: datetime, months: int) -> datetime:
    year = dt.year
    month = dt.month + months
    while month <= 0:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _format_category_trend(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    category = str(args.get("category", "build")).strip().lower()
    if category not in PRODUCTIVE_CATEGORIES:
        return ToolResult(
            ok=False,
            content=f"Invalid category '{category}'. Allowed: {', '.join(PRODUCTIVE_CATEGORIES)}",
            metadata={"action": "category_trend", "category": category},
        )
    period = str(args.get("period", "month")).strip().lower()
    if period not in {"week", "month"}:
        return ToolResult(
            ok=False,
            content="Invalid period. Use 'week' or 'month'.",
            metadata={"action": "category_trend", "period": period},
        )

    if period == "week":
        current_start = week_range_for(ctx.now).start
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start
        current_end = ctx.now
        current_label = f"current week ({current_start.date().isoformat()}..{ctx.now.date().isoformat()})"
        previous_label = f"previous week ({previous_start.date().isoformat()}..{(previous_end - timedelta(days=1)).date().isoformat()})"
    else:
        current_start = _start_of_month(ctx.now)
        previous_start = _add_month(current_start, -1)
        previous_end = current_start
        current_end = ctx.now
        current_label = f"current month ({current_start.date().isoformat()}..{ctx.now.date().isoformat()})"
        previous_label = f"previous month ({previous_start.date().isoformat()}..{(previous_end - timedelta(days=1)).date().isoformat()})"

    current_minutes = ctx.db.sum_minutes(
        ctx.user_id,
        "productive",
        start=current_start,
        end=current_end,
        category=category,
    )
    previous_minutes = ctx.db.sum_minutes(
        ctx.user_id,
        "productive",
        start=previous_start,
        end=previous_end,
        category=category,
    )
    delta = current_minutes - previous_minutes
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    if previous_minutes > 0:
        pct = (delta / previous_minutes) * 100.0
        pct_text = f"{pct:+.1f}%"
    else:
        pct_text = "n/a (no baseline)"

    content = (
        f"Trend for '{category}' ({period}):\n"
        f"- {current_label}: {format_minutes_hm(current_minutes)}\n"
        f"- {previous_label}: {format_minutes_hm(previous_minutes)}\n"
        f"- Delta: {format_minutes_hm(delta)} ({pct_text}), direction: {direction}"
    )
    return ToolResult(
        ok=True,
        content=content,
        metadata={
            "action": "category_trend",
            "category": category,
            "period": period,
            "delta_minutes": delta,
        },
    )


def _period_range(ctx: ToolContext, period: str) -> tuple[datetime | None, datetime | None, str]:
    p = period.strip().lower()
    if p in {"all", "all_time", ""}:
        return None, None, "all-time"
    if p == "week":
        start = week_range_for(ctx.now).start
        return start, ctx.now, "this week"
    if p == "month":
        start = _start_of_month(ctx.now)
        return start, ctx.now, "this month"
    if p == "last_7d":
        start = ctx.now - timedelta(days=7)
        return start, ctx.now, "last 7 days"
    if p == "last_30d":
        start = ctx.now - timedelta(days=30)
        return start, ctx.now, "last 30 days"
    return None, None, "all-time"


def _format_note_keyword_sum(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    keyword = str(args.get("query", "")).strip()
    if not keyword:
        return ToolResult(
            ok=False,
            content="Missing query. Example: {\"action\":\"note_keyword_sum\",\"kind\":\"spend\",\"query\":\"anime\"}",
            metadata={"action": "note_keyword_sum"},
        )
    kind = str(args.get("kind", "spend")).strip().lower()
    if kind not in {"spend", "productive", "all"}:
        return ToolResult(
            ok=False,
            content="Invalid kind. Use spend, productive, or all.",
            metadata={"action": "note_keyword_sum", "kind": kind},
        )
    kind_value = None if kind == "all" else kind
    period = str(args.get("period", "all")).strip().lower()
    start, end, period_label = _period_range(ctx, period)

    total, count = ctx.db.sum_minutes_by_note(
        user_id=ctx.user_id,
        note_query=keyword,
        kind=kind_value,
        start=start,
        end=end,
    )
    examples = ctx.db.list_entries_by_note(
        user_id=ctx.user_id,
        note_query=keyword,
        kind=kind_value,
        start=start,
        end=end,
        limit=5,
    )

    lines = [
        f"Keyword summary for '{keyword}' ({period_label}):",
        f"- Kind: {'all' if kind_value is None else kind_value}",
        f"- Total: {format_minutes_hm(total)} ({total}m)",
        f"- Matching entries: {count}",
    ]
    if examples:
        lines.append("- Recent matches:")
        for e in examples:
            ts = _as_local(e.created_at, ctx.now.tzinfo).strftime("%Y-%m-%d %H:%M")
            note = (e.note or "").strip()
            lines.append(f"  - {ts} | {e.kind} {format_minutes_hm(e.minutes)} | {note[:80]}")

    return ToolResult(
        ok=True,
        content="\n".join(lines),
        metadata={
            "action": "note_keyword_sum",
            "query": keyword,
            "kind": kind,
            "period": period,
            "total_minutes": total,
            "match_count": count,
        },
    )


def _format_recent_entries(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    limit = _safe_int(args.get("limit", 10), default=10, min_value=1, max_value=50)
    entries = ctx.db.list_recent_entries(ctx.user_id, limit=limit)
    if not entries:
        return ToolResult(ok=True, content="No entries found.", metadata={"action": "recent_entries", "count": 0})

    lines = [f"Recent entries ({len(entries)}):"]
    for entry in entries:
        ts = _as_local(entry.created_at, ctx.now.tzinfo).strftime("%Y-%m-%d %H:%M")
        note = f" | note: {entry.note}" if entry.note else ""
        if entry.kind == "productive":
            lines.append(
                f"- {ts} | +{format_minutes_hm(entry.minutes)} {entry.category}"
                f" | XP {entry.xp_earned} | fun +{entry.fun_earned}{note}"
            )
        elif entry.kind == "other":
            lines.append(f"- {ts} | {format_minutes_hm(entry.minutes)} other{note}")
        else:
            lines.append(f"- {ts} | -{format_minutes_hm(entry.minutes)} spend{note}")
    return ToolResult(ok=True, content="\n".join(lines), metadata={"action": "recent_entries", "count": len(entries)})


def _format_quest_history(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    days = _safe_int(args.get("days", 90), default=90, min_value=7, max_value=365)
    start = ctx.now - timedelta(days=days)
    history = ctx.db.list_quest_history(ctx.user_id, start=start, end=ctx.now)
    active = ctx.db.list_active_quests(ctx.user_id, ctx.now)

    lines = [f"Quests in last {days} days:"]
    lines.append(f"- Active now: {len(active)}")
    if active:
        for q in active[:5]:
            lines.append(
                f"  - ACTIVE [{q.difficulty}] {q.title} (reward {format_minutes_hm(q.reward_fun_minutes)}, expires {q.expires_at.date().isoformat()})"
            )
    lines.append(f"- Completed/expired/failed: {len(history)}")
    if history:
        for q in history[:10]:
            completed = q.completed_at.date().isoformat() if q.completed_at else "n/a"
            lines.append(
                f"  - {q.status.upper()} [{q.difficulty}] {q.title} (reward {format_minutes_hm(q.reward_fun_minutes)}, completed {completed})"
            )
    return ToolResult(
        ok=True,
        content="\n".join(lines),
        metadata={"action": "quest_history", "active": len(active), "history": len(history)},
    )


def _format_economy_breakdown(ctx: ToolContext) -> ToolResult:
    view = compute_status(ctx.db, ctx.user_id, ctx.now)
    tuning = ctx.db.get_economy_tuning()
    block_minutes = max(1, int(tuning.get("milestone_block_minutes", 600)))
    next_block_at = ((view.all_time.productive_minutes // block_minutes) + 1) * block_minutes
    minutes_to_next_block = max(0, next_block_at - view.all_time.productive_minutes)

    eco = view.economy
    content = (
        "Economy breakdown (all-time):\n"
        f"- Productive logged: {format_minutes_hm(view.all_time.productive_minutes)}\n"
        f"- Spent logged: {format_minutes_hm(view.all_time.spent_minutes)}\n"
        f"- Earned total: {format_minutes_hm(eco.earned_fun_minutes)}\n"
        f"  (base {format_minutes_hm(eco.base_fun_minutes)} + milestone {format_minutes_hm(eco.milestone_bonus_minutes)}"
        f" + level {format_minutes_hm(eco.level_bonus_minutes)} + quest {format_minutes_hm(eco.quest_bonus_minutes)}"
        f" + wheel {format_minutes_hm(eco.wheel_bonus_minutes)})\n"
        f"- Spent: {format_minutes_hm(eco.spent_fun_minutes)}\n"
        f"- Saved/locked: {format_minutes_hm(eco.saved_fun_minutes)}\n"
        f"- Remaining fun: {format_minutes_hm(eco.remaining_fun_minutes)}\n"
        f"- Next milestone block in: {format_minutes_hm(minutes_to_next_block)}"
    )
    return ToolResult(
        ok=True,
        content=content,
        metadata={"action": "economy_breakdown", "remaining_fun_minutes": eco.remaining_fun_minutes},
    )


class DbQueryTool(Tool):
    name = "db_query"
    description = (
        "Query user history/stats from tracker DB with structured actions. "
        "Args: {\"action\": \"weekly_breakdown|category_trend|recent_entries|quest_history|economy_breakdown|note_keyword_sum\", ...}. "
        "Use note_keyword_sum for note/description-based totals, e.g. anime/youtube."
    )
    tags = ("data", "stats", "history")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        if action == "weekly_breakdown":
            return _format_weekly_breakdown(ctx, args)
        if action == "category_trend":
            return _format_category_trend(ctx, args)
        if action == "recent_entries":
            return _format_recent_entries(ctx, args)
        if action == "quest_history":
            return _format_quest_history(ctx, args)
        if action == "economy_breakdown":
            return _format_economy_breakdown(ctx)
        if action == "note_keyword_sum":
            return _format_note_keyword_sum(ctx, args)
        return ToolResult(
            ok=False,
            content=f"Unknown action '{action}'. Supported actions: {', '.join(_SUPPORTED_ACTIONS)}",
            metadata={"action": action},
        )
