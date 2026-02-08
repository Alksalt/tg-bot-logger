from __future__ import annotations

from tg_time_logger.config import load_settings
from tg_time_logger.db import Database
from tg_time_logger.logging_setup import setup_logging
from tg_time_logger.telegram_bot import build_application


def run_bot() -> None:
    setup_logging()
    settings = load_settings()
    db = Database(settings.database_path)

    application = build_application(settings, db)
    application.run_polling()
