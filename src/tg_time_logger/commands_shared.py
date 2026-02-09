from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.llm_messages import LlmContext, level_up_message
from tg_time_logger.llm_router import LlmRoute


def build_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("+15m Study", callback_data="log:study:15"),
            InlineKeyboardButton("+30m Build", callback_data="log:build:30"),
            InlineKeyboardButton("+30m Training", callback_data="log:training:30"),
        ],
        [
            InlineKeyboardButton("+60m Build", callback_data="log:build:60"),
            InlineKeyboardButton("-15m Fun", callback_data="spend:15"),
            InlineKeyboardButton("-30m Fun", callback_data="spend:30"),
        ],
        [
            InlineKeyboardButton("-60m Fun", callback_data="spend:60"),
            InlineKeyboardButton("Status", callback_data="status"),
            InlineKeyboardButton("Week", callback_data="week"),
        ],
        [
            InlineKeyboardButton("Undo last", callback_data="undo"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get("settings")
    assert isinstance(settings, Settings)
    return settings


def llm_context(context: ContextTypes.DEFAULT_TYPE) -> LlmContext:
    settings = get_settings(context)
    return LlmContext(
        enabled=settings.llm_enabled,
        route=LlmRoute(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        ),
    )


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
        text = level_up_message(
            llm_context(context),
            level=lvl_event.level,
            total_hours=total_productive_minutes / 60,
            bonus=lvl_event.bonus_fun_minutes,
            xp_remaining=xp_remaining,
            top_category=top_category,
        )
        await msg.reply_text(text)
