from __future__ import annotations

import secrets
import shlex
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from tg_time_logger.agents.orchestration.runner import run_search_tool
from tg_time_logger.commands_shared import get_settings, get_user_language, touch_user
from tg_time_logger.db import Database
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.i18n import localize
from tg_time_logger.service import compute_status
from tg_time_logger.shop_pricing import nok_to_fun_minutes, parse_nok_literal, pick_nok_candidate
from tg_time_logger.shop import monthly_budget_remaining

PENDING_PRICE_ADDS_KEY = "shop_pending_price_adds"
PENDING_TTL_MINUTES = 20


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


def _parse_shop_add(raw_args: list[str], minutes_per_nok: int = 3) -> tuple[str, str, int, float | None]:
    raw = _normalize_smart_quotes(" ".join(raw_args))
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()

    if len(parts) < 3:
        raise ValueError("Usage: /shop add <emoji> \"name\" <cost_minutes|duration|nok_value> [nok_value]")

    emoji = parts[0]
    cost_idx = len(parts) - 1
    nok: float | None = None

    explicit_nok = parse_nok_literal(parts[cost_idx])
    if explicit_nok is not None:
        name = " ".join(parts[1:cost_idx]).strip()
        if not name:
            raise ValueError("Usage: /shop add <emoji> \"name\" <cost_minutes|duration|nok_value> [nok_value]")
        cost = nok_to_fun_minutes(explicit_nok, minutes_per_nok)
        return emoji, name, cost, explicit_nok

    # Optional trailing NOK metadata when cost is given in minutes/duration.
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
        raise ValueError("Usage: /shop add <emoji> \"name\" <cost_minutes|duration|nok_value> [nok_value]")

    return emoji, name, cost, nok


def _parse_shop_price(raw_args: list[str]) -> tuple[str, str, str]:
    raw = _normalize_smart_quotes(" ".join(raw_args))
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()
    if len(parts) < 3:
        raise ValueError("Usage: /shop price <emoji> \"name\" <query>")
    emoji = parts[0]
    name = parts[1].strip()
    query = " ".join(parts[2:]).strip()
    if not name or not query:
        raise ValueError("Usage: /shop price <emoji> \"name\" <query>")
    return emoji, name, query


def _minutes_per_nok(db: Database) -> int:
    raw = db.get_app_config_value("economy.nok_to_fun_minutes")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 3
    return max(1, value)


def _shop_pending(context: ContextTypes.DEFAULT_TYPE) -> dict[str, dict[str, object]]:
    store = context.application.bot_data.get(PENDING_PRICE_ADDS_KEY)
    if isinstance(store, dict):
        return store
    created: dict[str, dict[str, object]] = {}
    context.application.bot_data[PENDING_PRICE_ADDS_KEY] = created
    return created


def _cleanup_pending(context: ContextTypes.DEFAULT_TYPE, now_iso: str) -> None:
    now_val = now_iso
    store = _shop_pending(context)
    stale: list[str] = []
    for token, payload in store.items():
        expires = str(payload.get("expires_at", ""))
        if expires and expires <= now_val:
            stale.append(token)
    for token in stale:
        store.pop(token, None)


