from __future__ import annotations

from telegram import BotCommand
from telegram.ext import Application

from tg_time_logger.commands_core import register_core_handlers, register_unknown_handler
from tg_time_logger.commands_help import register_help_handlers
from tg_time_logger.commands_settings import register_settings_handlers
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


def build_application(settings: Settings, db: Database) -> Application:

    async def setup_bot_commands(app: Application) -> None:
        commands = [
            BotCommand("start", "Welcome & onboarding"),
            BotCommand("log", "Log time manually (e.g. /log 30m build)"),
            BotCommand("spend", "Log fun time (e.g. /spend 1h)"),
            BotCommand("timer", "Start a live timer (e.g. /timer study)"),
            BotCommand("stop", "Stop active timer"),
            BotCommand("status", "Show current progress"),
            BotCommand("undo", "Undo last entry"),
            BotCommand("help", "Show all commands"),
            BotCommand("settings", "Reminders, quiet hours, unspend"),
        ]
        await app.bot.set_my_commands(commands)

    app = Application.builder().token(settings.telegram_bot_token).post_init(setup_bot_commands).build()
    app.bot_data["db"] = db
    app.bot_data["settings"] = settings

    register_help_handlers(app)
    register_core_handlers(app)
    register_settings_handlers(app)
    register_unknown_handler(app)

    return app
