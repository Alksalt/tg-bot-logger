from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tg_time_logger.agents.execution.config import ModelConfig, ModelSpec, TierSpec, get_tier_order, load_model_config
from tg_time_logger.agents.execution.loop import AgentLoop, AgentRequest
from tg_time_logger.agents.execution.llm_client import parse_json_object
from tg_time_logger.agents.orchestration.runner import run_llm_agent
from tg_time_logger.agents.tools.base import ToolContext
from tg_time_logger.agents.tools.registry import build_default_registry
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_model_config_loads_default_tier() -> None:
    cfg = load_model_config(path=Path("agents/models.yaml"))
    assert cfg.default_tier in cfg.tiers
    assert "free" in cfg.tiers


def test_tier_order_escalation() -> None:
    cfg = load_model_config(path=Path("agents/models.yaml"))
    order_no = get_tier_order(cfg, requested_tier="free", allow_escalation=False)
    order_yes = get_tier_order(cfg, requested_tier="free", allow_escalation=True)
    assert order_no == ["free"]
    assert order_yes[0] == "free"
    assert len(order_yes) >= 1


def test_parse_json_object_with_wrapped_text() -> None:
    obj = parse_json_object("hello {\"action\":\"answer\",\"answer\":\"ok\"} bye")
    assert obj is not None
    assert obj["action"] == "answer"


def test_tool_cache_roundtrip(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11)
    db.set_tool_cache("web_search", "abc", {"content": "cached"}, fetched_at=now, ttl_seconds=60)
    cached = db.get_tool_cache("web_search", "abc", now)
    assert cached is not None
    assert cached["content"] == "cached"
    expired = db.get_tool_cache("web_search", "abc", now + timedelta(seconds=120))
    assert expired is None


def test_validate_action_rejects_unknown_tool() -> None:
    cfg = ModelConfig(
        default_tier="free",
        tiers={
            "free": TierSpec(
                name="free",
                description="x",
                models=(ModelSpec(id="openrouter/free"),),
            )
        },
    )
    loop = AgentLoop(model_config=cfg, api_key="k", registry=build_default_registry(), app_config={})
    action, details = loop._validate_action({"action": "tool", "tool": "nope", "args": {}})
    assert action is None
    assert "unknown tool" in str(details).lower()


def test_loop_budget_blocked_on_small_step_budget(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11)
    cfg = ModelConfig(
        default_tier="free",
        tiers={
            "free": TierSpec(
                name="free",
                description="x",
                models=(ModelSpec(id="openrouter/free"),),
            )
        },
    )
    loop = AgentLoop(
        model_config=cfg,
        api_key=None,
        registry=build_default_registry(),
        app_config={"agent.max_steps": 1, "agent.max_step_input_tokens": 10},
    )
    req = AgentRequest(
        question="Tell me long answer about everything",
        context_text="Context",
        directive_text="Directive",
        requested_tier="free",
        allow_tier_escalation=False,
    )
    settings = Settings(
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
    tool_ctx = ToolContext(user_id=1, now=now, db=db, settings=settings, config={})
    result = loop.run(req, tool_ctx)
    assert result.status == "budget_blocked"


def test_run_llm_agent_audit_includes_intent_telemetry(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11)
    captured: dict[str, object] = {}

    def _capture_audit(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(db, "add_admin_audit", _capture_audit)

    settings = Settings(
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
    res = run_llm_agent(
        db=db,
        settings=settings,
        user_id=123,
        now=now,
        question="search for productivity tips",
    )
    payload = captured.get("payload")
    assert isinstance(payload, dict)
    assert "prompt_tokens" in payload
    assert "matched_tags" in payload
    assert "loaded_tools_count" in payload
    assert "loaded_tools" in payload
    assert payload["loaded_tools_count"] >= 1
    assert "web_search" in payload["loaded_tools"]
    assert "search" in payload["matched_tags"]
    assert res["loaded_tools_count"] >= 1
