from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.db_query import DbQueryTool
from tg_time_logger.agents.tools.insights import InsightsTool
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


def _seed(db: Database, now: datetime) -> None:
    user_id = 1
    db.add_entry(user_id=user_id, kind="productive", category="build", minutes=180, created_at=now - timedelta(days=1), note="feature work")
    db.add_entry(user_id=user_id, kind="productive", category="study", minutes=120, created_at=now - timedelta(days=2), note="docs")
    db.add_entry(user_id=user_id, kind="productive", category="training", minutes=90, created_at=now - timedelta(days=8), note="gym")
    db.add_entry(user_id=user_id, kind="spend", minutes=60, created_at=now - timedelta(days=1), note="gaming")
    db.add_entry(user_id=user_id, kind="spend", minutes=40, created_at=now - timedelta(days=2), note="anime")
    db.add_entry(user_id=user_id, kind="spend", minutes=25, created_at=now - timedelta(days=3), note="anime")
    db.insert_quest(
        user_id=user_id,
        title="Build Sprint",
        description="Ship one feature this week",
        quest_type="build",
        difficulty="medium",
        reward_fun_minutes=120,
        condition={"type": "minutes", "category": "build", "target": 240},
        expires_at=now + timedelta(days=4),
        created_at=now - timedelta(days=3),
    )


def _ctx(tmp_path: Path) -> ToolContext:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11, 22, 0)
    _seed(db, now)
    return ToolContext(
        user_id=1,
        now=now,
        db=db,
        settings=_settings(tmp_path),
        config=db.get_app_config(),
    )


def test_db_query_recent_entries(tmp_path) -> None:
    tool = DbQueryTool()
    ctx = _ctx(tmp_path)
    result = tool.run({"action": "recent_entries", "limit": 3}, ctx)
    assert result.ok is True
    assert "Recent entries" in result.content
    assert "feature work" in result.content
    assert "spend" in result.content


def test_db_query_category_trend_month(tmp_path) -> None:
    tool = DbQueryTool()
    ctx = _ctx(tmp_path)
    result = tool.run({"action": "category_trend", "category": "build", "period": "month"}, ctx)
    assert result.ok is True
    assert "Trend for 'build'" in result.content
    assert "Delta:" in result.content


def test_db_query_economy_breakdown(tmp_path) -> None:
    tool = DbQueryTool()
    ctx = _ctx(tmp_path)
    result = tool.run({"action": "economy_breakdown"}, ctx)
    assert result.ok is True
    assert "Economy breakdown" in result.content
    assert "Remaining fun" in result.content


def test_db_query_note_keyword_sum(tmp_path) -> None:
    tool = DbQueryTool()
    ctx = _ctx(tmp_path)
    result = tool.run(
        {"action": "note_keyword_sum", "kind": "spend", "query": "anime", "period": "all"},
        ctx,
    )
    assert result.ok is True
    assert "Keyword summary for 'anime'" in result.content
    assert "65m" in result.content
    assert result.metadata["total_minutes"] == 65
    assert result.metadata["match_count"] == 2


def test_insights_snapshot(tmp_path) -> None:
    tool = InsightsTool()
    ctx = _ctx(tmp_path)
    result = tool.run({}, ctx)
    assert result.ok is True
    assert "Insights snapshot" in result.content
    assert "Consistency (30d)" in result.content
    assert "Category velocity" in result.content
    assert "Economy health" in result.content


def test_insights_focus_and_invalid_focus(tmp_path) -> None:
    tool = InsightsTool()
    ctx = _ctx(tmp_path)
    focused = tool.run({"focus": "streak"}, ctx)
    assert focused.ok is True
    assert focused.content.startswith("Streak risk:")

    invalid = tool.run({"focus": "unknown"}, ctx)
    assert invalid.ok is False
    assert "Unknown focus" in invalid.content
