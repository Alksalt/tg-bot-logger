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

from tg_time_logger.commands_shared import (
    build_keyboard,
    get_db,
    send_level_ups,
    touch_user,
)
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES
from tg_time_logger.messages import entry_removed_message, status_message
from tg_time_logger.service import add_productive_entry, compute_status, normalize_category

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline keyboard helpers
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = [
    ("Study", "study"),
    ("Build", "build"),
    ("Training", "training"),
    ("Job", "job"),
]


def _category_picker(callback_prefix: str, *, include_spend: bool = False) -> InlineKeyboardMarkup:
    """Build a category picker inline keyboard."""
    buttons = [
        InlineKeyboardButton(label, callback_data=f"{callback_prefix}:{key}")
        for label, key in _CATEGORY_LABELS
    ]
    rows = [buttons]
    if include_spend:
        rows.append([InlineKeyboardButton("Spend", callback_data=f"{callback_prefix}:spend")])
    return InlineKeyboardMarkup(rows)


def _duration_picker(callback_prefix: str) -> InlineKeyboardMarkup:
    """Build a duration picker inline keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10m", callback_data=f"{callback_prefix}:10"),
            InlineKeyboardButton("20m", callback_data=f"{callback_prefix}:20"),
            InlineKeyboardButton("30m", callback_data=f"{callback_prefix}:30"),
            InlineKeyboardButton("45m", callback_data=f"{callback_prefix}:45"),
        ],
        [
            InlineKeyboardButton("1h", callback_data=f"{callback_prefix}:60"),
            InlineKeyboardButton("1.5h", callback_data=f"{callback_prefix}:90"),
            InlineKeyboardButton("2h", callback_data=f"{callback_prefix}:120"),
            InlineKeyboardButton("3h", callback_data=f"{callback_prefix}:180"),
        ],
    ])


# ---------------------------------------------------------------------------
# Shared action helpers (used by both commands and menu/callback handlers)
# ---------------------------------------------------------------------------

async def _do_log(update, context, user_id, now, minutes, category, note=None, source="manual"):
    """Log a productive entry and send the response."""
    db = get_db(context)
    outcome = add_productive_entry(
        db=db,
        user_id=user_id,
        minutes=minutes,
        category=category,
        note=note,
        created_at=now,
        source=source,
        timer_mode=False,
    )
    view = compute_status(db, user_id, now)
    msg = update.callback_query.message if update.callback_query else update.effective_message
    await msg.reply_text(
        (
            f"Logged {minutes}m {outcome.entry.category}.\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.streak_mult:.1f}x streak)\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned}m\n\n"
            f"{status_message(view, username=update.effective_user.username)}"
        ),
        reply_markup=build_keyboard(),
    )
    await send_level_ups(
        update,
        context,
        top_category=outcome.top_week_category,
        level_ups=outcome.level_ups,
        total_productive_minutes=view.all_time.productive_minutes,
        xp_remaining=view.xp_remaining_to_next,
    )


async def _do_spend(update, context, user_id, now, minutes, note=None, source="manual"):
    """Log a spend entry and send the response."""
    db = get_db(context)
    db.add_entry(
        user_id=user_id,
        kind="spend",
        category="spend",
        minutes=minutes,
        note=note,
        created_at=now,
        source=source,
    )
    view = compute_status(db, user_id, now)
    msg = update.callback_query.message if update.callback_query else update.effective_message
    await msg.reply_text(
        f"Logged spend {minutes}m.\n\n{status_message(view, username=update.effective_user.username)}",
        reply_markup=build_keyboard(),
    )


async def _do_status(update, context, user_id, now):
    """Send status message."""
    db = get_db(context)
    view = compute_status(db, user_id, now)
    msg = update.callback_query.message if update.callback_query else update.effective_message
    await msg.reply_text(
        status_message(view, username=update.effective_user.username),
        reply_markup=build_keyboard(),
    )


async def _do_undo(update, context, user_id, now):
    """Undo last entry."""
    removed = get_db(context).undo_last_entry(user_id=user_id, deleted_at=now)
    msg = update.callback_query.message if update.callback_query else update.effective_message
    if not removed:
        await msg.reply_text("Nothing to undo", reply_markup=build_keyboard())
        return
    await msg.reply_text(entry_removed_message(removed), reply_markup=build_keyboard())


async def _do_stop_timer(update, context, user_id, now):
    """Stop active timer and log the entry."""
    db = get_db(context)
    session = db.stop_timer(user_id)
    msg = update.callback_query.message if update.callback_query else update.effective_message
    if not session:
        await msg.reply_text("No active timer", reply_markup=build_keyboard())
        return

    elapsed = now - session.started_at
    minutes = max(int(elapsed.total_seconds() // 60), 1)

    if session.category == "spend":
        db.add_entry(
            user_id=user_id,
            kind="spend",
            category="spend",
            minutes=minutes,
            note=session.note,
            created_at=now,
            source="timer",
        )
        view = compute_status(db, user_id, now)
        await msg.reply_text(
            (
                f"⏱️ Spend session complete: {minutes}m\n\n"
                f"📝 Logged fun spend: {minutes} min\n\n"
                f"{status_message(view, username=update.effective_user.username)}"
            ),
            reply_markup=build_keyboard(),
        )
        return

    outcome = add_productive_entry(
        db=db,
        user_id=user_id,
        minutes=minutes,
        category=session.category,
        note=session.note,
        created_at=now,
        source="timer",
        timer_mode=True,
    )
    view = compute_status(db, user_id, now)
    await msg.reply_text(
        (
            f"⏱️ Session complete: {minutes}m ({outcome.entry.category})\n\n"
            f"📝 Logged: {minutes} min ({outcome.entry.category})\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.deep_mult:.1f}x deep work, {outcome.streak_mult:.1f}x streak)\n"
            f"🔥 Streak: {outcome.streak.current_streak} days\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned} min\n\n"
            f"{status_message(view, username=update.effective_user.username)}"
        ),
        reply_markup=build_keyboard(),
    )
    await send_level_ups(
        update,
        context,
        top_category=outcome.top_week_category,
        level_ups=outcome.level_ups,
        total_productive_minutes=view.all_time.productive_minutes,
        xp_remaining=view.xp_remaining_to_next,
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)

    if len(context.args) < 1:
        await update.effective_message.reply_text(
            "Usage: /log <duration> [study|build|training|job|other] [note]",
            reply_markup=build_keyboard(),
        )
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    tail = context.args[1:]

    # /log 20m other breakfast with coffee
    if tail and tail[0].lower() == "other":
        description = " ".join(tail[1:]).strip() or None
        get_db(context).add_entry(
            user_id=user_id,
            kind="other",
            category="other",
            minutes=minutes,
            note=description,
            created_at=now,
        )
        label = description or "other"
        await update.effective_message.reply_text(
            f"Noted: {minutes}m {label}",
            reply_markup=build_keyboard(),
        )
        return

    category = "build"
    if tail and tail[0].lower() in PRODUCTIVE_CATEGORIES:
        category = tail[0].lower()
        tail = tail[1:]
    note = " ".join(tail).strip() or None

    await _do_log(update, context, user_id, now, minutes, category, note)


async def cmd_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)

    if len(context.args) < 1:
        await update.effective_message.reply_text(
            "Usage: /spend <duration> [note]",
            reply_markup=build_keyboard(),
        )
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    note = " ".join(context.args[1:]).strip() or None
    await _do_spend(update, context, user_id, now, minutes, note)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    await _do_status(update, context, user_id, now)


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    await _do_undo(update, context, user_id, now)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram /start -- onboarding welcome message."""
    touch_user(update, context)
    await update.effective_message.reply_text(
        (
            "Welcome! I'm your productivity tracker.\n\n"
            "Quick start:\n"
            "  /log 30m study -- log 30 min of study\n"
            "  /timer study -- start a live timer\n"
            "  /spend 1h -- log 1h of fun time\n"
            "  /status -- see your progress\n"
            "  /help -- all commands\n\n"
            "Or use the buttons below!"
        ),
        reply_markup=build_keyboard(),
    )


