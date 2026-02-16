from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from tg_time_logger.commands_shared import get_user_language, touch_user
from tg_time_logger.db import Database
from tg_time_logger.i18n import localize
from tg_time_logger.quests import evaluate_quest_progress, sync_quests_for_user
from tg_time_logger.time_utils import week_range_for


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


async def cmd_quests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)
    lang = get_user_language(context, user_id)
    if not db.is_feature_enabled("quests"):
        await update.effective_message.reply_text(localize(lang, "Quests are currently disabled by admin.", "Квести зараз вимкнені адміністратором."))
        return

    if context.args and context.args[0].lower() == "reset":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, reset", callback_data="quests_reset:y"),
                InlineKeyboardButton("❌ Cancel", callback_data="quests_reset:n"),
            ]
        ])
        await update.effective_message.reply_text(
            localize(
                lang,
                "Delete all your quests (active + history)?",
                "Видалити всі твої квести (активні + історію)?",
            ),
            reply_markup=kb,
        )
        return

    sync_quests_for_user(db, user_id, now)

    if context.args and context.args[0].lower() == "history":
        week = week_range_for(now)
        history = db.list_quest_history(user_id, week.start, week.end)
        if not history:
            await update.effective_message.reply_text(localize(lang, "No quest history this week.", "Цього тижня історії квестів немає."))
            return
        lines = [localize(lang, "Quest history:", "Історія квестів:")]
        for q in history:
            lines.append(f"- [{q.status}] {q.title} (+{q.reward_fun_minutes}m)")
        await update.effective_message.reply_text("\n".join(lines))
        return

    active = db.list_active_quests(user_id, now)
    if not active:
        await update.effective_message.reply_text(
            localize(
                lang,
                "No active quests.\nUse /llm quest easy|medium|hard [3|5|7|14|21] to generate one.",
                "Немає активних квестів.\nВикористай /llm quest easy|medium|hard [3|5|7|14|21], щоб згенерувати.",
            )
        )
        return

    lines = [localize(lang, "⚔️ Active quests:", "⚔️ Активні квести:")]
    for q in active:
        p = evaluate_quest_progress(db, user_id, q, now)
        lines.append(
            f"- {q.title} ({q.difficulty}, {q.duration_days}d): "
            f"{p.current}/{p.target} {p.unit} | +{q.reward_fun_minutes}m / -{q.penalty_fun_minutes}m"
        )
    await update.effective_message.reply_text("\n".join(lines))


async def handle_quests_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, _ = touch_user(update, context)
    db = _db(context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    if data == "quests_reset:n":
        await query.message.edit_text(localize(lang, "Cancelled.", "Скасовано."))
        return
    if data != "quests_reset:y":
        await query.message.edit_text(localize(lang, "Invalid request.", "Невірний запит."))
        return

    deleted_quests = db.delete_user_quests(user_id)
    deleted_proposals = db.clear_user_quest_proposals(user_id)
    await query.message.edit_text(
        localize(
            lang,
            "Quests reset: removed {q} quests and {p} proposals.",
            "Квести скинуто: видалено {q} квестів і {p} пропозицій.",
            q=deleted_quests,
            p=deleted_proposals,
        )
    )


def register_quest_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("quests", cmd_quests))
    app.add_handler(CallbackQueryHandler(handle_quests_reset_callback, pattern=r"^quests_reset:"))
