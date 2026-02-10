from __future__ import annotations

import logging
from datetime import timedelta

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from tg_time_logger.commands_shared import (
    build_keyboard,
    get_db,
    get_settings,
    send_level_ups,
    touch_user,
)
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES
from tg_time_logger.llm_parser import parse_free_form_with_llm
from tg_time_logger.llm_router import LlmRoute, call_text
from tg_time_logger.messages import entry_removed_message, status_message, week_message
from tg_time_logger.service import add_productive_entry, compute_status, normalize_category
from tg_time_logger.time_utils import week_range_for, week_start_date

logger = logging.getLogger(__name__)
LLM_DAILY_LIMIT = 10
LLM_COOLDOWN_SECONDS = 30


HELP_TOPICS: dict[str, str] = {
    "overview": (
        "Available commands:\n"
        "/log, /spend, /status, /week, /undo\n"
        "/plan, /start, /stop\n"
        "/quests, /shop, /redeem, /save\n"
        "/rules, /llm, /reminders, /quiet_hours, /freeze\n"
        "/help [command]\n\n"
        "Examples:\n"
        "/help log\n"
        "/help save\n"
        "/help shop"
    ),
    "log": (
        "/log <duration> [study|build|training|job] [note]\n"
        "Logs productive time.\n\n"
        "Duration examples:\n"
        "- /log 90m\n"
        "- /log 1.5h build API refactor\n"
        "- /log 1h20m study chapter 3\n"
        "- /log 45 training"
    ),
    "spend": (
        "/spend <duration> [note]\n"
        "Logs fun consumption time.\n\n"
        "Examples:\n"
        "- /spend 40m YouTube\n"
        "- /spend 2h movie night"
    ),
    "status": (
        "/status\n"
        "Shows level, XP, streak, week totals, plan progress, economy, and active quest count."
    ),
    "week": (
        "/week\n"
        "Shows this week summary (productive, spent, plan progress, XP, deep sessions, fun remaining)."
    ),
    "undo": (
        "/undo\n"
        "Soft-deletes your last entry (productive or spend)."
    ),
    "plan": (
        "/plan set <duration>\n"
        "/plan show\n"
        "Sets or shows this week target.\n\n"
        "Examples:\n"
        "- /plan set 20h\n"
        "- /plan show"
    ),
    "start": (
        "/start [study|build|training|job] [note]\n"
        "Starts a timer session.\n\n"
        "Example:\n"
        "- /start build backend cleanup"
    ),
    "stop": (
        "/stop\n"
        "Stops active timer and logs elapsed minutes with XP/fun."
    ),
    "quests": (
        "/quests\n"
        "/quests history\n"
        "Shows active quests or this-week quest history."
    ),
    "shop": (
        "/shop\n"
        "/shop add <emoji> \"name\" <cost_duration_or_minutes> [nok_value]\n"
        "/shop remove <item_id>\n"
        "/shop budget <minutes|off>\n\n"
        "Examples:\n"
        "- /shop add ⌚ \"Apple Watch\" 15000m\n"
        "- /shop add 🎧 \"AirPods\" 4000 2490\n"
        "- /shop remove 12"
    ),
    "redeem": (
        "/redeem <item_id|item_name>\n"
        "/redeem history\n\n"
        "Redeem uses savings fund first, then remaining fun minutes."
    ),
    "save": (
        "/save\n"
        "/save goal <duration> [name]\n"
        "/save fund <duration>\n\n"
        "Simple flow:\n"
        "1) Set a goal: /save goal 2000m Device fund\n"
        "2) Add into fund: /save fund 200m\n"
        "Fund is locked for shop redemptions."
    ),
    "rules": (
        "/rules\n"
        "/rules add <text>\n"
        "/rules remove <id>\n"
        "/rules clear\n\n"
        "Personal rulebook/notes for yourself. It does not change system logic."
    ),
    "llm": (
        "/llm <question>\n"
        "Ask analytics questions based on your stats.\n"
        "Requires LLM_ENABLED=1 and valid API key.\n\n"
        "Example:\n"
        "- /llm what should I focus on to hit level 10 faster?"
    ),
    "reminders": (
        "/reminders on\n"
        "/reminders off\n"
        "Turns reminder notifications on or off."
    ),
    "quiet_hours": (
        "/quiet_hours HH:MM-HH:MM\n"
        "Suppress reminders inside this window.\n"
        "Example: /quiet_hours 22:00-08:00"
    ),
    "freeze": (
        "/freeze\n"
        "Buys tomorrow streak freeze for 200 fun minutes."
    ),
    "help": (
        "/help\n"
        "/help <command>\n"
        "Shows global help or detailed docs for one command."
    ),
}


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /log <duration> [study|build|training|job] [note]")
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


