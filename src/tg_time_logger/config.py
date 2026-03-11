from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    database_path: Path
    tz: str
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


def load_settings() -> Settings:
    _load_env_file(Path(".env"))

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    db_path = Path(os.getenv("DATABASE_PATH", "./data/app.db"))
    tz = os.getenv("TZ", "Europe/Oslo")
    admin_port_raw = os.getenv("ADMIN_PORT", "8080")
    try:
        admin_port = int(admin_port_raw)
    except ValueError:
        admin_port = 8080

    return Settings(
        telegram_bot_token=token,
        database_path=db_path,
        tz=tz,
        admin_panel_token=os.getenv("ADMIN_PANEL_TOKEN"),
        admin_host=os.getenv("ADMIN_HOST", "127.0.0.1"),
        admin_port=admin_port,
    )
