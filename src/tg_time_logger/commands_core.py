from __future__ import annotations

import logging
import secrets
import random
from datetime import timedelta

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.orchestration.runner import run_llm_agent, run_llm_text
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from tg_time_logger.i18n import localize, t
from tg_time_logger.llm_parser import parse_free_form_with_llm
from tg_time_logger.llm_router import LlmRoute
from tg_time_logger.llm_tiers import resolve_available_tier
from tg_time_logger.messages import entry_removed_message, status_message
from tg_time_logger.quests import (
    QUEST_ALLOWED_DURATIONS,
    _validate_llm_quest,
    _weekly_stats,
    extract_quest_payload,
    quest_min_target_minutes,
    quest_reward_bounds,
    sync_quests_for_user,
)
from tg_time_logger.service import add_productive_entry, compute_status, normalize_category
from tg_time_logger.time_utils import week_range_for, week_start_date

logger = logging.getLogger(__name__)
_FF_PENDING_KEY = "freeform_pending"
_FF_TTL_MINUTES = 5
_QUEST_PENDING_KEY = "quest_pending"
_QUEST_TTL_MINUTES = 10


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if len(context.args) < 1:
        await update.effective_message.reply_text(localize(lang, "Usage: /log <duration> [study|build|training|job|other] [note]", "Використання: /log <duration> [study|build|training|job|other] [note]"))
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
        db.add_entry(
            user_id=user_id,
            kind="other",
            category="other",
            minutes=minutes,
            note=description,
            created_at=now,
        )
        label = description or "other"
        await update.effective_message.reply_text(
            localize(lang,
                     f"Noted: {minutes}m {label}",
                     f"Записано: {minutes}m {label}")
        )
        return

    category = "build"
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

    quest_sync = sync_quests_for_user(db, user_id, now)
    view = compute_status(db, user_id, now)
    quest_lines: list[str] = []
    for item in quest_sync.completed[:3]:
        quest_lines.append(f"✅ Quest: {item.quest.title} (+{item.quest.reward_fun_minutes}m)")
    if quest_sync.penalty_minutes_applied > 0:
        quest_lines.append(f"⚠️ Quest penalties applied: -{quest_sync.penalty_minutes_applied}m")
    quest_block = "\n\n" + "\n".join(quest_lines) if quest_lines else ""
    await update.effective_message.reply_text(
        (
            f"Logged {minutes}m {outcome.entry.category}.\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.streak_mult:.1f}x streak)\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned}m\n\n"
            f"{status_message(view, username=update.effective_user.username, lang=lang)}"
            f"{quest_block}"
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

    quest_sync = sync_quests_for_user(db, user_id, now)
    view = compute_status(db, user_id, now)
    quest_lines: list[str] = []
    for item in quest_sync.completed[:3]:
        quest_lines.append(f"✅ Quest: {item.quest.title} (+{item.quest.reward_fun_minutes}m)")
    if quest_sync.penalty_minutes_applied > 0:
        quest_lines.append(f"⚠️ Quest penalties applied: -{quest_sync.penalty_minutes_applied}m")
    quest_block = "\n" + "\n".join(quest_lines) if quest_lines else ""
    await update.effective_message.reply_text(
        f"{localize(lang, 'Logged spend {minutes}m.', 'Додано витрати {minutes}хв.', minutes=minutes)}\n\n{status_message(view, username=update.effective_user.username, lang=lang)}{quest_block}",
        reply_markup=build_keyboard(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)
    db = get_db(context)
    sync_quests_for_user(db, user_id, now)
    view = compute_status(db, user_id, now)
    await update.effective_message.reply_text(
        status_message(view, username=update.effective_user.username, lang=lang),
        reply_markup=build_keyboard(),
    )



async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not context.args:
        rules = db.list_user_rules(user_id)
        if not rules:
            await update.effective_message.reply_text(
                localize(lang, "No personal notes yet. Add one with /notes add <text>.", "Поки немає нотаток. Додай: /notes add <text>")
            )
            return
        lines = [localize(lang, "📘 Your notes:", "📘 Твої нотатки:")]
        for rule in rules:
            lines.append(f"{rule.id}. {rule.rule_text}")
        await update.effective_message.reply_text("\n".join(lines))
        return

    action = context.args[0].lower()
    if action == "add":
        text = " ".join(context.args[1:]).strip()
        if not text:
            await update.effective_message.reply_text(localize(lang, "Usage: /notes add <text>", "Використання: /notes add <text>"))
            return
        rule = db.add_user_rule(user_id, text, now)
        await update.effective_message.reply_text(localize(lang, "Note saved ({id}).", "Нотатку збережено ({id}).", id=rule.id))
        return

    if action == "remove":
        if len(context.args) < 2 or not context.args[1].isdigit():
            await update.effective_message.reply_text(localize(lang, "Usage: /notes remove <id>", "Використання: /notes remove <id>"))
            return
        ok = db.remove_user_rule(user_id, int(context.args[1]))
        await update.effective_message.reply_text(localize(lang, "Note removed.", "Нотатку видалено.") if ok else localize(lang, "Note not found.", "Нотатку не знайдено."))
        return

    if action == "clear":
        count = db.clear_user_rules(user_id)
        await update.effective_message.reply_text(localize(lang, "Removed {count} note(s).", "Видалено нотаток: {count}.", count=count))
        return

    await update.effective_message.reply_text(localize(lang, "Usage: /notes, /notes add, /notes remove, /notes clear", "Використання: /notes, /notes add, /notes remove, /notes clear"))


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


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram /start — onboarding welcome message."""
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)
    await update.effective_message.reply_text(
        localize(
            lang,
            (
                "Welcome! I'm your productivity tracker.\n\n"
                "Quick start:\n"
                "  /log 30m study — log 30 min of study\n"
                "  /timer study — start a live timer\n"
                "  /spend 1h — log 1h of fun time\n"
                "  /status — see your progress\n"
                "  /help — all commands\n\n"
                "Or just type naturally: \"studied 2h math\""
            ),
            (
                "Привіт! Я твій трекер продуктивності.\n\n"
                "Швидкий старт:\n"
                "  /log 30m study — записати 30 хв навчання\n"
                "  /timer study — запустити таймер\n"
                "  /spend 1h — записати 1 год відпочинку\n"
                "  /status — подивитися прогрес\n"
                "  /help — всі команди\n\n"
                "Або просто напиши: \"вчився 2 години математику\""
            ),
        ),
        reply_markup=build_keyboard(),
    )


async def cmd_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    lang = get_user_language(context, user_id)

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
            localize(
                lang,
                "A timer is already running for {cat} since {time}",
                "Таймер вже запущено для {cat} з {time}",
                cat=existing.category,
                time=existing.started_at.strftime("%H:%M"),
            ),
            reply_markup=timer_kb,
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
        ),
        reply_markup=timer_kb,
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
        quest_sync = sync_quests_for_user(db, user_id, now)
        view = compute_status(db, user_id, now)
        quest_lines: list[str] = []
        for item in quest_sync.completed[:3]:
            quest_lines.append(f"✅ Quest: {item.quest.title} (+{item.quest.reward_fun_minutes}m)")
        if quest_sync.penalty_minutes_applied > 0:
            quest_lines.append(f"⚠️ Quest penalties applied: -{quest_sync.penalty_minutes_applied}m")
        quest_block = "\n" + "\n".join(quest_lines) if quest_lines else ""
        await update.effective_message.reply_text(
            (
                f"⏱️ Spend session complete: {minutes}m\n\n"
                f"📝 Logged fun spend: {minutes} min\n\n"
                f"{status_message(view, username=update.effective_user.username, lang=lang)}"
                f"{quest_block}"
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
    quest_sync = sync_quests_for_user(db, user_id, now)
    view = compute_status(db, user_id, now)
    quest_lines: list[str] = []
    for item in quest_sync.completed[:3]:
        quest_lines.append(f"✅ Quest: {item.quest.title} (+{item.quest.reward_fun_minutes}m)")
    if quest_sync.penalty_minutes_applied > 0:
        quest_lines.append(f"⚠️ Quest penalties applied: -{quest_sync.penalty_minutes_applied}m")
    quest_block = "\n\n" + "\n".join(quest_lines) if quest_lines else ""

    await update.effective_message.reply_text(
        (
            f"⏱️ Session complete: {minutes}m ({outcome.entry.category})\n\n"
            f"📝 Logged: {minutes} min ({outcome.entry.category})\n"
            f"⚡ XP earned: {outcome.xp_earned} ({outcome.deep_mult:.1f}x deep work, {outcome.streak_mult:.1f}x streak)\n"
            f"🔥 Streak: {outcome.streak.current_streak} days\n"
            f"💰 Fun earned: +{outcome.entry.fun_earned} min\n\n"
            f"{status_message(view, username=update.effective_user.username, lang=lang)}"
            f"{quest_block}"
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
        sync_quests_for_user(db, user_id, now)
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
        sync_quests_for_user(db, user_id, now)
        view = compute_status(db, user_id, now)
        await query.message.reply_text(
            f"{localize(lang, 'Logged {minutes}m fun spend.', 'Додано витрати відпочинку: {minutes}хв.', minutes=minutes)}\n\n{status_message(view, lang=lang)}",
            reply_markup=build_keyboard(),
        )
        return

    if data == "status":
        sync_quests_for_user(db, user_id, now)
        view = compute_status(db, user_id, now)
        await query.message.reply_text(status_message(view, lang=lang), reply_markup=build_keyboard())
        return

    if data == "undo":
        removed = db.undo_last_entry(user_id, now)
        if not removed:
            await query.message.reply_text(localize(lang, "Nothing to undo", "Нічого скасовувати"))
            return
        await query.message.reply_text(entry_removed_message(removed, lang=lang), reply_markup=build_keyboard())
        return

    if data == "timer:stop":
        session = db.stop_timer(user_id)
        if not session:
            await query.message.reply_text(localize(lang, "No active timer", "Немає активного таймера"))
            return
        elapsed = now - session.started_at
        minutes = max(int(elapsed.total_seconds() // 60), 1)
        if session.category == "spend":
            db.add_entry(user_id=user_id, kind="spend", category="spend", minutes=minutes, note=session.note, created_at=now, source="timer")
            sync_quests_for_user(db, user_id, now)
            view = compute_status(db, user_id, now)
            await query.message.reply_text(
                f"⏱️ Spend session complete: {minutes}m\n\n📝 Logged fun spend: {minutes} min\n\n{status_message(view, username=update.effective_user.username, lang=lang)}",
                reply_markup=build_keyboard(),
            )
            return
        outcome = add_productive_entry(db=db, user_id=user_id, minutes=minutes, category=session.category, note=session.note, created_at=now, source="timer", timer_mode=True)
        sync_quests_for_user(db, user_id, now)
        view = compute_status(db, user_id, now)
        await query.message.reply_text(
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
        await send_level_ups(update, context, top_category=outcome.top_week_category, level_ups=outcome.level_ups, total_productive_minutes=view.all_time.productive_minutes, xp_remaining=view.xp_remaining_to_next)


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
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["timer", "t"], cmd_timer))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler(["notes", "rules"], cmd_notes))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(log:|spend:|status$|undo$|timer:stop$)"))


def register_unknown_handler(app: Application) -> None:
    # Register this after all command modules, in the default group, so it only
    # handles truly unknown commands.
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