async def cmd_spend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /spend <duration> [note]")
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
        f"Logged spend {minutes}m.\n\n{status_message(view, username=update.effective_user.username)}",
        reply_markup=build_keyboard(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    view = compute_status(get_db(context), user_id, now)
    await update.effective_message.reply_text(
        status_message(view, username=update.effective_user.username),
        reply_markup=build_keyboard(),
    )


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(week_message(view), reply_markup=build_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_user(update, context)
    if not context.args:
        await update.effective_message.reply_text(HELP_TOPICS["overview"])
        return

    topic = context.args[0].strip().lower().lstrip("/")
    text = HELP_TOPICS.get(topic)
    if not text:
        await update.effective_message.reply_text(
            f"No detailed help for '{topic}'. Try /help to see all commands."
        )
        return
    await update.effective_message.reply_text(text)


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)

    if not context.args:
        rules = db.list_user_rules(user_id)
        if not rules:
            await update.effective_message.reply_text(
                "No personal rules yet. Add one with /rules add <text>."
            )
            return
        lines = ["📘 Your rules:"]
        for rule in rules:
            lines.append(f"{rule.id}. {rule.rule_text}")
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "add":
        text = " ".join(context.args[1:]).strip()
        if not text:
            await update.effective_message.reply_text("Usage: /rules add <text>")
            return
        rule = db.add_user_rule(user_id, text, now)
        await update.effective_message.reply_text(f"Rule saved ({rule.id}).")
        return

    if action == "remove":
        if len(context.args) < 2 or not context.args[1].isdigit():
            await update.effective_message.reply_text("Usage: /rules remove <id>")
            return
        ok = db.remove_user_rule(user_id, int(context.args[1]))
        await update.effective_message.reply_text("Rule removed." if ok else "Rule not found.")
        return

    if action == "clear":
        count = db.clear_user_rules(user_id)
        await update.effective_message.reply_text(f"Removed {count} rule(s).")
        return

    await update.effective_message.reply_text("Usage: /rules, /rules add, /rules remove, /rules clear")


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    removed = get_db(context).undo_last_entry(user_id=user_id, deleted_at=now)
    if not removed:
        await update.effective_message.reply_text("Nothing to undo")
        return
    await update.effective_message.reply_text(entry_removed_message(removed), reply_markup=build_keyboard())


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)

    if not context.args:
        await update.effective_message.reply_text("Usage: /plan set <duration> OR /plan show")
        return

    action = context.args[0].lower()
    if action == "show":
        plan = db.get_plan_target(user_id, week_start_date(now))
        if not plan:
            await update.effective_message.reply_text("No plan set for this week")
            return
        done = db.sum_minutes(user_id, "productive", start=week_range_for(now).start, end=now)
        await update.effective_message.reply_text(
            f"Plan this week: {plan.total_target_minutes}m total productive | done {done}m"
        )
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
        total_target_minutes=target_minutes,
        build_target_minutes=target_minutes,
    )
    await update.effective_message.reply_text(f"Plan saved for week: {target_minutes}m total productive")


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    if not context.args:
        await update.effective_message.reply_text("Usage: /reminders on|off")
        return

    action = context.args[0].lower()
    if action not in {"on", "off"}:
        await update.effective_message.reply_text("Usage: /reminders on|off")
        return

    enabled = action == "on"
    get_db(context).update_reminders_enabled(user_id, enabled)
    await update.effective_message.reply_text(f"Reminders {'enabled' if enabled else 'disabled'}")


