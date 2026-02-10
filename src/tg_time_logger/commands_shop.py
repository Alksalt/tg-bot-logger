from __future__ import annotations

import shlex

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from tg_time_logger.commands_shared import touch_user
from tg_time_logger.db import Database
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.service import compute_status
from tg_time_logger.shop import monthly_budget_remaining


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    assert isinstance(db, Database)
    return db


def _normalize_smart_quotes(value: str) -> str:
    return (
        value.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _parse_shop_add(raw_args: list[str]) -> tuple[str, str, int, float | None]:
    raw = _normalize_smart_quotes(" ".join(raw_args))
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()

    if len(parts) < 3:
        raise ValueError("Usage: /shop add <emoji> \"name\" <cost_minutes|duration> [nok_value]")

    emoji = parts[0]
    nok: float | None = None
    cost_idx = len(parts) - 1

    # Optional NOK value at the end.
    if len(parts) >= 4:
        try:
            candidate_nok = float(parts[-1])
            _ = parse_duration_to_minutes(parts[-2])
            nok = candidate_nok
            cost_idx = len(parts) - 2
        except (ValueError, DurationParseError):
            nok = None
            cost_idx = len(parts) - 1

    try:
        cost = parse_duration_to_minutes(parts[cost_idx])
    except DurationParseError as exc:
        raise ValueError(f"Invalid cost duration: {exc}") from exc

    name = " ".join(parts[1:cost_idx]).strip()
    if not name:
        raise ValueError("Usage: /shop add <emoji> \"name\" <cost_minutes|duration> [nok_value]")

    return emoji, name, cost, nok


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)

    if not context.args:
        view = compute_status(db, user_id, now)
        budget_left = monthly_budget_remaining(db, user_id, now)
        lines = [f"🛍️ Shop (fun balance: {view.economy.remaining_fun_minutes}m)"]
        if budget_left is not None:
            lines.append(f"Monthly budget left: {budget_left}m")
        for item in db.list_shop_items(user_id):
            lines.append(f"{item.id}. {item.emoji} {item.name} — {item.cost_fun_minutes}m")
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "add":
        try:
            emoji, name, cost, nok = _parse_shop_add(context.args[1:])
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        item = db.add_shop_item(user_id, name, emoji, cost, nok, now)
        await update.effective_message.reply_text(f"Added shop item {item.id}: {item.emoji} {item.name} ({item.cost_fun_minutes}m)")
        return

    if action == "remove" and len(context.args) >= 2 and context.args[1].isdigit():
        ok = db.deactivate_shop_item(user_id, int(context.args[1]))
        await update.effective_message.reply_text("Item removed" if ok else "Item not found")
        return

    if action == "budget" and len(context.args) >= 2:
        value = context.args[1].lower()
        if value in {"off", "none", "0"}:
            db.update_shop_budget(user_id, None)
            await update.effective_message.reply_text("Shop monthly budget disabled")
            return
        if not value.isdigit():
            await update.effective_message.reply_text("Usage: /shop budget <minutes>|off")
            return
        db.update_shop_budget(user_id, int(value))
        await update.effective_message.reply_text(f"Shop monthly budget set to {value}m")
        return

    await update.effective_message.reply_text("Usage: /shop, /shop add, /shop remove, /shop budget")


async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)

    if not context.args:
        await update.effective_message.reply_text("Usage: /redeem <item_id|item_name> OR /redeem history")
        return

    if context.args[0].lower() == "history":
        rows = db.list_redemptions(user_id, limit=20)
        if not rows:
            await update.effective_message.reply_text("No redemptions yet.")
            return
        lines = ["Redemption history:"]
        for r in rows:
            lines.append(f"- {r['emoji']} {r['name']} ({r['fun_minutes_spent']}m)")
        await update.effective_message.reply_text("\n".join(lines))
        return

    identifier = " ".join(context.args)
    item = db.find_shop_item(user_id, identifier)
    if not item:
        await update.effective_message.reply_text("Shop item not found")
        return

    view = compute_status(db, user_id, now)
    spendable_for_shop = view.economy.remaining_fun_minutes + view.economy.saved_fun_minutes
    if spendable_for_shop < item.cost_fun_minutes:
        await update.effective_message.reply_text("Not enough fun minutes for this redemption")
        return

    budget_left = monthly_budget_remaining(db, user_id, now)
    if budget_left is not None and budget_left < item.cost_fun_minutes:
        await update.effective_message.reply_text(f"Monthly budget exceeded. Remaining: {budget_left}m")
        return

    from_fund = min(item.cost_fun_minutes, max(view.economy.saved_fun_minutes, 0))
    moved = db.withdraw_from_savings(user_id, from_fund, now)
    from_remaining = item.cost_fun_minutes - moved

    db.add_redemption(user_id, item.id, item.cost_fun_minutes, now)
    db.add_entry(
        user_id=user_id,
        kind="spend",
        category="spend",
        minutes=item.cost_fun_minutes,
        note=f"Redeem: {item.name}",
        created_at=now,
        source="redeem",
    )

    await update.effective_message.reply_text(
        (
            f"{item.emoji} Redeemed: {item.name}! -{item.cost_fun_minutes} fun min\n"
            f"Used from fund: {moved}m | from remaining: {from_remaining}m"
        )
    )


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)

    if not context.args:
        goal = db.get_active_savings_goal(user_id)
        if not goal:
            await update.effective_message.reply_text(
                "No save fund yet. Use /save goal <duration> [name]."
            )
            return
        pct = (goal.saved_fun_minutes / goal.target_fun_minutes * 100) if goal.target_fun_minutes else 0
        await update.effective_message.reply_text(
            (
                "🏦 Save fund\n"
                f"Goal: {goal.name}\n"
                f"Progress: {goal.saved_fun_minutes}/{goal.target_fun_minutes}m ({pct:.1f}%)\n"
                "Use /save fund <duration> to add minutes."
            )
        )
        return

    action = context.args[0].lower()
    if action == "goal" and len(context.args) >= 2:
        try:
            target = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        name = " ".join(context.args[2:]).strip() or "Save fund"
        goal = db.upsert_active_savings_goal(user_id, name, target, now)
        await update.effective_message.reply_text(
            f"Save goal set: {goal.name} ({goal.saved_fun_minutes}/{goal.target_fun_minutes}m)"
        )
        return

    if action in {"fund", "deposit"} and len(context.args) >= 2:
        try:
            minutes = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        view = compute_status(db, user_id, now)
        if view.economy.remaining_fun_minutes < minutes:
            await update.effective_message.reply_text("Not enough available fun minutes to deposit")
            return
        goal = db.deposit_to_savings(user_id, minutes, now)
        if not goal:
            await update.effective_message.reply_text("No save goal. Use /save goal <duration> first.")
            return
        await update.effective_message.reply_text(
            f"Deposited {minutes}m into '{goal.name}' ({goal.saved_fun_minutes}/{goal.target_fun_minutes})"
        )
        return

    if action == "auto" and len(context.args) >= 2:
        try:
            minutes = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        db.update_auto_save_minutes(user_id, minutes)
        await update.effective_message.reply_text(f"Auto-save set to {minutes}m/day")
        return

    if action == "cancel" and len(context.args) >= 2 and context.args[1].isdigit():
        ok = db.cancel_savings_goal(user_id, int(context.args[1]))
        await update.effective_message.reply_text("Savings goal cancelled" if ok else "Goal not found")
        return

    await update.effective_message.reply_text(
        "Usage: /save, /save goal <duration> [name], /save fund <duration>, /save auto <duration>"
    )


def register_shop_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("save", cmd_save))
