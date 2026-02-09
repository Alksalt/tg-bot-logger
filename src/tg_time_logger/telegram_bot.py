from __future__ import annotations

from telegram.ext import Application

from tg_time_logger.commands_core import register_core_handlers
from tg_time_logger.commands_quests import register_quest_handlers
from tg_time_logger.commands_shop import register_shop_handlers
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


def build_application(settings: Settings, db: Database) -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["db"] = db
    app.bot_data["settings"] = settings

    register_core_handlers(app)
    register_quest_handlers(app)
    register_shop_handlers(app)

    return app
