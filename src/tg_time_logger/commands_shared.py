from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.gamification import get_title


def build_keyboard(*, timer_running: bool = False) -> ReplyKeyboardMarkup:
    if timer_running:
        return ReplyKeyboardMarkup(
            [[KeyboardButton("\u23f9 Stop Timer")]],
            resize_keyboard=True,
        )
    rows = [
        [KeyboardButton("Log"), KeyboardButton("Spend"), KeyboardButton("Timer")],
        [KeyboardButton("Status"), KeyboardButton("Undo")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get("settings")
    assert isinstance(settings, Settings)
    return settings


def touch_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, int, object]:
    assert update.effective_user is not None
    assert update.effective_chat is not None
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    from tg_time_logger.time_utils import now_local

    now = now_local(get_settings(context).tz)
    get_db(context).upsert_user_profile(user_id=user_id, chat_id=chat_id, seen_at=now)
    return user_id, chat_id, now


async def send_level_ups(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    top_category: str,
    level_ups: list,
    total_productive_minutes: int,
    xp_remaining: int,
) -> None:
    if not level_ups:
        return

    msg = update.effective_message
    if msg is None:
        return

    for lvl_event in level_ups:
        title = get_title(lvl_event.level)
        text = (
            f"\u2b50 Level {lvl_event.level} \u2014 {title}!\n"
            f"Bonus: +{lvl_event.bonus_fun_minutes}m fun\n"
            f"Total: {total_productive_minutes // 60}h productive"
        )
        await msg.reply_text(text)
