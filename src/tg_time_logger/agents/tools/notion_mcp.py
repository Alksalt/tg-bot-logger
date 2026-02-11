from __future__ import annotations

from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.notion_backup import build_backup_payload, push_to_notion_scaffold, write_local_backup


class NotionMcpTool(Tool):
    name = "notion_mcp"
    description = (
        "Scaffolded Notion backup helper. "
        "Args: {\"mode\": \"backup_now\", \"user_id\": int(optional)}"
    )

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        mode = str(args.get("mode", "backup_now")).strip().lower()
        if mode != "backup_now":
            return ToolResult(ok=False, content="Unsupported mode. Use mode=backup_now.", metadata={"mode": mode})

        raw_user_id = args.get("user_id")
        user_id = ctx.user_id
        if raw_user_id is not None:
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                return ToolResult(ok=False, content="Invalid user_id", metadata={})

        payload = build_backup_payload(ctx.db, user_id, ctx.now)
        path = write_local_backup(payload, ctx.settings.notion_backup_dir, user_id, ctx.now)
        remote_status, remote_message = push_to_notion_scaffold(payload, ctx.settings)
        return ToolResult(
            ok=True,
            content=(
                f"Notion backup scaffold complete for user {user_id}. "
                f"Local snapshot: {path}. Remote status: {remote_status}."
            ),
            metadata={
                "path": str(path),
                "remote_status": remote_status,
                "remote_message": remote_message,
                "entry_count": len(payload.get("entries", [])),
            },
        )

