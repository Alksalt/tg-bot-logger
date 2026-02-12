from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.todo import TodoManageTool
from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.help_guides import (
    COMMAND_DESCRIPTIONS,
    GUIDE_PAGES,
    GUIDE_TITLES,
    HELP_TOPICS,
    TOPIC_ALIASES,
)


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="x",
        database_path=tmp_path / "app.db",
        tz="Europe/Oslo",
        llm_enabled=True,
        llm_provider="openai",
        llm_model="gpt-5-mini",
        llm_api_key=None,
        llm_router_config_path=Path("llm_router.yaml"),
        admin_panel_token=None,
        admin_host="127.0.0.1",
        admin_port=8080,
        openrouter_api_key=None,
        openai_api_key=None,
        google_api_key=None,
        anthropic_api_key=None,
        brave_search_api_key=None,
        tavily_api_key=None,
        serper_api_key=None,
        agent_models_path=Path("agents/models.yaml"),
        agent_directive_path=Path("agents/directives/llm_assistant.md"),
        notion_api_key=None,
        notion_database_id=None,
        notion_backup_dir=tmp_path / "notion_backups",
        notion_backend="api",
        notion_mcp_url=None,
        notion_mcp_auth_token=None,
        notion_mcp_tool_name="notion-create-pages",
    )


def _ctx(db: Database, tmp_path: Path) -> ToolContext:
    return ToolContext(
        user_id=1,
        now=_dt(2026, 2, 13),
        db=db,
        settings=_settings(tmp_path),
        config={},
    )


# ---------------------------------------------------------------------------
# DB CRUD tests
# ---------------------------------------------------------------------------


