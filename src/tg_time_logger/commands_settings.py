from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from tg_time_logger.commands_shared import get_db, get_user_language, touch_user
from tg_time_logger.i18n import localize, normalize_language_code, t


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not context.args:
        # Show current settings overview
        user_settings = db.get_settings(user_id)
        lang_code = normalize_language_code(user_settings.language_code, default="en")
        reminders = "on" if user_settings.reminders_enabled else "off"
        quiet = user_settings.quiet_hours or "not set"
        await update.effective_message.reply_text(
            localize(
                lang,
                f"Settings:\n  Language: {lang_code}\n  Reminders: {reminders}\n  Quiet hours: {quiet}\n\nChange with:\n  /settings lang <en|uk>\n  /settings reminders <on|off>\n  /settings quiet <HH:MM-HH:MM>",
                f"Налаштування:\n  Мова: {lang_code}\n  Нагадування: {reminders}\n  Тихі години: {quiet}\n\nЗмінити:\n  /settings lang <en|uk>\n  /settings reminders <on|off>\n  /settings quiet <HH:MM-HH:MM>",
            )
        )
        return

    action = context.args[0].lower()

    # --- lang ---
    if action == "lang":
        current = get_user_language(context, user_id)
        if len(context.args) < 2:
            await update.effective_message.reply_text(t("lang_show", current, code=current))
            return
        raw_requested = context.args[1].strip().lower()
        if not (raw_requested.startswith("en") or raw_requested.startswith("uk")):
            await update.effective_message.reply_text(t("lang_usage", current))
            return
        requested = normalize_language_code(raw_requested, default=current)
        db.update_language_code(user_id, requested)
        await update.effective_message.reply_text(t("lang_set", requested, code=requested))
        return

    # --- reminders ---
    if action == "reminders":
        if len(context.args) < 2 or context.args[1].lower() not in {"on", "off"}:
            await update.effective_message.reply_text(localize(lang, "Usage: /settings reminders on|off", "Використання: /settings reminders on|off"))
            return
        enabled = context.args[1].lower() == "on"
        db.update_reminders_enabled(user_id, enabled)
        await update.effective_message.reply_text(
            localize(lang, "Reminders enabled" if enabled else "Reminders disabled", "Нагадування увімкнено" if enabled else "Нагадування вимкнено")
        )
        return

    # --- quiet ---
    if action == "quiet":
        if len(context.args) < 2:
            await update.effective_message.reply_text(localize(lang, "Usage: /settings quiet HH:MM-HH:MM", "Використання: /settings quiet HH:MM-HH:MM"))
            return
        raw = context.args[1]
        if "-" not in raw or ":" not in raw:
            await update.effective_message.reply_text(localize(lang, "Invalid format. Example: /settings quiet 22:00-08:00", "Невірний формат. Приклад: /settings quiet 22:00-08:00"))
            return
        db.update_quiet_hours(user_id, raw)
        await update.effective_message.reply_text(localize(lang, "Quiet hours set to {raw}", "Тихі години встановлено: {raw}", raw=raw))
        return

    # --- unspend ---
    if action == "unspend":
        if len(context.args) < 2:
            await update.effective_message.reply_text(localize(lang, "Usage: /settings unspend <amount>", "Використання: /settings unspend <amount>"))
            return
        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.effective_message.reply_text(localize(lang, "Invalid amount. Must be positive.", "Невірна кількість. Має бути більше 0."))
            return

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, deduct", callback_data=f"unspend:y:{amount}"),
                InlineKeyboardButton("❌ Cancel", callback_data="unspend:n"),
            ]
        ])
        await update.effective_message.reply_text(
            localize(lang, "Deduct {amount} fun minutes from balance?", "Відняти {amount} хвилин відпочинку з балансу?", amount=amount),
            reply_markup=kb,
        )
        return

    await update.effective_message.reply_text(
        localize(lang, "Usage: /settings, /settings lang, /settings reminders, /settings quiet", "Використання: /settings, /settings lang, /settings reminders, /settings quiet")
    )


def register_settings_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(handle_unspend_callback, pattern=r"^unspend:"))


async def handle_unspend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    if data == "unspend:n":
        await query.message.edit_text(localize(lang, "Cancelled.", "Скасовано."))
        return

    # unspend:y:amount
    parse = data.split(":")
    if len(parse) < 3:
        await query.message.edit_text(localize(lang, "Invalid request.", "Невірний запит."))
        return
    try:
        amount = int(parse[2])
    except (TypeError, ValueError):
        await query.message.edit_text(localize(lang, "Invalid amount.", "Невірна кількість."))
        return
    if amount <= 0:
        await query.message.edit_text(localize(lang, "Invalid amount.", "Невірна кількість."))
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
    await query.message.edit_text(localize(lang, "Deducted {amount}m.", "Віднято {amount}хв.", amount=amount))
