from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    database_path: Path
    tz: str
    openai_api_key: str | None
    llm_enabled: bool


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
    openai_api_key = os.getenv("OPENAI_API_KEY")
    llm_enabled = _parse_bool(os.getenv("LLM_ENABLED", "0"), default=False)

    return Settings(
        telegram_bot_token=token,
        database_path=db_path,
        tz=tz,
        openai_api_key=openai_api_key,
        llm_enabled=llm_enabled,
    )
