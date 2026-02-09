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
        raw = " ".join(context.args[1:])
        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = context.args[1:]
        if len(parts) < 3:
            await update.effective_message.reply_text("Usage: /shop add <emoji> \"name\" <cost_minutes> [nok_value]")
            return
        emoji = parts[0]
        name = parts[1]
        if not parts[2].isdigit():
            await update.effective_message.reply_text("Cost must be an integer number of fun minutes")
            return
        cost = int(parts[2])
        nok = float(parts[3]) if len(parts) > 3 else None
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
    if view.economy.remaining_fun_minutes < item.cost_fun_minutes:
        await update.effective_message.reply_text("Not enough fun minutes for this redemption")
        return

    budget_left = monthly_budget_remaining(db, user_id, now)
    if budget_left is not None and budget_left < item.cost_fun_minutes:
        await update.effective_message.reply_text(f"Monthly budget exceeded. Remaining: {budget_left}m")
        return

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
        f"{item.emoji} Redeemed: {item.name}! Enjoy your reward. -{item.cost_fun_minutes} fun min"
    )


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)

    if not context.args:
        goals = db.list_savings_goals(user_id)
        if not goals:
            await update.effective_message.reply_text("No savings goals. Use /save <target> \"name\"")
            return
        lines = ["🏦 Savings goals:"]
        for g in goals:
            pct = (g.saved_fun_minutes / g.target_fun_minutes * 100) if g.target_fun_minutes else 0
            lines.append(
                f"{g.id}. {g.name} [{g.status}] {g.saved_fun_minutes}/{g.target_fun_minutes} ({pct:.1f}%)"
            )
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "deposit" and len(context.args) >= 2:
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
            await update.effective_message.reply_text("No active savings goal")
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

    if action == "complete" and len(context.args) >= 2 and context.args[1].isdigit():
        ok = db.complete_savings_goal(user_id, int(context.args[1]), now)
        await update.effective_message.reply_text("Savings goal marked complete" if ok else "Goal not found")
        return

    try:
        target = parse_duration_to_minutes(context.args[0])
    except DurationParseError:
        await update.effective_message.reply_text(
            "Usage: /save <target_minutes|duration> <name> or /save deposit <duration>"
        )
        return
    name = " ".join(context.args[1:]).strip() or "Savings goal"
    goal = db.create_savings_goal(user_id, name, target, now)
    await update.effective_message.reply_text(f"Created savings goal {goal.id}: {goal.name} ({goal.target_fun_minutes}m)")


def register_shop_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("save", cmd_save))
