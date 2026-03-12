from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from tg_time_logger.commands_shared import get_db, touch_user
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    db = get_db(context)

    if not context.args:
        user_settings = db.get_settings(user_id)
        reminders = "on" if user_settings.reminders_enabled else "off"
        quiet = user_settings.quiet_hours or "not set"
        goal = f"{user_settings.daily_goal_minutes}m"
        await update.effective_message.reply_text(
            (
                f"Settings:\n"
                f"  Reminders: {reminders}\n"
                f"  Quiet hours: {quiet}\n"
                f"  Daily goal: {goal}\n\n"
                "Change with:\n"
                "  /settings reminders <on|off>\n"
                "  /settings quiet <HH:MM-HH:MM>\n"
                "  /settings goal <duration>\n"
                "  /settings unspend <amount>"
            )
        )
        return

    action = context.args[0].lower()

    # --- reminders ---
    if action == "reminders":
        if len(context.args) < 2 or context.args[1].lower() not in {"on", "off"}:
            await update.effective_message.reply_text("Usage: /settings reminders on|off")
            return
        enabled = context.args[1].lower() == "on"
        db.update_reminders_enabled(user_id, enabled)
        await update.effective_message.reply_text(
            "Reminders enabled" if enabled else "Reminders disabled"
        )
        return

    # --- quiet ---
    if action == "quiet":
        if len(context.args) < 2:
            await update.effective_message.reply_text("Usage: /settings quiet HH:MM-HH:MM")
            return
        raw = context.args[1]
        if "-" not in raw or ":" not in raw:
            await update.effective_message.reply_text(
                "Invalid format. Example: /settings quiet 22:00-08:00"
            )
            return
        db.update_quiet_hours(user_id, raw)
        await update.effective_message.reply_text(f"Quiet hours set to {raw}")
        return

    # --- goal ---
    if action == "goal":
        if len(context.args) < 2:
            await update.effective_message.reply_text("Usage: /settings goal <duration>\nExample: /settings goal 2h")
            return
        try:
            minutes = parse_duration_to_minutes(context.args[1])
        except DurationParseError:
            await update.effective_message.reply_text("Invalid duration. Examples: 2h, 90m, 1h30m")
            return
        db.update_daily_goal(user_id, minutes)
        await update.effective_message.reply_text(f"Daily goal set to {minutes}m")
        return

    # --- unspend ---
    if action == "unspend":
        if len(context.args) < 2:
            await update.effective_message.reply_text("Usage: /settings unspend <amount>")
            return
        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text(
                "Invalid amount. Must be positive."
            )
            return

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, deduct", callback_data=f"unspend:y:{amount}"),
                InlineKeyboardButton("Cancel", callback_data="unspend:n"),
            ]
        ])
        await update.effective_message.reply_text(
            f"Deduct {amount} fun minutes from balance?",
            reply_markup=kb,
        )
        return

    await update.effective_message.reply_text(
        "/settings usage: reminders | quiet | goal | unspend"
    )


async def handle_unspend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    data = query.data or ""

    if data == "unspend:n":
        await query.message.edit_text("Cancelled.")
        return

    # unspend:y:amount
    parse = data.split(":")
    if len(parse) < 3:
        await query.message.edit_text("Invalid request.")
        return
    try:
        amount = int(parse[2])
    except (TypeError, ValueError):
        await query.message.edit_text("Invalid amount.")
        return
    if amount <= 0:
        await query.message.edit_text("Invalid amount.")
        return

    db.add_entry(
        user_id=user_id,
        kind="spend",
        category="spend",
        minutes=amount,
        note=f"Manual deduction (-{amount})",
        created_at=now,
        source="manual",
    )
    await query.message.edit_text(f"Deducted {amount}m.")


def register_settings_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(handle_unspend_callback, pattern=r"^unspend:"))
