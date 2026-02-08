from __future__ import annotations

import asyncio

from tg_time_logger.config import load_settings
from tg_time_logger.db import Database
from tg_time_logger.logging_setup import setup_logging
from tg_time_logger.telegram_bot import build_application


def run_bot() -> None:
    setup_logging()
    settings = load_settings()
    db = Database(settings.database_path)

    # Python 3.14 does not auto-create a default event loop in main thread.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    application = build_application(settings, db)
    application.run_polling()
