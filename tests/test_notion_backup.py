from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.notion_backup import push_to_notion_scaffold, run_notion_backup_job


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_notion_backup_scaffold_writes_local_file(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11)
    db.upsert_user_profile(user_id=42, chat_id=99, seen_at=now)
    db.add_entry(
        user_id=42,
        kind="productive",
        category="build",
        minutes=60,
        note="test",
        created_at=now,
    )

    settings = Settings(
        telegram_bot_token="x",
        database_path=tmp_path / "app.db",
        tz="Europe/Oslo",
        llm_enabled=False,
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

    records = run_notion_backup_job(db, settings, now)
    assert len(records) == 1
    assert records[0].path.exists()
    assert records[0].remote_status == "skipped"


def test_notion_push_success_with_stubbed_http(monkeypatch, tmp_path) -> None:
    class _Resp:
        def __init__(self, status_code: int, data: dict[str, object]) -> None:
            self.status_code = status_code
            self._data = data
            self.text = str(data)
            self.headers: dict[str, str] = {}

        def json(self) -> dict[str, object]:
            return self._data

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, headers: dict[str, str]):
            _ = headers
            assert "databases" in url
            return _Resp(200, {"properties": {"Name": {"type": "title"}}})

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]):
            _ = headers
            _ = json
            assert url.endswith("/v1/pages")
            return _Resp(200, {"id": "abc123"})

    import tg_time_logger.notion_backup as nb

    monkeypatch.setattr(nb.httpx, "Client", _Client)
    payload = {"user_id": 1, "generated_at": "2026-02-11T10:00:00+01:00", "status": {"level": 2}}
    settings = Settings(
        telegram_bot_token="x",
        database_path=tmp_path / "app.db",
        tz="Europe/Oslo",
        llm_enabled=False,
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
        notion_api_key="secret",
        notion_database_id="dbid",
        notion_backup_dir=tmp_path / "notion_backups",
        notion_backend="api",
        notion_mcp_url=None,
        notion_mcp_auth_token=None,
        notion_mcp_tool_name="notion-create-pages",
    )
    status, msg = push_to_notion_scaffold(payload, settings)
    assert status == "synced"
    assert "abc123" in msg


def test_notion_push_mcp_mode_success(monkeypatch, tmp_path) -> None:
    class _Resp:
        def __init__(self, status_code: int, data: dict[str, object]) -> None:
            self.status_code = status_code
            self._data = data
            self.text = str(data)
            self.headers: dict[str, str] = {}

        def json(self) -> dict[str, object]:
            return self._data

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, headers: dict[str, str], json: dict[str, object]):
            _ = headers
            assert url == "http://localhost:8787/mcp"
            assert json.get("method") == "tools/call"
            return _Resp(200, {"jsonrpc": "2.0", "id": "x", "result": {"ok": True}})

    import tg_time_logger.notion_backup as nb

    monkeypatch.setattr(nb.httpx, "Client", _Client)
    payload = {"user_id": 1, "generated_at": "2026-02-11T10:00:00+01:00", "status": {"level": 2}}
    settings = Settings(
        telegram_bot_token="x",
        database_path=tmp_path / "app.db",
        tz="Europe/Oslo",
        llm_enabled=False,
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
        notion_database_id="dbid",
        notion_backup_dir=tmp_path / "notion_backups",
        notion_backend="mcp",
        notion_mcp_url="http://localhost:8787/mcp",
        notion_mcp_auth_token=None,
        notion_mcp_tool_name="notion-create-pages",
    )
    status, _ = push_to_notion_scaffold(payload, settings)
    assert status == "synced"
