from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from tg_time_logger.commands_shared import get_user_language, touch_user
from tg_time_logger.help_guides import (
    COMMAND_DESCRIPTIONS,
    GUIDE_TITLES,
    HELP_TOPICS,
    get_guide_page,
    list_guide_topics,
    resolve_guide_topic,
)
from tg_time_logger.i18n import localize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------


def _guide_nav_keyboard(topic: str, page: int, total: int, lang: str) -> InlineKeyboardMarkup:
    """Build navigation keyboard for guide pages."""
    nav_row: list[InlineKeyboardButton] = []

    if page > 1:
        nav_row.append(InlineKeyboardButton(
            "\u2190 Prev",
            callback_data=f"guide:{topic}:{page - 1}",
        ))

    nav_row.append(InlineKeyboardButton(
        f"{page}/{total}",
        callback_data="guide:noop",
    ))

    if page < total:
        nav_row.append(InlineKeyboardButton(
            "Next \u2192",
            callback_data=f"guide:{topic}:{page + 1}",
        ))

    back_row = [InlineKeyboardButton(
        localize(lang, "\u21a9 Back to Help", "\u21a9 \u041d\u0430\u0437\u0430\u0434"),
        callback_data="guide:back",
    )]

    return InlineKeyboardMarkup([nav_row, back_row])


def _topic_keyboard(guide_topic: str, lang: str) -> InlineKeyboardMarkup:
    """Single button to open the guide for a topic."""
    title = GUIDE_TITLES.get(guide_topic, "Guide")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"\U0001f4d6 {title}",
            callback_data=f"guide:{guide_topic}:1",
        ),
    ]])


# ---------------------------------------------------------------------------
# Overview text
# ---------------------------------------------------------------------------


def _help_overview_text() -> str:
    lines = ["Available commands:\n"]
    for cmd, desc in COMMAND_DESCRIPTIONS.items():
        lines.append(f"/{cmd} \u2014 {desc}")
    lines.append("")
    guides = list_guide_topics()
    guide_names = ", ".join(guides)
    lines.append(f"Guides: {guide_names}")
    lines.append("Type /help <topic> and tap the Guide button.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    lang = get_user_language(context, user_id)

    if not context.args:
        await update.effective_message.reply_text(_help_overview_text())
        return

    topic = context.args[0].strip().lower().lstrip("/")
    help_text = HELP_TOPICS.get(topic)
    guide_topic = resolve_guide_topic(topic)

    if not help_text and not guide_topic:
        await update.effective_message.reply_text(
            localize(
                lang,
                "No help for '{topic}'. Try /help to see all commands.",
                "\u041d\u0435\u043c\u0430\u0454 \u0434\u043e\u0432\u0456\u0434\u043a\u0438 \u0434\u043b\u044f '{topic}'. \u0412\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u0430\u0439 /help.",
                topic=topic,
            )
        )
        return

    text = help_text or f"Use the guide below for detailed help on '{topic}'."
    if guide_topic:
        await update.effective_message.reply_text(
            text,
            reply_markup=_topic_keyboard(guide_topic, lang),
        )
    else:
        await update.effective_message.reply_text(text)


async def handle_guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, _ = touch_user(update, context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    parts = data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]

    if action == "noop":
        return

    if action == "back":
        try:
            await query.edit_message_text(_help_overview_text())
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise
        return

    if len(parts) != 3:
        return

    topic = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        return

    text, total = get_guide_page(topic, page)
    if text is None:
        try:
            await query.edit_message_text(
                localize(lang, "Guide not found.", "\u0414\u043e\u0432\u0456\u0434\u043a\u0443 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e.")
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise
        return

    title = GUIDE_TITLES.get(topic, topic.title())
    header = f"{title} ({page}/{total})\n{'=' * 30}\n\n"

    try:
        await query.edit_message_text(
            header + text,
            reply_markup=_guide_nav_keyboard(topic, page, total, lang),
        )
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_help_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(
        handle_guide_callback,
        pattern=r"^guide:",
    ))
