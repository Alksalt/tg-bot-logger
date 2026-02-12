from __future__ import annotations

import logging
from datetime import timedelta

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.orchestration.runner import run_llm_agent, run_search_tool
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from tg_time_logger.commands_shared import (
    build_keyboard,
    get_db,
    get_settings,
    get_user_language,
    send_level_ups,
    touch_user,
)
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES
from tg_time_logger.i18n import localize, normalize_language_code, t
from tg_time_logger.llm_parser import parse_free_form_with_llm
from tg_time_logger.llm_router import LlmRoute
from tg_time_logger.messages import entry_removed_message, status_message, week_message
from tg_time_logger.service import add_productive_entry, compute_status, normalize_category
from tg_time_logger.time_utils import week_range_for, week_start_date

logger = logging.getLogger(__name__)
LLM_DAILY_LIMIT = 10
LLM_COOLDOWN_SECONDS = 30



async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if len(context.args) < 1:
        await update.effective_message.reply_text(localize(lang, "Usage: /log <duration> [study|build|training|job] [note]", "Використання: /log <duration> [study|build|training|job] [note]"))
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    category = "build"
    tail = context.args[1:]
    if tail and tail[0].lower() in PRODUCTIVE_CATEGORIES:
        category = tail[0].lower()
        tail = tail[1:]
    note = " ".join(tail).strip() or None

    outcome = add_productive_entry(
        db=db,
        user_id=user_id,
        minutes=minutes,
        category=category,
        note=note,
        created_at=now,
        source="manual",
        timer_mode=False,
    )

    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(
        (
            f"Logged {minutes}m {outcome.entry.category}.\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.streak_mult:.1f}x streak)\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned}m\n\n"
            f"{status_message(view, username=update.effective_user.username, lang=lang)}"
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


async def cmd_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if len(context.args) < 1:
        await update.effective_message.reply_text(localize(lang, "Usage: /spend <duration> [note]", "Використання: /spend <duration> [note]"))
        return

    try:
        minutes = parse_duration_to_minutes(context.args[0])
    except DurationParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    note = " ".join(context.args[1:]).strip() or None
    db.add_entry(
        user_id=user_id,
        kind="spend",
        category="spend",
        minutes=minutes,
        note=note,
        created_at=now,
    )

    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(
        f"{localize(lang, 'Logged spend {minutes}m.', 'Додано витрати {minutes}хв.', minutes=minutes)}\n\n{status_message(view, username=update.effective_user.username, lang=lang)}",
        reply_markup=build_keyboard(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)
    view = compute_status(get_db(context), user_id, now)
    await update.effective_message.reply_text(
        status_message(view, username=update.effective_user.username, lang=lang),
        reply_markup=build_keyboard(),
    )


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(week_message(view, lang=lang), reply_markup=build_keyboard())


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    db = get_db(context)
    current = get_user_language(context, user_id)
    if not context.args:
        await update.effective_message.reply_text(t("lang_show", current, code=current))
        return

    raw_requested = context.args[0].strip().lower()
    if not (raw_requested.startswith("en") or raw_requested.startswith("uk")):
        await update.effective_message.reply_text(t("lang_usage", current))
        return
    requested = normalize_language_code(raw_requested, default=current)
    db.update_language_code(user_id, requested)
    await update.effective_message.reply_text(t("lang_set", requested, code=requested))


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not context.args:
        rules = db.list_user_rules(user_id)
        if not rules:
            await update.effective_message.reply_text(
                localize(lang, "No personal rules yet. Add one with /rules add <text>.", "Поки немає правил. Додай: /rules add <text>")
            )
            return
        lines = [localize(lang, "📘 Your rules:", "📘 Твої правила:")]
        for rule in rules:
            lines.append(f"{rule.id}. {rule.rule_text}")
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "add":
        text = " ".join(context.args[1:]).strip()
        if not text:
            await update.effective_message.reply_text(localize(lang, "Usage: /rules add <text>", "Використання: /rules add <text>"))
            return
        rule = db.add_user_rule(user_id, text, now)
        await update.effective_message.reply_text(localize(lang, "Rule saved ({id}).", "Правило збережено ({id}).", id=rule.id))
        return

    if action == "remove":
        if len(context.args) < 2 or not context.args[1].isdigit():
            await update.effective_message.reply_text(localize(lang, "Usage: /rules remove <id>", "Використання: /rules remove <id>"))
            return
        ok = db.remove_user_rule(user_id, int(context.args[1]))
        await update.effective_message.reply_text(localize(lang, "Rule removed.", "Правило видалено.") if ok else localize(lang, "Rule not found.", "Правило не знайдено."))
        return

    if action == "clear":
        count = db.clear_user_rules(user_id)
        await update.effective_message.reply_text(localize(lang, "Removed {count} rule(s).", "Видалено правил: {count}.", count=count))
        return

    await update.effective_message.reply_text(localize(lang, "Usage: /rules, /rules add, /rules remove, /rules clear", "Використання: /rules, /rules add, /rules remove, /rules clear"))


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)
    removed = get_db(context).undo_last_entry(user_id=user_id, deleted_at=now)
    if not removed:
        await update.effective_message.reply_text(localize(lang, "Nothing to undo", "Нічого скасовувати"))
        return
    await update.effective_message.reply_text(entry_removed_message(removed, lang=lang), reply_markup=build_keyboard())


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not context.args:
        await update.effective_message.reply_text(localize(lang, "Usage: /plan set <duration> OR /plan show", "Використання: /plan set <duration> OR /plan show"))
        return

    action = context.args[0].lower()
    if action == "show":
        plan = db.get_plan_target(user_id, week_start_date(now))
        if not plan:
            await update.effective_message.reply_text(localize(lang, "No plan set for this week", "План на цей тиждень не встановлено"))
            return
        done = db.sum_minutes(user_id, "productive", start=week_range_for(now).start, end=now)
        await update.effective_message.reply_text(
            localize(
                lang,
                "Plan this week: {target}m total productive | done {done}m",
                "План на тиждень: {target}хв продуктивно | виконано {done}хв",
                target=plan.total_target_minutes,
                done=done,
            )
        )
        return

    if action != "set" or len(context.args) < 2:
        await update.effective_message.reply_text(localize(lang, "Usage: /plan set <duration>", "Використання: /plan set <duration>"))
        return

    try:
        target_minutes = parse_duration_to_minutes(context.args[1])
    except DurationParseError as exc:
        await update.effective_message.reply_text(localize(lang, "Plan parse error: {err}", "Помилка розбору плану: {err}", err=exc))
        return

    db.set_plan_target(
        user_id=user_id,
        week_start=week_start_date(now),
        total_target_minutes=target_minutes,
        build_target_minutes=target_minutes,
    )
    await update.effective_message.reply_text(localize(lang, "Plan saved for week: {target}m total productive", "План збережено: {target}хв продуктивно на тиждень", target=target_minutes))


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    lang = get_user_language(context, user_id)
    if not context.args:
        await update.effective_message.reply_text(localize(lang, "Usage: /reminders on|off", "Використання: /reminders on|off"))
        return

    action = context.args[0].lower()
    if action not in {"on", "off"}:
        await update.effective_message.reply_text(localize(lang, "Usage: /reminders on|off", "Використання: /reminders on|off"))
        return

    enabled = action == "on"
    get_db(context).update_reminders_enabled(user_id, enabled)
    await update.effective_message.reply_text(
        localize(
            lang,
            "Reminders enabled" if enabled else "Reminders disabled",
            "Нагадування увімкнено" if enabled else "Нагадування вимкнено",
        )
    )


async def cmd_quiet_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    lang = get_user_language(context, user_id)
    if not context.args:
        await update.effective_message.reply_text(localize(lang, "Usage: /quiet_hours HH:MM-HH:MM", "Використання: /quiet_hours HH:MM-HH:MM"))
        return

    raw = context.args[0]
    if "-" not in raw or ":" not in raw:
        await update.effective_message.reply_text(localize(lang, "Invalid format. Example: /quiet_hours 22:00-08:00", "Невірний формат. Приклад: /quiet_hours 22:00-08:00"))
        return

    get_db(context).update_quiet_hours(user_id, raw)
    await update.effective_message.reply_text(localize(lang, "Quiet hours set to {raw}", "Тихі години встановлено: {raw}", raw=raw))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)

    category = "build"
    tail = context.args
    if tail and (tail[0].lower() in PRODUCTIVE_CATEGORIES or tail[0].lower() == "spend"):
        category = tail[0].lower()
        tail = tail[1:]
    note = " ".join(tail).strip() or None

    existing, created = get_db(context).get_or_start_timer(user_id, category, now, note)
    if existing:
        await update.effective_message.reply_text(
            localize(
                lang,
                "A timer is already running for {cat} since {time}",
                "Таймер вже запущено для {cat} з {time}",
                cat=existing.category,
                time=existing.started_at.strftime("%H:%M"),
            )
        )
        return

    await update.effective_message.reply_text(
        (
            localize(
                lang,
                "Timer started for {cat} at {time}",
                "Таймер запущено для {cat} о {time}",
                cat=created.category,
                time=created.started_at.strftime("%H:%M"),
            )
            if created.category != "spend"
            else localize(lang, "Spend timer started at {time}", "Таймер витрат запущено о {time}", time=created.started_at.strftime("%H:%M"))
        )
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    session = db.stop_timer(user_id)
    if not session:
        await update.effective_message.reply_text(localize(lang, "No active timer", "Немає активного таймера"))
        return

    elapsed = now - session.started_at
    minutes = int(elapsed.total_seconds() // 60)
    if minutes <= 0:
        minutes = 1

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
        await update.effective_message.reply_text(
            (
                f"⏱️ Spend session complete: {minutes}m\n\n"
                f"📝 Logged fun spend: {minutes} min\n\n"
                f"{status_message(view, username=update.effective_user.username, lang=lang)}"
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

    await update.effective_message.reply_text(
        (
            f"⏱️ Session complete: {minutes}m ({outcome.entry.category})\n\n"
            f"📝 Logged: {minutes} min ({outcome.entry.category})\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.deep_mult:.1f}x deep work, {outcome.streak_mult:.1f}x streak)\n"
            f"🔥 Streak: {outcome.streak.current_streak} days\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned} min\n\n"
            f"{status_message(view, username=update.effective_user.username, lang=lang)}"
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


async def cmd_freeze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    view = compute_status(db, user_id, now)

    if view.economy.remaining_fun_minutes < 200:
        await update.effective_message.reply_text(localize(lang, "Need at least 200 fun minutes to buy a streak freeze.", "Потрібно щонайменше 200 fun хвилин для покупки freeze."))
        return

    freeze_date = now.date() + timedelta(days=1)
    if db.has_freeze_on_date(user_id, freeze_date):
        await update.effective_message.reply_text(localize(lang, "Freeze already active for tomorrow.", "Freeze вже активний на завтра."))
        return

    db.add_entry(
        user_id=user_id,
        kind="spend",
        category="spend",
        minutes=200,
        note=f"Streak freeze for {freeze_date.isoformat()}",
        created_at=now,
        source="freeze",
    )
    db.create_freeze(user_id, freeze_date, now)

    await update.effective_message.reply_text(
        localize(
            lang,
            "🧊 Streak freeze purchased for {date} (-200 fun minutes).",
            "🧊 Freeze для серії куплено на {date} (-200 fun хвилин).",
            date=freeze_date.isoformat(),
        )
    )


async def cmd_llm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not db.is_feature_enabled("llm"):
        await update.effective_message.reply_text(localize(lang, "LLM features are currently disabled by admin.", "LLM-функції зараз вимкнені адміністратором."))
        return
    if not db.is_feature_enabled("agent"):
        await update.effective_message.reply_text(localize(lang, "Agent runtime is currently disabled by admin.", "Середовище агента зараз вимкнено адміністратором."))
        return

    if not settings.openrouter_api_key:
        await update.effective_message.reply_text(t("llm_disabled_key", lang))
        return

    if context.args and context.args[0].lower() == "models":
        cfg = load_model_config(settings.agent_models_path)
        rows = [f"Default tier: {cfg.default_tier}"]
        for tier_name, tier in cfg.tiers.items():
            ids = ", ".join(m.id for m in tier.models[:4])
            rows.append(f"- {tier_name}: {ids}")
        await update.effective_message.reply_text("\n".join(rows))
        return

    tier_override: str | None = None
    model_preference: str | None = None
    question_args = context.args
    if len(context.args) >= 3 and context.args[0].lower() == "tier":
        tier_override = context.args[1].strip()
        question_args = context.args[2:]
    elif len(context.args) >= 2 and context.args[0].lower() in ("gpt", "claude", "gemini"):
        model_preference = context.args[0].lower()
        tier_override = "top_tier"
        question_args = context.args[1:]
    question = " ".join(question_args).strip()
    if not question:
        await update.effective_message.reply_text(t("llm_usage", lang))
        return

    day_key = now.date().isoformat()
    usage = db.get_llm_usage(user_id, day_key)
    if usage.request_count >= LLM_DAILY_LIMIT:
        await update.effective_message.reply_text(localize(lang, "Daily /llm limit reached. Try again tomorrow.", "Денний ліміт /llm вичерпано. Спробуй завтра."))
        return
    if usage.last_request_at and (now - usage.last_request_at).total_seconds() < LLM_COOLDOWN_SECONDS:
        await update.effective_message.reply_text(localize(lang, "Please wait a bit before the next /llm question.", "Зачекай трохи перед наступним /llm запитом."))
        return

    db.increment_llm_usage(user_id, day_key, now)
    pending = await update.effective_message.reply_text(f"🤖 {t('llm_working', lang)}")
    result = run_llm_agent(
        db=db,
        settings=settings,
        user_id=user_id,
        now=now,
        question=question,
        tier_override=tier_override,
        model_preference=model_preference,
    )
    answer = str(result.get("answer", "")).strip()
    model_used = str(result.get("model", "unknown"))
    tier_used = str(result.get("tier", "unknown"))
    status = str(result.get("status", "unknown"))
    prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
    completion_tokens = int(result.get("completion_tokens", 0) or 0)
    if not answer:
        await pending.edit_text(localize(lang, "LLM could not answer right now. Try again later.", "LLM зараз не зміг відповісти. Спробуй пізніше."))
        return
    await pending.edit_text(
        f"{answer}\n\n`model: {model_used} | tier: {tier_used} | status: {status} | tok: {prompt_tokens}/{completion_tokens}`"
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    if not db.is_feature_enabled("search"):
        await update.effective_message.reply_text(localize(lang, "Search is currently disabled by admin.", "Пошук зараз вимкнений адміністратором."))
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.effective_message.reply_text(t("search_usage", lang))
        return
    pending = await update.effective_message.reply_text(f"🔎 {t('search_working', lang)}")
    res = run_search_tool(
        db=db,
        settings=settings,
        user_id=user_id,
        now=now,
        query=query,
        max_results=5,
    )
    if not res["ok"]:
        await pending.edit_text(localize(lang, "Search failed: {err}", "Помилка пошуку: {err}", err=res["content"]))
        return
    provider = str(res.get("metadata", {}).get("provider", "unknown"))
    cached = bool(res.get("metadata", {}).get("cached", False))
    await pending.edit_text(
        f"Search results ({provider}{', cached' if cached else ''}):\n\n{res['content']}"
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    if data.startswith("log:"):
        _, category, minutes_raw = data.split(":", maxsplit=2)
        minutes = int(minutes_raw)
        outcome = add_productive_entry(
            db=db,
            user_id=user_id,
            minutes=minutes,
            category=normalize_category(category),
            note=None,
            created_at=now,
            source="button",
            timer_mode=False,
        )
        view = compute_status(db, user_id, now)
        await query.message.reply_text(
            f"{localize(lang, 'Logged {minutes}m {category}.', 'Додано {minutes}хв {category}.', minutes=minutes, category=outcome.entry.category)}\n"
            f"⚡ XP +{outcome.xp_earned}\n💰 Fun +{outcome.entry.fun_earned}\n\n{status_message(view, lang=lang)}",
            reply_markup=build_keyboard(),
        )
        return

    if data.startswith("spend:"):
        _, minutes_raw = data.split(":", maxsplit=1)
        minutes = int(minutes_raw)
        db.add_entry(
            user_id=user_id,
            kind="spend",
            category="spend",
            minutes=minutes,
            created_at=now,
            source="button",
        )
        view = compute_status(db, user_id, now)
        await query.message.reply_text(
            f"{localize(lang, 'Logged {minutes}m fun spend.', 'Додано витрати відпочинку: {minutes}хв.', minutes=minutes)}\n\n{status_message(view, lang=lang)}",
            reply_markup=build_keyboard(),
        )
        return

    if data == "status":
        view = compute_status(db, user_id, now)
        await query.message.reply_text(status_message(view, lang=lang), reply_markup=build_keyboard())
        return

    if data == "week":
        view = compute_status(db, user_id, now)
        await query.message.reply_text(week_message(view, lang=lang), reply_markup=build_keyboard())
        return

    if data == "undo":
        removed = db.undo_last_entry(user_id, now)
        if not removed:
            await query.message.reply_text(localize(lang, "Nothing to undo", "Нічого скасовувати"))
            return
        await query.message.reply_text(entry_removed_message(removed, lang=lang), reply_markup=build_keyboard())


async def handle_free_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return

    if not db.is_feature_enabled("llm"):
        await update.effective_message.reply_text(
            localize(lang, "Nothing happened. Free-form parsing is disabled by admin.", "Нічого не сталося. Вільний LLM-парсинг вимкнено адміністратором.")
        )
        return

    if not settings.llm_enabled or not settings.llm_api_key:
        await update.effective_message.reply_text(
            localize(lang, "Nothing happened. Free-form LLM parsing is disabled. Use /help for commands.", "Нічого не сталося. Вільний LLM-парсинг вимкнений. Використай /help для команд.")
        )
        return

    if update.effective_chat:
        await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        parsed = parse_free_form_with_llm(
            text,
            LlmRoute(
                provider=settings.llm_provider,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
            ),
        )
    except Exception:
        logger.exception("LLM parse failed")
        await update.effective_message.reply_text(localize(lang, "Something went wrong while parsing. Nothing was logged.", "Сталася помилка під час парсингу. Нічого не записано."))
        return

    if not parsed:
        await update.effective_message.reply_text(
            localize(lang, "Nothing happened. I could not map that text to a log action.", "Нічого не сталося. Я не зміг перетворити цей текст у дію логування.")
        )
        return

    if parsed.action == "log":
        _ = add_productive_entry(
            db=db,
            user_id=user_id,
            minutes=parsed.minutes,
            category=parsed.category or "build",
            note=parsed.note,
            created_at=now,
            source="llm",
            timer_mode=False,
        )
    else:
        db.add_entry(
            user_id=user_id,
            kind="spend",
            category="spend",
            minutes=parsed.minutes,
            note=parsed.note,
            created_at=now,
            source="llm",
        )

    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(
        f"{localize(lang, 'Parsed and logged via LLM.', 'Розібрано й додано через LLM.')}\n\n{status_message(view, lang=lang)}"
    )


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    lang = get_user_language(context, user_id)
    await update.effective_message.reply_text(
        t("unknown_command", lang)
    )


def register_core_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("spend", cmd_spend))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("reminders", cmd_reminders))
    app.add_handler(CommandHandler("quiet_hours", cmd_quiet_hours))
    app.add_handler(CommandHandler("freeze", cmd_freeze))
    app.add_handler(CommandHandler("llm", cmd_llm))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(log:|spend:|status$|week$|undo$)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))


def register_unknown_handler(app: Application) -> None:
    # Register this after all command modules, in the default group, so it only
    # handles truly unknown commands.
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
