from __future__ import annotations

from telegram import BotCommand
from telegram.ext import Application

from tg_time_logger.commands_core import register_core_handlers, register_unknown_handler
from tg_time_logger.commands_help import register_help_handlers
from tg_time_logger.commands_llm import register_llm_handlers
from tg_time_logger.commands_quests import register_quest_handlers
from tg_time_logger.commands_settings import register_settings_handlers
from tg_time_logger.commands_shop import register_shop_handlers
from tg_time_logger.commands_todo import register_todo_handlers
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


def build_application(settings: Settings, db: Database) -> Application:

    async def setup_bot_commands(app: Application) -> None:
        commands = [
            BotCommand("start", "Welcome & onboarding"),
            BotCommand("status", "Show current progress"),
            BotCommand("quests", "View active quests"),
            BotCommand("shop", "Open the shop"),
            BotCommand("timer", "Start a live timer (e.g. /timer study)"),
            BotCommand("log", "Log time manually (e.g. /log 30m build)"),
            BotCommand("spend", "Log fun time (e.g. /spend 1h)"),
            BotCommand("help", "Show all commands"),
        ]
        await app.bot.set_my_commands(commands)

    app = Application.builder().token(settings.telegram_bot_token).post_init(setup_bot_commands).build()
    app.bot_data["db"] = db
    app.bot_data["settings"] = settings

    register_help_handlers(app)
    register_core_handlers(app)
    register_llm_handlers(app)
    register_quest_handlers(app)
    register_shop_handlers(app)
    register_settings_handlers(app)
    register_todo_handlers(app)
    register_unknown_handler(app)

    return app
