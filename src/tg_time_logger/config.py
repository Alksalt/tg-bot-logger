from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tg_time_logger.llm_router import LlmRoute, load_router_config, resolve_route


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    database_path: Path
    tz: str
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_api_key: str | None
    llm_router_config_path: Path
    admin_panel_token: str | None
    admin_host: str
    admin_port: int


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    _load_env_file(Path(".env"))

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    db_path = Path(os.getenv("DATABASE_PATH", "./data/app.db"))
    tz = os.getenv("TZ", "Europe/Oslo")
    llm_enabled = _parse_bool(os.getenv("LLM_ENABLED", "0"), default=False)
    router_path = Path(os.getenv("LLM_ROUTER_CONFIG", "./llm_router.yaml"))
    router_cfg = load_router_config(router_path)
    route: LlmRoute = resolve_route(
        config=router_cfg,
        provider_override=os.getenv("LLM_PROVIDER"),
        model_override=os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL"),
        env_getter=os.getenv,
    )
    admin_port_raw = os.getenv("ADMIN_PORT", "8080")
    try:
        admin_port = int(admin_port_raw)
    except ValueError:
        admin_port = 8080

    return Settings(
        telegram_bot_token=token,
        database_path=db_path,
        tz=tz,
        llm_enabled=llm_enabled,
        llm_provider=route.provider,
        llm_model=route.model,
        llm_api_key=route.api_key,
        llm_router_config_path=router_path,
        admin_panel_token=os.getenv("ADMIN_PANEL_TOKEN"),
        admin_host=os.getenv("ADMIN_HOST", "127.0.0.1"),
        admin_port=admin_port,
    )