class TestTodoDB:
    def test_add_todo(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "improve tg bot", 120, 0, now)
        assert item.id == 1
        assert item.user_id == 1
        assert item.plan_date == "2026-02-13"
        assert item.title == "improve tg bot"
        assert item.duration_minutes == 120
        assert item.status == "pending"
        assert item.position == 0

    def test_add_todo_no_duration(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "meeting", None, 0, now)
        assert item.duration_minutes is None

    def test_list_todos_ordered(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        db.add_todo(1, "2026-02-13", "task B", None, 1, now)
        db.add_todo(1, "2026-02-13", "task A", None, 0, now)
        db.add_todo(1, "2026-02-13", "task C", None, 2, now)
        items = db.list_todos(1, "2026-02-13")
        assert [i.title for i in items] == ["task A", "task B", "task C"]

    def test_list_todos_empty(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        assert db.list_todos(1, "2026-02-13") == []

    def test_mark_todo_done(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "training", 60, 0, now)
        ok = db.mark_todo_done(item.id, now)
        assert ok is True
        updated = db.get_todo(item.id)
        assert updated is not None
        assert updated.status == "done"
        assert updated.completed_at is not None

    def test_mark_todo_done_already_done(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "training", 60, 0, now)
        db.mark_todo_done(item.id, now)
        ok = db.mark_todo_done(item.id, now)
        assert ok is False

    def test_delete_todo(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "task", None, 0, now)
        ok = db.delete_todo(1, item.id)
        assert ok is True
        assert db.get_todo(item.id) is None

    def test_delete_todo_wrong_user(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        item = db.add_todo(1, "2026-02-13", "task", None, 0, now)
        ok = db.delete_todo(999, item.id)
        assert ok is False

    def test_clear_pending_todos(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        db.add_todo(1, "2026-02-13", "task A", None, 0, now)
        item_b = db.add_todo(1, "2026-02-13", "task B", None, 1, now)
        db.mark_todo_done(item_b.id, now)
        db.add_todo(1, "2026-02-13", "task C", None, 2, now)
        count = db.clear_pending_todos(1, "2026-02-13")
        assert count == 2
        remaining = db.list_todos(1, "2026-02-13")
        assert len(remaining) == 1
        assert remaining[0].status == "done"

    def test_get_todo_not_found(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        assert db.get_todo(9999) is None

    def test_next_todo_position(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 13)
        assert db.next_todo_position(1, "2026-02-13") == 0
        db.add_todo(1, "2026-02-13", "task A", None, 0, now)
        assert db.next_todo_position(1, "2026-02-13") == 1
        db.add_todo(1, "2026-02-13", "task B", None, 1, now)
        assert db.next_todo_position(1, "2026-02-13") == 2


# ---------------------------------------------------------------------------
# Agent tool tests
# ---------------------------------------------------------------------------


class TestTodoManageTool:
    def test_add(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "add", "title": "improve bot", "duration": "2h"}, ctx)
        assert result.ok is True
        assert "improve bot" in result.content
        assert "(120m)" in result.content

    def test_add_no_title(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "add", "title": ""}, ctx)
        assert result.ok is False

    def test_add_with_tomorrow(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "add", "title": "gym", "plan_date": "tomorrow"}, ctx)
        assert result.ok is True
        tomorrow = (ctx.now.date() + timedelta(days=1)).isoformat()
        assert tomorrow in result.content

    def test_list_empty(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "list"}, ctx)
        assert result.ok is True
        assert "No tasks" in result.content

    def test_list_with_items(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        today = ctx.now.date().isoformat()
        db.add_todo(1, today, "task A", 60, 0, ctx.now)
        db.add_todo(1, today, "task B", None, 1, ctx.now)
        tool = TodoManageTool()
        result = tool.run({"action": "list"}, ctx)
        assert result.ok is True
        assert "task A" in result.content
        assert "task B" in result.content
        assert result.metadata["count"] == 2

    def test_done(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        today = ctx.now.date().isoformat()
        item = db.add_todo(1, today, "training", 60, 0, ctx.now)
        tool = TodoManageTool()
        result = tool.run({"action": "done", "id": item.id}, ctx)
        assert result.ok is True
        assert "done" in result.content.lower()

    def test_done_not_found(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "done", "id": 9999}, ctx)
        assert result.ok is False

    def test_delete(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        today = ctx.now.date().isoformat()
        item = db.add_todo(1, today, "task", None, 0, ctx.now)
        tool = TodoManageTool()
        result = tool.run({"action": "delete", "id": item.id}, ctx)
        assert result.ok is True
        assert db.get_todo(item.id) is None

    def test_invalid_action(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = TodoManageTool()
        result = tool.run({"action": "foo"}, ctx)
        assert result.ok is False


# ---------------------------------------------------------------------------
# Callback data size
# ---------------------------------------------------------------------------


class TestCallbackData:
    def test_callback_data_fits_telegram_limit(self) -> None:
        # Telegram allows up to 64 bytes for callback_data
        patterns = [
            "todo:done:999999",
            "todo:yes:999999:training",
            "todo:no:999999",
        ]
        for pattern in patterns:
            assert len(pattern.encode("utf-8")) <= 64, f"'{pattern}' exceeds 64 bytes"


# ---------------------------------------------------------------------------
# Help guide integration
# ---------------------------------------------------------------------------


class TestTodoHelpGuide:
    def test_command_description_exists(self) -> None:
        assert "todo" in COMMAND_DESCRIPTIONS

    def test_help_topic_exists(self) -> None:
        assert "todo" in HELP_TOPICS

    def test_guide_topic_exists(self) -> None:
        assert "todo" in GUIDE_PAGES
        assert "todo" in GUIDE_TITLES

    def test_guide_has_enough_pages(self) -> None:
        assert len(GUIDE_PAGES["todo"]) >= 3

    def test_guide_pages_under_limit(self) -> None:
        header_budget = 300
        max_len = 4096 - header_budget
        for i, page in enumerate(GUIDE_PAGES["todo"], 1):
            assert len(page) <= max_len, f"Todo guide page {i} is {len(page)} chars (max {max_len})"
            assert len(page) > 0, f"Todo guide page {i} is empty"

    def test_topic_aliases(self) -> None:
        assert TOPIC_ALIASES.get("todo") == "todo"
        assert TOPIC_ALIASES.get("todos") == "todo"
        assert TOPIC_ALIASES.get("tasks") == "todo"
