from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.memory import MemoryManageTool
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


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
        now=_dt(2026, 2, 12),
        db=db,
        settings=_settings(tmp_path),
        config={},
    )


# ---------------------------------------------------------------------------
# DB: coach_messages
# ---------------------------------------------------------------------------


class TestCoachMessages:
    def test_add_and_list(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        db.add_coach_message(1, "user", "Hello coach", now)
        db.add_coach_message(1, "assistant", "Hi! How can I help?", now)
        msgs = db.list_coach_messages(1, limit=10)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert msgs[0].content == "Hello coach"

    def test_list_returns_chronological_order(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        for i in range(5):
            db.add_coach_message(1, "user", f"msg {i}", _dt(2026, 2, 12, 10, i))
        msgs = db.list_coach_messages(1, limit=3)
        assert len(msgs) == 3
        assert msgs[0].content == "msg 2"
        assert msgs[2].content == "msg 4"

    def test_prune_keeps_newest(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        for i in range(10):
            db.add_coach_message(1, "user", f"msg {i}", _dt(2026, 2, 12, 10, i))
        deleted = db.prune_coach_messages(1, keep=3)
        assert deleted == 7
        remaining = db.list_coach_messages(1, limit=100)
        assert len(remaining) == 3
        assert remaining[0].content == "msg 7"

    def test_clear(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        db.add_coach_message(1, "user", "msg", _dt(2026, 2, 12))
        count = db.clear_coach_messages(1)
        assert count == 1
        assert db.list_coach_messages(1) == []

    def test_isolation_between_users(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        db.add_coach_message(1, "user", "user1 msg", now)
        db.add_coach_message(2, "user", "user2 msg", now)
        assert len(db.list_coach_messages(1)) == 1
        assert len(db.list_coach_messages(2)) == 1


# ---------------------------------------------------------------------------
# DB: coach_memory
# ---------------------------------------------------------------------------


class TestCoachMemory:
    def test_add_and_list(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        mem = db.add_coach_memory(1, "preference", "I prefer mornings", "schedule", now)
        assert mem.category == "preference"
        assert mem.tags == "schedule"
        memories = db.list_coach_memories(1)
        assert len(memories) == 1

    def test_list_by_category(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        db.add_coach_memory(1, "preference", "morning person", None, now)
        db.add_coach_memory(1, "goal", "reach level 20", None, now)
        prefs = db.list_coach_memories(1, category="preference")
        assert len(prefs) == 1
        assert prefs[0].category == "preference"

    def test_remove(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        mem = db.add_coach_memory(1, "fact", "works from home", None, now)
        assert db.remove_coach_memory(1, mem.id)
        assert db.list_coach_memories(1) == []

    def test_remove_nonexistent(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        assert not db.remove_coach_memory(1, 999)

    def test_clear(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        db.add_coach_memory(1, "fact", "fact1", None, now)
        db.add_coach_memory(1, "goal", "goal1", None, now)
        count = db.clear_coach_memories(1)
        assert count == 2

    def test_tags_nullable(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        mem = db.add_coach_memory(1, "fact", "no tags", None, now)
        assert mem.tags is None


# ---------------------------------------------------------------------------
# Memory tool
# ---------------------------------------------------------------------------


class TestMemoryManageTool:
    def test_save(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run(
            {"action": "save", "category": "preference", "content": "I like mornings"},
            ctx,
        )
        assert result.ok
        assert "saved" in result.content.lower()

    def test_save_invalid_category(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run(
            {"action": "save", "category": "invalid", "content": "test"},
            ctx,
        )
        assert not result.ok

    def test_save_empty_content(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run({"action": "save", "category": "fact", "content": ""}, ctx)
        assert not result.ok

    def test_save_dedup(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        tool.run({"action": "save", "category": "fact", "content": "works remote"}, ctx)
        result = tool.run(
            {"action": "save", "category": "fact", "content": "works remote"}, ctx
        )
        assert result.ok
        assert "duplicate" in result.content.lower()

    def test_list(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        tool.run({"action": "save", "category": "goal", "content": "reach level 20"}, ctx)
        result = tool.run({"action": "list"}, ctx)
        assert result.ok
        assert "level 20" in result.content

    def test_list_empty(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run({"action": "list"}, ctx)
        assert result.ok
        assert "no memories" in result.content.lower()

    def test_delete(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        tool.run({"action": "save", "category": "fact", "content": "test"}, ctx)
        memories = db.list_coach_memories(1)
        result = tool.run({"action": "delete", "id": memories[0].id}, ctx)
        assert result.ok

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run({"action": "delete", "id": 999}, ctx)
        assert not result.ok

    def test_unknown_action(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run({"action": "nope"}, ctx)
        assert not result.ok

    def test_save_with_tags(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "app.db")
        ctx = _ctx(db, tmp_path)
        tool = MemoryManageTool()
        result = tool.run(
            {"action": "save", "category": "preference", "content": "likes building", "tags": "build,coding"},
            ctx,
        )
        assert result.ok
        memories = db.list_coach_memories(1)
        assert memories[0].tags == "build,coding"


# ---------------------------------------------------------------------------
# Coach runner (unit-level, mocked)
# ---------------------------------------------------------------------------


class TestCoachRunner:
    def test_saves_messages(self, tmp_path: Path, monkeypatch) -> None:
        from tg_time_logger.agents.orchestration import coach_runner
        from tg_time_logger.agents.execution.loop import AgentRunResult

        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        settings = _settings(tmp_path)

        def fake_run(self, req, ctx):
            return AgentRunResult(
                answer="Great question!",
                model_used="test-model",
                steps=[],
                prompt_tokens=100,
                completion_tokens=50,
                status="ok",
            )

        monkeypatch.setattr(
            "tg_time_logger.agents.execution.loop.AgentLoop.run", fake_run
        )
        monkeypatch.setattr(db, "add_admin_audit", lambda **kw: None)

        result = coach_runner.run_coach_agent(
            db=db, settings=settings, user_id=1, now=now, message="How am I doing?"
        )
        assert result["ok"]
        assert result["answer"] == "Great question!"

        msgs = db.list_coach_messages(1, limit=10)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content == "How am I doing?"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "Great question!"

    def test_context_includes_history(self, tmp_path: Path, monkeypatch) -> None:
        from tg_time_logger.agents.orchestration import coach_runner
        from tg_time_logger.agents.execution.loop import AgentRunResult

        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        settings = _settings(tmp_path)

        # Pre-populate conversation
        db.add_coach_message(1, "user", "Hi coach", _dt(2026, 2, 12, 9, 0))
        db.add_coach_message(1, "assistant", "Hello!", _dt(2026, 2, 12, 9, 1))

        captured_req = {}

        def fake_run(self, req, ctx):
            captured_req["context_text"] = req.context_text
            return AgentRunResult(
                answer="Here is advice.",
                model_used="test-model",
                steps=[],
                prompt_tokens=100,
                completion_tokens=50,
                status="ok",
            )

        monkeypatch.setattr(
            "tg_time_logger.agents.execution.loop.AgentLoop.run", fake_run
        )
        monkeypatch.setattr(db, "add_admin_audit", lambda **kw: None)

        coach_runner.run_coach_agent(
            db=db, settings=settings, user_id=1, now=now, message="What next?"
        )
        ctx_text = captured_req["context_text"]
        assert "Recent conversation:" in ctx_text
        assert "Hi coach" in ctx_text

    def test_context_includes_memory(self, tmp_path: Path, monkeypatch) -> None:
        from tg_time_logger.agents.orchestration import coach_runner
        from tg_time_logger.agents.execution.loop import AgentRunResult

        db = Database(tmp_path / "app.db")
        now = _dt(2026, 2, 12)
        settings = _settings(tmp_path)

        db.add_coach_memory(1, "preference", "loves mornings", None, now)

        captured_req = {}

        def fake_run(self, req, ctx):
            captured_req["context_text"] = req.context_text
            return AgentRunResult(
                answer="Noted.",
                model_used="test-model",
                steps=[],
                prompt_tokens=100,
                completion_tokens=50,
                status="ok",
            )

        monkeypatch.setattr(
            "tg_time_logger.agents.execution.loop.AgentLoop.run", fake_run
        )
        monkeypatch.setattr(db, "add_admin_audit", lambda **kw: None)

        coach_runner.run_coach_agent(
            db=db, settings=settings, user_id=1, now=now, message="Tell me about me"
        )
        ctx_text = captured_req["context_text"]
        assert "Known about user:" in ctx_text
        assert "loves mornings" in ctx_text


# ---------------------------------------------------------------------------
# Coach runner context helpers (unit)
# ---------------------------------------------------------------------------


class TestContextBuilders:
    def test_conversation_history_text_empty(self, tmp_path: Path) -> None:
        from tg_time_logger.agents.orchestration.coach_runner import _build_conversation_history_text

        db = Database(tmp_path / "app.db")
        assert _build_conversation_history_text(db, 1) == ""

    def test_conversation_history_truncates(self, tmp_path: Path) -> None:
        from tg_time_logger.agents.orchestration.coach_runner import _build_conversation_history_text

        db = Database(tmp_path / "app.db")
        long_msg = "x" * 500
        db.add_coach_message(1, "user", long_msg, _dt(2026, 2, 12))
        text = _build_conversation_history_text(db, 1)
        assert "..." in text
        assert len(text) < 500

    def test_memory_context_text_empty(self, tmp_path: Path) -> None:
        from tg_time_logger.agents.orchestration.coach_runner import _build_memory_context_text

        db = Database(tmp_path / "app.db")
        assert _build_memory_context_text(db, 1) == ""

    def test_memory_context_text_with_tags(self, tmp_path: Path) -> None:
        from tg_time_logger.agents.orchestration.coach_runner import _build_memory_context_text

        db = Database(tmp_path / "app.db")
        db.add_coach_memory(1, "goal", "level 20", "gamification", _dt(2026, 2, 12))
        text = _build_memory_context_text(db, 1)
        assert "Known about user:" in text
        assert "level 20" in text
        assert "[gamification]" in text
