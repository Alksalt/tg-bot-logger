from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.agents.tools.db_query import DbQueryTool
from tg_time_logger.agents.tools.insights import InsightsTool
from tg_time_logger.agents.tools.memory import MemoryManageTool
from tg_time_logger.agents.tools.notion_mcp import NotionMcpTool
from tg_time_logger.agents.tools.quest_propose import QuestProposeTool
from tg_time_logger.agents.tools.todo import TodoManageTool


@dataclass
class StubTool:
    name: str
    description: str
    tags: tuple[str, ...] = ()
    is_stub: bool = True

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(
            ok=False,
            content=f"Tool '{self.name}' is scaffolded but not implemented yet.",
            metadata={"args": args},
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_specs(self, *, include_stubs: bool = False, tags: set[str] | None = None) -> list[dict[str, str]]:
        specs: list[dict[str, str]] = []
        for t in self._tools.values():
            if not include_stubs and getattr(t, "is_stub", False):
                continue
            if tags is not None:
                tool_tags = set(getattr(t, "tags", ()))
                if not tool_tags.intersection(tags):
                    continue
            specs.append({"name": t.name, "description": t.description})
        return specs

    def filter_by_tags(self, tags: set[str]) -> ToolRegistry:
        """Return a new registry containing only non-stub tools matching any of the given tags."""
        filtered = ToolRegistry()
        for t in self._tools.values():
            if getattr(t, "is_stub", False):
                continue
            tool_tags = set(getattr(t, "tags", ()))
            if tool_tags.intersection(tags):
                filtered.register(t)
        return filtered

    def run(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(ok=False, content=f"Unknown tool: {name}", metadata={})
        return tool.run(args, ctx)


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(DbQueryTool())
    reg.register(InsightsTool())
    reg.register(QuestProposeTool())
    reg.register(MemoryManageTool())
    reg.register(NotionMcpTool())
    reg.register(TodoManageTool())
    reg.register(StubTool(name="mail_api", description="Future mail integration tool.", tags=("communication", "mail")))
    reg.register(StubTool(name="maps_api", description="Future maps/geocoding integration tool.", tags=("maps", "location")))
    reg.register(StubTool(name="custom_http_api", description="Future generic app API connector tool.", tags=("http", "api")))
    return reg
