from __future__ import annotations

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.llm_parser import parse_free_form_with_llm
from tg_time_logger.messages import entry_removed_message, status_message, week_message
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import now_local, week_start_date

logger = logging.getLogger(__name__)


def build_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("+15m Productive", callback_data="productive:15"),
            InlineKeyboardButton("+30m Productive", callback_data="productive:30"),
            InlineKeyboardButton("+60m Productive", callback_data="productive:60"),
        ],
        [
            InlineKeyboardButton("-15m Fun", callback_data="spend:15"),
            InlineKeyboardButton("-30m Fun", callback_data="spend:30"),
            InlineKeyboardButton("-60m Fun", callback_data="spend:60"),
        ],
        [
            InlineKeyboardButton("Status", callback_data="status"),
            InlineKeyboardButton("Week", callback_data="week"),
            InlineKeyboardButton("Undo last", callback_data="undo"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get("settings")
    assert isinstance(settings, Settings)
    return settings


def _touch_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, int, object]:
    assert update.effective_user is not None
    assert update.effective_chat is not None
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    now = now_local(_settings(context).tz)
    _db(context).upsert_user_profile(user_id=user_id, chat_id=chat_id, seen_at=now)
    return user_id, chat_id, now


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /log <duration> [note]")
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    note = " ".join(context.args[1:]).strip() or None
    _db(context).add_entry(
        user_id=user_id,
        kind="productive",
        minutes=minutes,
        note=note,
        created_at=now,
    )

    view = compute_status(_db(context), user_id, now)
    await update.effective_message.reply_text(
        f"Logged {minutes}m productive.\n\n{status_message(view)}",
        reply_markup=build_keyboard(),
    )


async def cmd_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /spend <duration> [note]")
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    note = " ".join(context.args[1:]).strip() or None
    _db(context).add_entry(
        user_id=user_id,
        kind="spend",
        minutes=minutes,
        note=note,
        created_at=now,
    )

    view = compute_status(_db(context), user_id, now)
    await update.effective_message.reply_text(
        f"Logged spend {minutes}m.\n\n{status_message(view)}",
        reply_markup=build_keyboard(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    view = compute_status(_db(context), user_id, now)
    await update.effective_message.reply_text(status_message(view), reply_markup=build_keyboard())


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    db = _db(context)
    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(week_message(view), reply_markup=build_keyboard())


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    removed = _db(context).undo_last_entry(user_id=user_id, deleted_at=now)
    if not removed:
        await update.effective_message.reply_text("Nothing to undo")
        return
    await update.effective_message.reply_text(entry_removed_message(removed), reply_markup=build_keyboard())


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    db = _db(context)

    if not context.args:
        await update.effective_message.reply_text("Usage: /plan set <duration> OR /plan show")
        return

    action = context.args[0].lower()
    if action == "show":
        plan = db.get_plan_target(user_id, week_start_date(now))
        if not plan:
            await update.effective_message.reply_text("No plan set for this week")
            return
        target_total = plan.work_minutes + plan.study_minutes + plan.learn_minutes
        await update.effective_message.reply_text(f"Plan this week (productive): {target_total}m")
        return

    if action != "set" or len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /plan set <duration>")
        return

    try:
        target_minutes = parse_duration_to_minutes(context.args[1])
    except DurationParseError as exc:
        await update.effective_message.reply_text(f"Plan parse error: {exc}")
        return

    db.set_plan_target(
        user_id=user_id,
        week_start=week_start_date(now),
        work_minutes=target_minutes,
        study_minutes=0,
        learn_minutes=0,
    )
    await update.effective_message.reply_text(f"Plan saved for week (productive): {target_minutes}m")


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = _touch_user(update, context)
    if not context.args:
        await update.effective_message.reply_text("Usage: /reminders on|off")
        return

    action = context.args[0].lower()
    if action not in {"on", "off"}:
        await update.effective_message.reply_text("Usage: /reminders on|off")
        return

    enabled = action == "on"
    _db(context).update_reminders_enabled(user_id, enabled)
    await update.effective_message.reply_text(f"Reminders {'enabled' if enabled else 'disabled'}")


async def cmd_quiet_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = _touch_user(update, context)
    if not context.args:
        await update.effective_message.reply_text("Usage: /quiet_hours HH:MM-HH:MM")
        return

    raw = context.args[0]
    if "-" not in raw or ":" not in raw:
        await update.effective_message.reply_text("Invalid format. Example: /quiet_hours 22:00-08:00")
        return

    _db(context).update_quiet_hours(user_id, raw)
    await update.effective_message.reply_text(f"Quiet hours set to {raw}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)

    if context.args and context.args[0].lower() == "productive":
        note = " ".join(context.args[1:]).strip() or None
    else:
        note = " ".join(context.args).strip() or None

    existing, created = _db(context).get_or_start_timer(user_id, now, note)
    if existing:
        await update.effective_message.reply_text(
            f"A timer is already running since {existing.started_at.strftime('%H:%M')}"
        )
        return

    await update.effective_message.reply_text(f"Productive timer started at {created.started_at.strftime('%H:%M')}")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    db = _db(context)
    session = db.stop_timer(user_id)
    if not session:
        await update.effective_message.reply_text("No active timer")
        return

    elapsed = now - session.started_at
    minutes = int(elapsed.total_seconds() // 60)
    if minutes <= 0:
        minutes = 1

    db.add_entry(
        user_id=user_id,
        kind="productive",
        minutes=minutes,
        note=session.note,
        created_at=now,
        source="timer",
    )

    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(
        f"Stopped timer: logged {minutes}m productive.\n\n{status_message(view)}",
        reply_markup=build_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = _touch_user(update, context)
    db = _db(context)
    data = query.data or ""

    if data.startswith("productive:") or data.startswith("spend:"):
        kind, minutes_raw = data.split(":", maxsplit=1)
        minutes = int(minutes_raw)
        db.add_entry(
            user_id=user_id,
            kind=kind,
            minutes=minutes,
            created_at=now,
            source="button",
        )
        view = compute_status(db, user_id, now)
        verb = "productive" if kind == "productive" else "fun spend"
        await query.message.reply_text(
            f"Logged {minutes}m {verb}.\n\n{status_message(view)}",
            reply_markup=build_keyboard(),
        )
        return

    if data == "status":
        view = compute_status(db, user_id, now)
        await query.message.reply_text(status_message(view), reply_markup=build_keyboard())
        return

    if data == "week":
        view = compute_status(db, user_id, now)
        await query.message.reply_text(week_message(view), reply_markup=build_keyboard())
        return

    if data == "undo":
        removed = db.undo_last_entry(user_id, now)
        if not removed:
            await query.message.reply_text("Nothing to undo")
            return
        await query.message.reply_text(entry_removed_message(removed), reply_markup=build_keyboard())


async def handle_free_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = _touch_user(update, context)
    settings = _settings(context)
    if not settings.llm_enabled or not settings.openai_api_key:
        return

    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return

    try:
        parsed = parse_free_form_with_llm(text, settings.openai_api_key)
    except Exception:
        logger.exception("LLM parse failed")
        return

    if not parsed:
        return

    db = _db(context)
    db.add_entry(
        user_id=user_id,
        kind="productive" if parsed.action == "log" else "spend",
        minutes=parsed.minutes,
        note=parsed.note,
        created_at=now,
        source="llm",
    )

    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(f"Parsed and logged via LLM.\n\n{status_message(view)}")


def build_application(settings: Settings, db: Database) -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["db"] = db
    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("spend", cmd_spend))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("reminders", cmd_reminders))
    app.add_handler(CommandHandler("quiet_hours", cmd_quiet_hours))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))

    return app
