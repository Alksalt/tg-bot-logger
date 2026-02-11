from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from tg_time_logger.commands_shared import get_settings, touch_user
from tg_time_logger.db import Database
from tg_time_logger.llm_router import LlmRoute
from tg_time_logger.quests import ensure_weekly_quests, evaluate_quest_progress
from tg_time_logger.time_utils import week_range_for


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


async def cmd_quests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)
    settings = get_settings(context)
    if not db.is_feature_enabled("quests"):
        await update.effective_message.reply_text("Quests are currently disabled by admin.")
        return

    if context.args and context.args[0].lower() == "history":
        week = week_range_for(now)
        history = db.list_quest_history(user_id, week.start, week.end)
        if not history:
            await update.effective_message.reply_text("No quest history this week.")
            return
        lines = ["Quest history:"]
        for q in history:
            lines.append(f"- [{q.status}] {q.title} (+{q.reward_fun_minutes}m)")
        await update.effective_message.reply_text("\n".join(lines))
        return

    ensure_weekly_quests(
        db,
        user_id,
        now,
        llm_enabled=settings.llm_enabled and db.is_feature_enabled("llm"),
        llm_route=LlmRoute(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        ),
    )
    active = db.list_active_quests(user_id, now)
    if not active:
        await update.effective_message.reply_text("No active quests.")
        return

    lines = ["⚔️ Active quests:"]
    for q in active:
        p = evaluate_quest_progress(db, user_id, q, now)
        lines.append(f"- {q.title} ({q.difficulty}): {p.current}/{p.target} {p.unit} | +{q.reward_fun_minutes}m")
    await update.effective_message.reply_text("\n".join(lines))


def register_quest_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("quests", cmd_quests))
