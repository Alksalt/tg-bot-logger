from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.agents.tools.notion_mcp import NotionMcpTool
from tg_time_logger.agents.tools.search import WebSearchTool


@dataclass
class StubTool:
    name: str
    description: str

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

    def list_specs(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def run(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(ok=False, content=f"Unknown tool: {name}", metadata={})
        return tool.run(args, ctx)


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(WebSearchTool())
    reg.register(NotionMcpTool())
    reg.register(StubTool(name="mail_api", description="Future mail integration tool."))
    reg.register(StubTool(name="maps_api", description="Future maps/geocoding integration tool."))
    reg.register(StubTool(name="custom_http_api", description="Future generic app API connector tool."))
    return reg
