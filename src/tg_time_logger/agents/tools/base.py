from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from tg_time_logger.config import Settings
from tg_time_logger.db import Database


@dataclass(frozen=True)
class ToolContext:
    user_id: int
    now: datetime
    db: Database
    settings: Settings
    config: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str
    metadata: dict[str, Any]


class Tool(Protocol):
    name: str
    description: str
    tags: tuple[str, ...]

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        ...