def _parse_price_args(raw_args: list[str]) -> tuple[list[str], bool]:
    normalized: list[str] = []
    auto_add = False
    for arg in raw_args:
        if arg.strip().lower() == "--add":
            auto_add = True
            continue
        normalized.append(arg)
    return normalized, auto_add


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = _db(context)
    settings = get_settings(context)
    lang = get_user_language(context, user_id)
    _cleanup_pending(context, now.isoformat())
    if not db.is_feature_enabled("shop"):
        await update.effective_message.reply_text(localize(lang, "Shop is currently disabled by admin.", "Магазин зараз вимкнений адміністратором."))
        return

    ratio = _minutes_per_nok(db)

    if not context.args:
        view = compute_status(db, user_id, now)
        budget_left = monthly_budget_remaining(db, user_id, now)
        lines = [
            localize(lang, "🛍️ Shop (fun balance: {bal}m)", "🛍️ Магазин (баланс fun: {bal}хв)", bal=view.economy.remaining_fun_minutes),
            localize(lang, "Price conversion: 1 NOK = {ratio} fun min", "Конвертація: 1 NOK = {ratio} fun хв", ratio=ratio),
        ]
        if budget_left is not None:
            lines.append(localize(lang, "Monthly budget left: {mins}m", "Залишок місячного бюджету: {mins}хв", mins=budget_left))
        for item in db.list_shop_items(user_id):
            if item.nok_value and item.nok_value > 0:
                lines.append(
                    f"{item.id}. {item.emoji} {item.name} — {item.cost_fun_minutes}m (~{int(round(item.nok_value))} NOK)"
                )
            else:
                lines.append(f"{item.id}. {item.emoji} {item.name} — {item.cost_fun_minutes}m")
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "add":
        try:
            emoji, name, cost, nok = _parse_shop_add(context.args[1:], ratio)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        item = db.add_shop_item(user_id, name, emoji, cost, nok, now)
        if nok is not None:
            await update.effective_message.reply_text(
                (
                    localize(
                        lang,
                        "Added shop item {id}: {emoji} {name} ({cost}m)\nBased on {nok} NOK at 1 NOK = {ratio} fun min",
                        "Додано товар {id}: {emoji} {name} ({cost}хв)\nНа основі {nok} NOK при 1 NOK = {ratio} fun хв",
                        id=item.id,
                        emoji=item.emoji,
                        name=item.name,
                        cost=item.cost_fun_minutes,
                        nok=int(round(nok)),
                        ratio=ratio,
                    )
                )
            )
        else:
            await update.effective_message.reply_text(
                localize(
                    lang,
                    "Added shop item {id}: {emoji} {name} ({cost}m)",
                    "Додано товар {id}: {emoji} {name} ({cost}хв)",
                    id=item.id,
                    emoji=item.emoji,
                    name=item.name,
                    cost=item.cost_fun_minutes,
                )
            )
        return

    if action == "remove" and len(context.args) >= 2 and context.args[1].isdigit():
        ok = db.deactivate_shop_item(user_id, int(context.args[1]))
        await update.effective_message.reply_text(localize(lang, "Item removed", "Товар видалено") if ok else localize(lang, "Item not found", "Товар не знайдено"))
        return

    if action == "price":
        if not db.is_feature_enabled("search"):
            await update.effective_message.reply_text(localize(lang, "Search is disabled by admin, cannot estimate NOK price.", "Пошук вимкнений адміністратором, не можу оцінити ціну в NOK."))
            return
        price_args, auto_add = _parse_price_args(context.args[1:])
        try:
            emoji, name, query = _parse_shop_price(price_args)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        pending = await update.effective_message.reply_text(localize(lang, "Checking web prices...", "Перевіряю ціни в інтернеті..."))
        res = run_search_tool(
            db=db,
            settings=settings,
            user_id=user_id,
            now=now,
            query=query,
            max_results=6,
        )
        if not res["ok"]:
            await pending.edit_text(localize(lang, "Price search failed: {err}", "Помилка пошуку цін: {err}", err=res["content"]))
            return
        provider = str(res.get("metadata", {}).get("provider") or "unknown")
        cached = bool(res.get("metadata", {}).get("cached", False))
        content = str(res.get("content", "")).strip()
        meta = f"{provider}{', cached' if cached else ''}"
        nok_guess = pick_nok_candidate(content)
        if nok_guess is None:
            await pending.edit_text(
                (
                    localize(lang, 'Could not detect a NOK price from results ({meta}).', 'Не вдалося визначити ціну в NOK з результатів ({meta}).', meta=meta) + "\n" +
                    localize(lang, 'Use manual add: /shop add <emoji> "name" <minutes> [nok]', 'Використай ручне додавання: /shop add <emoji> "name" <minutes> [nok]') + "\n\n" +
                    f"Top results:\n{content[:2500]}"
                )
            )
            return
        cost_minutes = nok_to_fun_minutes(nok_guess, ratio)
        suggested_nok = int(round(nok_guess))
        if auto_add:
            token = secrets.token_urlsafe(8)
            _shop_pending(context)[token] = {
                "user_id": user_id,
                "emoji": emoji,
                "name": name,
                "cost": cost_minutes,
                "nok": suggested_nok,
                "expires_at": (now + timedelta(minutes=PENDING_TTL_MINUTES)).isoformat(),
            }
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=localize(lang, "Confirm add", "Підтвердити"),
                            callback_data=f"shop_price_add:{token}",
                        ),
                        InlineKeyboardButton(
                            text=localize(lang, "Cancel", "Скасувати"),
                            callback_data=f"shop_price_cancel:{token}",
                        ),
                    ]
                ]
            )
            await pending.edit_text(
                (
                    localize(lang, 'Price scout ({meta})', 'Скан цін ({meta})', meta=meta) + "\n" +
                    localize(lang, 'Detected price: ~{nok} NOK', 'Виявлена ціна: ~{nok} NOK', nok=suggested_nok) + "\n" +
                    localize(lang, 'Rate: 1 NOK = {ratio} fun min', 'Курс: 1 NOK = {ratio} fun хв', ratio=ratio) + "\n" +
                    localize(lang, 'Suggested cost: {cost}m', 'Рекомендована ціна: {cost}хв', cost=cost_minutes) + "\n\n" +
                    localize(lang, 'Top results:', 'Топ результатів:') + f"\n{content[:1800]}"
                ),
                reply_markup=kb,
            )
            return

        suggested_cmd = f'/shop add {emoji} "{name}" {cost_minutes}m {suggested_nok}'
        await pending.edit_text(
            (
                localize(lang, 'Price scout ({meta})', 'Скан цін ({meta})', meta=meta) + "\n" +
                localize(lang, 'Detected price: ~{nok} NOK', 'Виявлена ціна: ~{nok} NOK', nok=suggested_nok) + "\n" +
                localize(lang, 'Rate: 1 NOK = {ratio} fun min', 'Курс: 1 NOK = {ratio} fun хв', ratio=ratio) + "\n" +
                localize(lang, 'Suggested cost: {cost}m', 'Рекомендована ціна: {cost}хв', cost=cost_minutes) + "\n\n" +
                localize(lang, 'Suggested command:', 'Рекомендована команда:') + "\n" +
                f"{suggested_cmd}\n\n" +
                localize(lang, 'Top results:', 'Топ результатів:') + f"\n{content[:2200]}"
            )
        )
        return

    if action == "budget" and len(context.args) >= 2:
        value = context.args[1].lower()
        if value in {"off", "none", "0"}:
            db.update_shop_budget(user_id, None)
            await update.effective_message.reply_text(localize(lang, "Shop monthly budget disabled", "Місячний бюджет магазину вимкнено"))
            return
        if not value.isdigit():
            await update.effective_message.reply_text(localize(lang, "Usage: /shop budget <minutes>|off", "Використання: /shop budget <minutes>|off"))
            return
        db.update_shop_budget(user_id, int(value))
        await update.effective_message.reply_text(localize(lang, "Shop monthly budget set to {value}m", "Місячний бюджет магазину: {value}хв", value=value))
        return

    # --- buy (was /redeem + /freeze) ---
    if action == "buy":
        sub_args = context.args[1:]
        if not sub_args:
            await update.effective_message.reply_text(localize(lang, "Usage: /shop buy <id|name> OR /shop buy history OR /shop buy freeze", "Використання: /shop buy <id|name> OR /shop buy history OR /shop buy freeze"))
            return
        sub = sub_args[0].lower()
        if sub == "history":
            rows = db.list_redemptions(user_id, limit=20)
            if not rows:
                await update.effective_message.reply_text(localize(lang, "No redemptions yet.", "Покупок ще немає."))
                return
            lines = [localize(lang, "Redemption history:", "Історія покупок:")]
            for r in rows:
                lines.append(f"- {r['emoji']} {r['name']} ({r['fun_minutes_spent']}m)")
            await update.effective_message.reply_text("\n".join(lines))
            return
        if sub == "freeze":
            view = compute_status(db, user_id, now)
            if view.economy.remaining_fun_minutes < 200:
                await update.effective_message.reply_text(localize(lang, "Need at least 200 fun minutes to buy a streak freeze.", "Потрібно щонайменше 200 fun хвилин для покупки freeze."))
                return
            freeze_date = now.date() + timedelta(days=1)
            if db.has_freeze_on_date(user_id, freeze_date):
                await update.effective_message.reply_text(localize(lang, "Freeze already active for tomorrow.", "Freeze вже активний на завтра."))
                return
            db.add_entry(user_id=user_id, kind="spend", category="spend", minutes=200, note=f"Streak freeze for {freeze_date.isoformat()}", created_at=now, source="freeze")
            db.create_freeze(user_id, freeze_date, now)
            await update.effective_message.reply_text(
                localize(lang, "🧊 Streak freeze purchased for {date} (-200 fun minutes).", "🧊 Freeze для серії куплено на {date} (-200 fun хвилин).", date=freeze_date.isoformat())
            )
            return
        # buy item by id or name
        identifier = " ".join(sub_args)
        item = db.find_shop_item(user_id, identifier)
        if not item:
            await update.effective_message.reply_text(localize(lang, "Shop item not found", "Товар не знайдено"))
            return
        view = compute_status(db, user_id, now)
        spendable = view.economy.remaining_fun_minutes + view.economy.saved_fun_minutes
        if spendable < item.cost_fun_minutes:
            await update.effective_message.reply_text(localize(lang, "Not enough fun minutes for this redemption", "Недостатньо fun хвилин для цієї покупки"))
            return
        budget_left = monthly_budget_remaining(db, user_id, now)
        if budget_left is not None and budget_left < item.cost_fun_minutes:
            await update.effective_message.reply_text(localize(lang, "Monthly budget exceeded. Remaining: {mins}m", "Місячний бюджет перевищено. Залишок: {mins}хв", mins=budget_left))
            return
        from_fund = min(item.cost_fun_minutes, max(view.economy.saved_fun_minutes, 0))
        moved = db.withdraw_from_savings(user_id, from_fund, now)
        from_remaining = item.cost_fun_minutes - moved
        db.add_redemption(user_id, item.id, item.cost_fun_minutes, now)
        db.add_entry(user_id=user_id, kind="spend", category="spend", minutes=item.cost_fun_minutes, note=f"Redeem: {item.name}", created_at=now, source="redeem")
        await update.effective_message.reply_text(
            localize(lang, "{emoji} Redeemed: {name}! -{cost} fun min\nUsed from fund: {fund}m | from remaining: {remain}m", "{emoji} Придбано: {name}! -{cost} fun хв\nЗ фонду: {fund}хв | із залишку: {remain}хв", emoji=item.emoji, name=item.name, cost=item.cost_fun_minutes, fund=moved, remain=from_remaining)
        )
        return

    # --- save (was /save with no args) ---
    if action == "save":
        if not db.is_feature_enabled("savings"):
            await update.effective_message.reply_text(localize(lang, "Savings fund is currently disabled by admin.", "Фонд заощаджень зараз вимкнений адміністратором."))
            return
        goal = db.get_active_savings_goal(user_id)
        if not goal:
            await update.effective_message.reply_text(
                localize(lang, "No save fund yet. Use /shop fund <duration> or /shop goal <duration> [name].", "Фонду ще немає. Використай /shop fund <duration> або /shop goal <duration> [name].")
            )
            return
        pct = (goal.saved_fun_minutes / goal.target_fun_minutes * 100) if goal.target_fun_minutes else 0
        settings_user = db.get_settings(user_id)
        sunday = settings_user.sunday_fund_percent
        await update.effective_message.reply_text(
            localize(lang, "🏦 Save fund\nGoal: {name}\nProgress: {saved}/{target}m ({pct:.1f}%)\nSunday auto-transfer: {sunday}\nUse /shop fund <duration> to add minutes.", "🏦 Фонд збереження\nЦіль: {name}\nПрогрес: {saved}/{target}хв ({pct:.1f}%)\nНедільний автопереказ: {sunday}\nВикористай /shop fund <duration> для поповнення.", name=goal.name, saved=goal.saved_fun_minutes, target=goal.target_fun_minutes, pct=pct, sunday=("off" if sunday == 0 else f"{sunday}% on"))
        )
        return

    # --- fund/deposit (was /save fund) ---
    if action in {"fund", "deposit"} and len(context.args) >= 2:
        if not db.is_feature_enabled("savings"):
            await update.effective_message.reply_text(localize(lang, "Savings fund is currently disabled by admin.", "Фонд заощаджень зараз вимкнений адміністратором."))
            return
        try:
            minutes = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        view = compute_status(db, user_id, now)
        if view.economy.remaining_fun_minutes < minutes:
            await update.effective_message.reply_text(localize(lang, "Not enough available fun minutes to deposit", "Недостатньо доступних fun хвилин для внеску"))
            return
        db.ensure_fund_goal(user_id, now)
        goal = db.deposit_to_savings(user_id, minutes, now)
        if not goal:
            await update.effective_message.reply_text(localize(lang, "Could not update save fund right now. Try again.", "Не вдалося оновити фонд збереження. Спробуй ще раз."))
            return
        await update.effective_message.reply_text(
            localize(lang, "Deposited {mins}m into '{name}' ({saved}/{target})", "Додано {mins}хв до '{name}' ({saved}/{target})", mins=minutes, name=goal.name, saved=goal.saved_fun_minutes, target=goal.target_fun_minutes)
        )
        return

    # --- goal (was /save goal) ---
    if action == "goal" and len(context.args) >= 2:
        if not db.is_feature_enabled("savings"):
            await update.effective_message.reply_text(localize(lang, "Savings fund is currently disabled by admin.", "Фонд заощаджень зараз вимкнений адміністратором."))
            return
        try:
            target = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        name = " ".join(context.args[2:]).strip() or "Save fund"
        goal = db.upsert_active_savings_goal(user_id, name, target, now)
        await update.effective_message.reply_text(
            localize(lang, "Save goal set: {name} ({saved}/{target}m)", "Ціль збереження встановлено: {name} ({saved}/{target}хв)", name=goal.name, saved=goal.saved_fun_minutes, target=goal.target_fun_minutes)
        )
        return

    # --- sunday (was /save sunday) ---
    if action == "sunday":
        if len(context.args) == 1:
            percent = db.get_settings(user_id).sunday_fund_percent
            await update.effective_message.reply_text(
                localize(lang, "Sunday auto-transfer is {mode}.\nUse /shop sunday on 50|60|70 or /shop sunday off.", "Недільний автопереказ: {mode}.\nВикористай /shop sunday on 50|60|70 або /shop sunday off.", mode=("off" if percent == 0 else f"on ({percent}%)"))
            )
            return
        sub = context.args[1].lower()
        if sub == "off":
            db.update_sunday_fund_percent(user_id, 0)
            await update.effective_message.reply_text(localize(lang, "Sunday auto-transfer disabled.", "Недільний автопереказ вимкнено."))
            return
        if sub == "on":
            if len(context.args) < 3 or context.args[2] not in {"50", "60", "70"}:
                await update.effective_message.reply_text(localize(lang, "Usage: /shop sunday on 50|60|70", "Використання: /shop sunday on 50|60|70"))
                return
            percent = int(context.args[2])
            db.update_sunday_fund_percent(user_id, percent)
            await update.effective_message.reply_text(localize(lang, "Sunday auto-transfer enabled: {p}% of available fun.", "Недільний автопереказ увімкнено: {p}% доступного fun.", p=percent))
            return
        await update.effective_message.reply_text(localize(lang, "Usage: /shop sunday on 50|60|70 OR /shop sunday off", "Використання: /shop sunday on 50|60|70 OR /shop sunday off"))
        return

    # --- auto (was /save auto) ---
    if action == "auto" and len(context.args) >= 2:
        try:
            minutes = parse_duration_to_minutes(context.args[1])
        except DurationParseError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        db.update_auto_save_minutes(user_id, minutes)
        await update.effective_message.reply_text(localize(lang, "Auto-save set to {mins}m/day", "Автозбереження: {mins}хв/день", mins=minutes))
        return

    # --- cancel (was /save cancel) ---
    if action == "cancel" and len(context.args) >= 2 and context.args[1].isdigit():
        ok = db.cancel_savings_goal(user_id, int(context.args[1]))
        await update.effective_message.reply_text(localize(lang, "Savings goal cancelled", "Ціль збереження скасовано") if ok else localize(lang, "Goal not found", "Ціль не знайдено"))
        return

    await update.effective_message.reply_text(localize(lang, "Usage: /shop, /shop add, /shop buy, /shop save, /shop fund, /shop goal, /shop price, /shop remove, /shop budget", "Використання: /shop, /shop add, /shop buy, /shop save, /shop fund, /shop goal, /shop price, /shop remove, /shop budget"))


