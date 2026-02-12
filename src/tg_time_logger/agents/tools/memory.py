from __future__ import annotations

from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult

_VALID_CATEGORIES = ("preference", "goal", "fact", "context")
_MAX_MEMORIES = 30


class MemoryManageTool(Tool):
    name = "memory_manage"
    description = (
        "Save, list, or delete long-term user memories. "
        "Args: {\"action\": \"save|list|delete\", "
        "\"category\": \"preference|goal|fact|context\" (required for save), "
        "\"content\": str (required for save), "
        "\"tags\": str (optional, comma-separated), "
        "\"id\": int (required for delete)}"
    )
    tags = ("memory", "coach")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        if action == "save":
            return self._save(args, ctx)
        if action == "list":
            return self._list(args, ctx)
        if action == "delete":
            return self._delete(args, ctx)
        return ToolResult(
            ok=False,
            content=f"Unknown action '{action}'. Use save, list, or delete.",
            metadata={"action": action},
        )

    def _save(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        category = str(args.get("category", "")).strip().lower()
        content = str(args.get("content", "")).strip()
        tags_raw = args.get("tags")
        tags_str = str(tags_raw).strip() if tags_raw else None

        if category not in _VALID_CATEGORIES:
            return ToolResult(
                ok=False,
                content=f"Invalid category '{category}'. Use: {', '.join(_VALID_CATEGORIES)}",
                metadata={"action": "save"},
            )
        if not content:
            return ToolResult(ok=False, content="Missing required field: content.", metadata={"action": "save"})
        if len(content) > 500:
            content = content[:500]

        existing = ctx.db.list_coach_memories(ctx.user_id, limit=_MAX_MEMORIES + 1)
        if len(existing) >= _MAX_MEMORIES:
            return ToolResult(
                ok=False,
                content=f"Memory limit reached ({_MAX_MEMORIES}). Delete old memories first.",
                metadata={"action": "save", "count": len(existing)},
            )

        for mem in existing:
            if mem.content.lower().strip() == content.lower().strip():
                return ToolResult(
                    ok=True,
                    content=f"Memory already exists (id={mem.id}). Skipped duplicate.",
                    metadata={"action": "save", "duplicate_id": mem.id},
                )

        memory = ctx.db.add_coach_memory(
            user_id=ctx.user_id,
            category=category,
            content=content,
            tags=tags_str,
            created_at=ctx.now,
        )
        return ToolResult(
            ok=True,
            content=f"Memory saved (id={memory.id}, category={category}).",
            metadata={"action": "save", "id": memory.id, "category": category},
        )

    def _list(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        category = str(args.get("category", "")).strip().lower() or None
        if category and category not in _VALID_CATEGORIES:
            category = None

        memories = ctx.db.list_coach_memories(ctx.user_id, category=category, limit=20)
        if not memories:
            return ToolResult(ok=True, content="No memories stored yet.", metadata={"action": "list", "count": 0})

        lines = [f"Memories ({len(memories)}):"]
        for mem in memories:
            tag_text = f" [{mem.tags}]" if mem.tags else ""
            lines.append(f"- [{mem.id}] ({mem.category}{tag_text}) {mem.content}")
        return ToolResult(ok=True, content="\n".join(lines), metadata={"action": "list", "count": len(memories)})

    def _delete(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            memory_id = int(args.get("id", 0))
        except (TypeError, ValueError):
            return ToolResult(ok=False, content="Missing or invalid 'id' for delete.", metadata={"action": "delete"})
        if memory_id <= 0:
            return ToolResult(ok=False, content="Invalid memory id.", metadata={"action": "delete"})

        ok = ctx.db.remove_coach_memory(ctx.user_id, memory_id)
        if ok:
            return ToolResult(ok=True, content=f"Memory {memory_id} deleted.", metadata={"action": "delete", "id": memory_id})
        return ToolResult(ok=False, content=f"Memory {memory_id} not found.", metadata={"action": "delete", "id": memory_id})