async def cmd_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)

    category = "build"
    tail = context.args
    if tail and (tail[0].lower() in PRODUCTIVE_CATEGORIES or tail[0].lower() == "spend"):
        category = tail[0].lower()
        tail = tail[1:]
    note = " ".join(tail).strip() or None

    existing, created = get_db(context).get_or_start_timer(user_id, category, now, note)
    timer_kb = build_keyboard(timer_running=True)
    if existing:
        await update.effective_message.reply_text(
            f"A timer is already running for {existing.category} since {existing.started_at.strftime('%H:%M')}",
            reply_markup=timer_kb,
        )
        return

    if created.category != "spend":
        text = f"Timer started for {created.category} at {created.started_at.strftime('%H:%M')}"
    else:
        text = f"Spend timer started at {created.started_at.strftime('%H:%M')}"
    await update.effective_message.reply_text(text, reply_markup=timer_kb)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    await _do_stop_timer(update, context, user_id, now)


# ---------------------------------------------------------------------------
# Reply keyboard menu handler
# ---------------------------------------------------------------------------

async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle taps on the ReplyKeyboard buttons."""
    text = (update.effective_message.text or "").strip()

    if text == "Log":
        await update.effective_message.reply_text(
            "What did you work on?",
            reply_markup=_category_picker("menu:log:cat"),
        )
        return

    if text == "Spend":
        await update.effective_message.reply_text(
            "How long?",
            reply_markup=_duration_picker("menu:spend:dur"),
        )
        return

    if text == "Timer":
        await update.effective_message.reply_text(
            "Start timer for:",
            reply_markup=_category_picker("menu:timer:cat", include_spend=True),
        )
        return

    if text == "Status":
        user_id, _, now = touch_user(update, context)
        await _do_status(update, context, user_id, now)
        return

    if text == "Undo":
        user_id, _, now = touch_user(update, context)
        await _do_undo(update, context, user_id, now)
        return

    if text == "\u23f9 Stop Timer":
        user_id, _, now = touch_user(update, context)
        await _do_stop_timer(update, context, user_id, now)
        return

    # Anything else: ignore silently
    return


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    data = query.data or ""

    # --- New menu flow: log category selected -> show duration picker ---
    if data.startswith("menu:log:cat:"):
        cat = data.split(":")[-1]
        await query.message.edit_text(
            f"Log {cat} -- how long?",
            reply_markup=_duration_picker(f"menu:log:dur:{cat}"),
        )
        return

    # --- New menu flow: log duration selected -> actually log ---
    if data.startswith("menu:log:dur:"):
        parts = data.split(":")
        # menu:log:dur:<cat>:<min>
        cat = parts[3]
        minutes = int(parts[4])
        await _do_log(update, context, user_id, now, minutes, normalize_category(cat), source="button")
        return

    # --- New menu flow: spend duration selected -> actually log spend ---
    if data.startswith("menu:spend:dur:"):
        minutes = int(data.split(":")[-1])
        await _do_spend(update, context, user_id, now, minutes, source="button")
        return

    # --- New menu flow: timer category selected -> start timer ---
    if data.startswith("menu:timer:cat:"):
        cat = data.split(":")[-1]
        existing, created = db.get_or_start_timer(user_id, cat, now, None)
        timer_kb = build_keyboard(timer_running=True)
        if existing:
            await query.message.reply_text(
                f"A timer is already running for {existing.category} since {existing.started_at.strftime('%H:%M')}",
                reply_markup=timer_kb,
            )
            return
        if created.category != "spend":
            text = f"Timer started for {created.category} at {created.started_at.strftime('%H:%M')}"
        else:
            text = f"Spend timer started at {created.started_at.strftime('%H:%M')}"
        await query.message.reply_text(text, reply_markup=timer_kb)
        return

    # --- Legacy callback patterns (backward compat) ---

    if data.startswith("log:"):
        _, category, minutes_raw = data.split(":", maxsplit=2)
        minutes = int(minutes_raw)
        await _do_log(update, context, user_id, now, minutes, normalize_category(category), source="button")
        return

    if data.startswith("spend:"):
        _, minutes_raw = data.split(":", maxsplit=1)
        minutes = int(minutes_raw)
        await _do_spend(update, context, user_id, now, minutes, source="button")
        return

    if data == "status":
        await _do_status(update, context, user_id, now)
        return

    if data == "undo":
        await _do_undo(update, context, user_id, now)
        return

    if data == "timer:stop":
        await _do_stop_timer(update, context, user_id, now)
        return


# ---------------------------------------------------------------------------
# Unknown command handler
# ---------------------------------------------------------------------------

async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_user(update, context)
    await update.effective_message.reply_text(
        "Unknown command. Try /help to see available commands.",
        reply_markup=build_keyboard(),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_core_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("spend", cmd_spend))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler(["timer", "t"], cmd_timer))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(
        handle_callback,
        pattern=r"^(menu:|log:|spend:|status$|undo$|timer:stop$)",
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_text))


def register_unknown_handler(app: Application) -> None:
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