async def handle_shop_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)
    data = query.data or ""
    if ":" not in data:
        return
    action, token = data.split(":", maxsplit=1)
    store = _shop_pending(context)
    payload = store.get(token)
    if not payload:
        await query.edit_message_text(localize(lang, "Request expired. Run /shop price --add again.", "Запит застарів. Запусти /shop price --add ще раз."))
        return

    expires_at = str(payload.get("expires_at") or "")
    if expires_at and expires_at <= now.isoformat():
        store.pop(token, None)
        await query.edit_message_text(localize(lang, "Request expired. Run /shop price --add again.", "Запит застарів. Запусти /shop price --add ще раз."))
        return

    if int(payload.get("user_id") or 0) != user_id:
        await query.answer(localize(lang, "This confirmation is not yours.", "Це підтвердження не для тебе."), show_alert=True)
        return

    if action == "shop_price_cancel":
        store.pop(token, None)
        await query.edit_message_text(localize(lang, "Cancelled. Item was not added.", "Скасовано. Товар не додано."))
        return

    if action != "shop_price_add":
        return

    db = _db(context)
    item = db.add_shop_item(
        user_id=user_id,
        name=str(payload.get("name") or "Item"),
        emoji=str(payload.get("emoji") or "🎁"),
        cost_fun_minutes=int(payload.get("cost") or 0),
        nok_value=float(payload.get("nok") or 0),
        created_at=now,
    )
    store.pop(token, None)
    await query.edit_message_text(
        localize(
            lang,
            "Added shop item {id}: {emoji} {name} ({cost}m)",
            "Додано товар {id}: {emoji} {name} ({cost}хв)",
            id=item.id,
            emoji=item.emoji,
            name=item.name,
            cost=item.cost_fun_minutes,
        )
    )


def register_shop_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CallbackQueryHandler(handle_shop_callbacks, pattern=r"^shop_price_(?:add|cancel):"))