async def cmd_quiet_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, _ = touch_user(update, context)
    if not context.args:
        await update.effective_message.reply_text("Usage: /quiet_hours HH:MM-HH:MM")
        return

    raw = context.args[0]
    if "-" not in raw or ":" not in raw:
        await update.effective_message.reply_text("Invalid format. Example: /quiet_hours 22:00-08:00")
        return

    get_db(context).update_quiet_hours(user_id, raw)
    await update.effective_message.reply_text(f"Quiet hours set to {raw}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)

    category = "build"
    tail = context.args
    if tail and tail[0].lower() in PRODUCTIVE_CATEGORIES:
        category = tail[0].lower()
        tail = tail[1:]
    note = " ".join(tail).strip() or None

    existing, created = get_db(context).get_or_start_timer(user_id, category, now, note)
    if existing:
        await update.effective_message.reply_text(
            f"A timer is already running for {existing.category} since {existing.started_at.strftime('%H:%M')}"
        )
        return

    await update.effective_message.reply_text(
        f"Timer started for {created.category} at {created.started_at.strftime('%H:%M')}"
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    session = db.stop_timer(user_id)
    if not session:
        await update.effective_message.reply_text("No active timer")
        return

    elapsed = now - session.started_at
    minutes = int(elapsed.total_seconds() // 60)
    if minutes <= 0:
        minutes = 1

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


async def cmd_freeze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    view = compute_status(db, user_id, now)

    if view.economy.remaining_fun_minutes < 200:
        await update.effective_message.reply_text("Need at least 200 fun minutes to buy a streak freeze.")
        return

    freeze_date = now.date() + timedelta(days=1)
    if db.has_freeze_on_date(user_id, freeze_date):
        await update.effective_message.reply_text("Freeze already active for tomorrow.")
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
        f"🧊 Streak freeze purchased for {freeze_date.isoformat()} (-200 fun minutes)."
    )


async def cmd_llm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    db = get_db(context)

    if not settings.llm_enabled or not settings.llm_api_key:
        await update.effective_message.reply_text("LLM is disabled. Set LLM_ENABLED=1 and provider API key.")
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.effective_message.reply_text("Usage: /llm <question about your stats>")
        return

    day_key = now.date().isoformat()
    usage = db.get_llm_usage(user_id, day_key)
    if usage.request_count >= LLM_DAILY_LIMIT:
        await update.effective_message.reply_text("Daily /llm limit reached. Try again tomorrow.")
        return
    if usage.last_request_at and (now - usage.last_request_at).total_seconds() < LLM_COOLDOWN_SECONDS:
        await update.effective_message.reply_text("Please wait a bit before the next /llm question.")
        return

    view = compute_status(db, user_id, now)
    db.increment_llm_usage(user_id, day_key, now)

    prompt = (
        "You are an analytics assistant for a gamified productivity tracker. "
        "Answer the user's question using only the provided stats and be concise.\n\n"
        f"User question: {question}\n\n"
        "Stats:\n"
        f"- Level: {view.level} ({view.title})\n"
        f"- XP total: {view.xp_total}, XP this week: {view.xp_week}\n"
        f"- XP to next level: {view.xp_remaining_to_next}\n"
        f"- Streak: {view.streak_current}, longest: {view.streak_longest}\n"
        f"- Week productive: {view.week.productive_minutes} min\n"
        f"- Week spent: {view.week.spent_minutes} min\n"
        f"- Week category minutes: {view.week_categories}\n"
        f"- Economy remaining fun: {view.economy.remaining_fun_minutes} min\n"
        f"- Active quests: {view.active_quests}\n"
        "\nIf question asks missing data, say what is missing."
    )

    route = LlmRoute(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
    )
    pending = await update.effective_message.reply_text("🤖 Working on your question...")
    answer = call_text(route, prompt, max_tokens=240)
    if not answer:
        await pending.edit_text("LLM could not answer right now. Try again later.")
        return

    await pending.edit_text(answer)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
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
            f"Logged {minutes}m {outcome.entry.category}.\n⚡ XP +{outcome.xp_earned}\n💰 Fun +{outcome.entry.fun_earned}\n\n{status_message(view)}",
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
            f"Logged {minutes}m fun spend.\n\n{status_message(view)}",
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
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return

    if not settings.llm_enabled or not settings.llm_api_key:
        await update.effective_message.reply_text(
            "Nothing happened. Free-form LLM parsing is disabled. Use /help for commands."
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
        await update.effective_message.reply_text("Something went wrong while parsing. Nothing was logged.")
        return

    if not parsed:
        await update.effective_message.reply_text(
            "Nothing happened. I could not map that text to a log action."
        )
        return

    db = get_db(context)
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
    await update.effective_message.reply_text(f"Parsed and logged via LLM.\n\n{status_message(view)}")


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_user(update, context)
    await update.effective_message.reply_text(
        "Nothing happened. Unknown command. Use /help to see all commands."
    )


def register_core_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("help", cmd_help))
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
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
