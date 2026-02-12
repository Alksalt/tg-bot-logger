from __future__ import annotations

from datetime import timedelta
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes


class TodoManageTool(Tool):
    name = "todo_manage"
    description = (
        "Manage the user's daily to-do list. "
        'Args: {"action": "add|list|done|delete", '
        '"title": str (for add), '
        '"duration": str (optional for add, e.g. "2h", "30m"), '
        '"plan_date": str (optional, "today"|"tomorrow"|"YYYY-MM-DD", default today), '
        '"id": int (for done/delete)}. '
        "Can add multiple items by calling this tool multiple times."
    )
    tags = ("todo", "task", "productivity")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        if action == "add":
            return self._add(args, ctx)
        if action == "list":
            return self._list(args, ctx)
        if action == "done":
            return self._done(args, ctx)
        if action == "delete":
            return self._delete(args, ctx)
        return ToolResult(
            ok=False,
            content=f"Unknown action '{action}'. Use add, list, done, or delete.",
            metadata={"action": action},
        )

    def _resolve_date(self, raw: str | None, ctx: ToolContext) -> str:
        if not raw or raw == "today":
            return ctx.now.date().isoformat()
        if raw == "tomorrow":
            return (ctx.now.date() + timedelta(days=1)).isoformat()
        # Accept YYYY-MM-DD directly
        if isinstance(raw, str) and len(raw) == 10 and raw[4] == "-":
            return raw
        return ctx.now.date().isoformat()

    def _add(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        title = str(args.get("title", "")).strip()
        if not title:
            return ToolResult(ok=False, content="Missing required field: title.", metadata={"action": "add"})

        duration_minutes: int | None = None
        dur_raw = args.get("duration")
        if dur_raw:
            try:
                duration_minutes = parse_duration_to_minutes(str(dur_raw))
            except DurationParseError:
                pass

        plan_date = self._resolve_date(args.get("plan_date"), ctx)
        pos = ctx.db.next_todo_position(ctx.user_id, plan_date)
        item = ctx.db.add_todo(ctx.user_id, plan_date, title, duration_minutes, pos, ctx.now)

        dur_text = f" ({duration_minutes}m)" if duration_minutes else ""
        return ToolResult(
            ok=True,
            content=f"Added todo #{item.id}: {title}{dur_text} for {plan_date}",
            metadata={"action": "add", "id": item.id, "plan_date": plan_date},
        )

    def _list(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        plan_date = self._resolve_date(args.get("plan_date"), ctx)
        items = ctx.db.list_todos(ctx.user_id, plan_date)
        if not items:
            return ToolResult(
                ok=True,
                content=f"No tasks for {plan_date}.",
                metadata={"action": "list", "plan_date": plan_date, "count": 0},
            )
        lines = [f"Tasks for {plan_date} ({sum(1 for i in items if i.status == 'done')}/{len(items)} done):"]
        for item in items:
            icon = "\u2705" if item.status == "done" else "\u2b1c"
            dur = f" ({item.duration_minutes}m)" if item.duration_minutes else ""
            lines.append(f"  {item.id}. {icon} {item.title}{dur}")
        return ToolResult(
            ok=True,
            content="\n".join(lines),
            metadata={"action": "list", "plan_date": plan_date, "count": len(items)},
        )

    def _done(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            todo_id = int(args.get("id", 0))
        except (TypeError, ValueError):
            return ToolResult(ok=False, content="Missing or invalid 'id'.", metadata={"action": "done"})
        item = ctx.db.get_todo(todo_id)
        if not item or item.user_id != ctx.user_id:
            return ToolResult(ok=False, content=f"Todo #{todo_id} not found.", metadata={"action": "done"})
        ok = ctx.db.mark_todo_done(todo_id, ctx.now)
        if not ok:
            return ToolResult(ok=False, content=f"Todo #{todo_id} is already done.", metadata={"action": "done"})
        return ToolResult(ok=True, content=f"Todo #{todo_id} marked done.", metadata={"action": "done", "id": todo_id})

    def _delete(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            todo_id = int(args.get("id", 0))
        except (TypeError, ValueError):
            return ToolResult(ok=False, content="Missing or invalid 'id'.", metadata={"action": "delete"})
        ok = ctx.db.delete_todo(ctx.user_id, todo_id)
        if not ok:
            return ToolResult(ok=False, content=f"Todo #{todo_id} not found.", metadata={"action": "delete"})
        return ToolResult(
            ok=True, content=f"Todo #{todo_id} deleted.", metadata={"action": "delete", "id": todo_id}
        )
