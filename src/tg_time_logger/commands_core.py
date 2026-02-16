from __future__ import annotations

import logging
import secrets
import random
from datetime import timedelta

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.orchestration.runner import run_llm_agent
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
LLM_DAILY_LIMIT = 80
LLM_COOLDOWN_SECONDS = 30
_FF_PENDING_KEY = "freeform_pending"
_FF_TTL_MINUTES = 5
_QUEST_PENDING_KEY = "quest_pending"
_QUEST_TTL_MINUTES = 10


def _quest_pending(context: ContextTypes.DEFAULT_TYPE) -> dict[str, dict[str, object]]:
    store = context.application.bot_data.get(_QUEST_PENDING_KEY)
    if isinstance(store, dict):
        return store
    created: dict[str, dict[str, object]] = {}
    context.application.bot_data[_QUEST_PENDING_KEY] = created
    return created


def _quest_cleanup(context: ContextTypes.DEFAULT_TYPE, now_iso: str) -> None:
    store = _quest_pending(context)
    stale = [t for t, p in store.items() if str(p.get("expires_at", "")) <= now_iso]
    for t in stale:
        store.pop(t, None)


def _load_quest_skill_text(settings) -> str:
    path = settings.agent_directive_path.parent / "skills" / "quest_builder.md"
    if not path.exists():
        return ""
    text = path.read_text().strip()
    return text[:6000] if text else ""


def _build_quest_generation_prompt(
    *,
    difficulty: str,
    duration_days: int,
    min_target: int,
    reward_lo: int,
    reward_hi: int,
    stats: dict[str, object],
    recent_quest_lines: list[str],
    memory_lines: list[str],
    skill_text: str,
) -> str:
    recent_block = "\n".join(f"- {x}" for x in recent_quest_lines) if recent_quest_lines else "- none"
    memory_block = "\n".join(f"- {x}" for x in memory_lines) if memory_lines else "- none"
    skill_block = f"\nSkill directive:\n{skill_text}\n" if skill_text else ""
    return (
        "Create exactly one quest proposal as JSON object only (no markdown, no commentary).\n"
        "This user is build-first: target around 60-70% build focus over time. "
        "Study and training should be supportive additions.\n"
        f"Requested difficulty: {difficulty}\n"
        f"Requested duration_days: {duration_days}\n"
        f"Minimum target_minutes for this difficulty/duration: {min_target}\n"
        f"Reward bounds (inclusive): {reward_lo}-{reward_hi}\n"
        "Penalty must equal reward.\n\n"
        "User snapshot:\n"
        f"- weekly_hours: {stats.get('weekly_hours')}\n"
        f"- avg_daily: {stats.get('avg_daily')}\n"
        f"- build_share: {stats.get('build_share')}\n"
        f"- top_category: {stats.get('top_category')}\n"
        f"- streak: {stats.get('streak')}\n"
        f"- level: {stats.get('level')}\n"
        f"- fun_spent: {stats.get('fun_spent')}\n\n"
        "Recent quests/proposals (avoid duplicates):\n"
        f"{recent_block}\n\n"
        "Quest memory hints:\n"
        f"{memory_block}\n"
        f"{skill_block}\n"
        "Return JSON with keys:\n"
        "{\n"
        '  "title": "short unique title",\n'
        '  "description": "one sentence",\n'
        '  "quest_type": "challenge",\n'
        f'  "difficulty": "{difficulty}",\n'
        f'  "duration_days": {duration_days},\n'
        '  "condition": {"type":"total_minutes","target_minutes":<int>,"category":"build|study|training|all"},\n'
        f'  "reward_fun_minutes": <{reward_lo}-{reward_hi}>,\n'
        '  "penalty_fun_minutes": "same as reward",\n'
        '  "extra_benefit": "optional text, especially for hard quests"\n'
        "}\n"
    )



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
    quest_block = f"\n\n" + "\n".join(quest_lines) if quest_lines else ""
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
    quest_block = f"\n" + "\n".join(quest_lines) if quest_lines else ""
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
        quest_block = f"\n" + "\n".join(quest_lines) if quest_lines else ""
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
    quest_block = f"\n\n" + "\n".join(quest_lines) if quest_lines else ""

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

    if context.args and context.args[0].lower() == "models":
        cfg = load_model_config(settings.agent_models_path)
        rows = [f"Default tier: {cfg.default_tier}"]
        for tier_name, tier in cfg.tiers.items():
            ids = ", ".join(m.id for m in tier.models[:4])
            rows.append(f"- {tier_name}: {ids}")
        await update.effective_message.reply_text("\n".join(rows))
        return

    # --- Quests 2.0 manual generation ---
    if context.args and context.args[0].lower() in {"quest", "quests"}:
        mode = context.args[0].lower()
        valid_difficulties = ("easy", "medium", "hard")
        difficulty = random.choice(valid_difficulties)
        duration_days = 7

        if mode == "quest":
            if len(context.args) < 2:
                await update.effective_message.reply_text(
                    localize(
                        lang,
                        "Usage: /llm quest easy|medium|hard [3|5|7|14|21]",
                        "Використання: /llm quest easy|medium|hard [3|5|7|14|21]",
                    )
                )
                return
            difficulty = context.args[1].strip().lower()
            if difficulty not in valid_difficulties:
                await update.effective_message.reply_text(
                    localize(
                        lang,
                        "Difficulty must be easy, medium, or hard.",
                        "Складність має бути easy, medium або hard.",
                    )
                )
                return
            if len(context.args) >= 3:
                if not context.args[2].isdigit():
                    await update.effective_message.reply_text(
                        localize(
                            lang,
                            "Duration must be one of: 3, 5, 7, 14, 21.",
                            "Тривалість має бути: 3, 5, 7, 14, 21.",
                        )
                    )
                    return
                duration_days = int(context.args[2])
        else:
            if len(context.args) >= 2:
                if not context.args[1].isdigit():
                    await update.effective_message.reply_text(
                        localize(
                            lang,
                            "Usage: /llm quests [3|5|7|14|21]",
                            "Використання: /llm quests [3|5|7|14|21]",
                        )
                    )
                    return
                duration_days = int(context.args[1])

        if duration_days not in QUEST_ALLOWED_DURATIONS:
            await update.effective_message.reply_text(
                localize(
                    lang,
                    "Duration must be one of: 3, 5, 7, 14, 21.",
                    "Тривалість має бути: 3, 5, 7, 14, 21.",
                )
            )
            return

        has_any_key = (
            settings.openrouter_api_key
            or settings.openai_api_key
            or settings.google_api_key
            or settings.anthropic_api_key
        )
        if not has_any_key:
            await update.effective_message.reply_text(t("llm_disabled_key", lang))
            return

        day_key = now.date().isoformat()
        usage = db.get_llm_usage(user_id, day_key)
        if usage.request_count >= LLM_DAILY_LIMIT:
            await update.effective_message.reply_text(localize(lang, "Daily /llm limit reached. Try again tomorrow.", "Денний ліміт /llm вичерпано. Спробуй завтра."))
            return
        if usage.last_request_at and (now - usage.last_request_at).total_seconds() < LLM_COOLDOWN_SECONDS:
            await update.effective_message.reply_text(localize(lang, "Please wait a bit before the next /llm request.", "Зачекай трохи перед наступним /llm запитом."))
            return

        db.increment_llm_usage(user_id, day_key, now)
        pending = await update.effective_message.reply_text(localize(lang, "Generating quest...", "Генерую квест..."))

        stats = _weekly_stats(db, user_id, now - timedelta(days=28), now)
        min_target = quest_min_target_minutes(difficulty, duration_days)
        reward_lo, reward_hi = quest_reward_bounds(difficulty, duration_days)
        recent_quests = db.list_recent_quests(user_id, limit=20)
        recent_proposals = db.list_recent_quest_payloads(user_id, limit=20)
        memories = db.list_coach_memories(user_id, category="context", limit=20)

        recent_lines = [
            f"[{q.status}] {q.title} ({q.difficulty}, {q.duration_days}d, +{q.reward_fun_minutes}/-{q.penalty_fun_minutes})"
            for q in recent_quests[:10]
        ]
        recent_lines.extend(
            f"[proposal:{r['status']}] {str(r['payload'].get('title', 'untitled'))}"
            for r in recent_proposals[:10]
            if isinstance(r.get("payload"), dict)
        )
        recent_titles = {q.title.strip().lower() for q in recent_quests}
        for r in recent_proposals:
            payload = r.get("payload")
            if isinstance(payload, dict):
                title = str(payload.get("title", "")).strip().lower()
                if title:
                    recent_titles.add(title)

        memory_lines = []
        for mem in memories:
            tags = (mem.tags or "").lower()
            if "quest" in tags or "quest" in mem.content.lower():
                memory_lines.append(f"{mem.content[:180]}")

        skill_text = _load_quest_skill_text(settings)
        prompt = _build_quest_generation_prompt(
            difficulty=difficulty,
            duration_days=duration_days,
            min_target=min_target,
            reward_lo=reward_lo,
            reward_hi=reward_hi,
            stats=stats,
            recent_quest_lines=recent_lines[:20],
            memory_lines=memory_lines[:12],
            skill_text=skill_text,
        )

        user_settings = db.get_settings(user_id)
        result = run_llm_agent(
            db=db,
            settings=settings,
            user_id=user_id,
            now=now,
            question=prompt,
            tier_override=user_settings.preferred_tier,
        )
        answer = str(result.get("answer", "")).strip()
        model_used = str(result.get("model", "unknown"))
        payload = extract_quest_payload(answer)
        if not payload:
            await pending.edit_text(
                localize(
                    lang,
                    "Could not parse quest JSON. Try again.",
                    "Не вдалося розібрати JSON квесту. Спробуй ще раз.",
                )
            )
            return

        validated = _validate_llm_quest(
            payload,
            stats,
            random.Random(f"{user_id}:{now.isoformat()}:{difficulty}:{duration_days}"),
            difficulty_hint=difficulty,
            duration_days_hint=duration_days,
        )
        if not validated:
            await pending.edit_text(
                localize(
                    lang,
                    "Quest failed validation. Try again.",
                    "Квест не пройшов валідацію. Спробуй ще раз.",
                )
            )
            return

        title_norm = str(validated["title"]).strip().lower()
        if title_norm in recent_titles:
            await pending.edit_text(
                localize(
                    lang,
                    "Model repeated a recent quest title. Run command again for a new one.",
                    "Модель повторила недавню назву квесту. Запусти команду ще раз.",
                )
            )
            return

        proposal_payload = {
            "title": validated["title"],
            "description": validated["description"],
            "quest_type": validated["quest_type"],
            "difficulty": validated["difficulty"],
            "duration_days": int(validated["duration_days"]),
            "condition": validated["condition"],
            "reward_fun_minutes": int(validated["reward_fun_minutes"]),
            "penalty_fun_minutes": int(validated["penalty_fun_minutes"]),
            "extra_benefit": validated.get("extra_benefit"),
        }
        proposal_id = db.create_quest_proposal(
            user_id=user_id,
            payload=proposal_payload,
            created_at=now,
            source="llm_quest",
            model=model_used,
            prompt_version="quests-2.0",
        )

        _quest_cleanup(context, now.isoformat())
        token = secrets.token_urlsafe(8)
        _quest_pending(context)[token] = {
            "user_id": user_id,
            "proposal_id": proposal_id,
            "expires_at": (now + timedelta(minutes=_QUEST_TTL_MINUTES)).isoformat(),
        }

        cond = proposal_payload["condition"]
        cond_cat = str(cond.get("category", "all"))
        cond_target = int(cond.get("target_minutes", min_target))
        extra = str(proposal_payload.get("extra_benefit") or "").strip()
        extra_line = f"\n🎁 Extra: {extra}" if extra else ""
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"q2:y:{token}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"q2:n:{token}"),
            ]
        ])
        await pending.edit_text(
            (
                "🧩 Quest Proposal\n"
                f"Title: {proposal_payload['title']}\n"
                f"Difficulty: {proposal_payload['difficulty']}\n"
                f"Duration: {proposal_payload['duration_days']} days\n"
                f"Target: {cond_target}m ({cond_cat})\n"
                f"Reward/Penalty: +{proposal_payload['reward_fun_minutes']}m / -{proposal_payload['penalty_fun_minutes']}m"
                f"{extra_line}\n\n"
                f"model: {model_used}"
            ),
            reply_markup=kb,
        )
        return

    # --- Chat subcommands (was /coach) ---
    if context.args and context.args[0].lower() == "chat":
        question_args = context.args[1:]
        question = " ".join(question_args).strip()
        if not question:
            await update.effective_message.reply_text(localize(lang, "Usage: /llm chat <message>", "Використання: /llm chat <повідомлення>"))
            return
        has_any_key = settings.openrouter_api_key or settings.openai_api_key or settings.google_api_key or settings.anthropic_api_key
        if not has_any_key:
            await update.effective_message.reply_text(t("llm_disabled_key", lang))
            return
        day_key = now.date().isoformat()
        usage = db.get_llm_usage(user_id, day_key)
        if usage.request_count >= LLM_DAILY_LIMIT:
            await update.effective_message.reply_text(localize(lang, "Daily /llm limit reached. Try again tomorrow.", "Денний ліміт /llm вичерпано. Спробуй завтра."))
            return
        if usage.last_request_at and (now - usage.last_request_at).total_seconds() < LLM_COOLDOWN_SECONDS:
            await update.effective_message.reply_text(localize(lang, "Please wait a bit before the next message.", "Зачекай трохи перед наступним повідомленням."))
            return
        db.increment_llm_usage(user_id, day_key, now)
        if update.effective_chat:
            await update.effective_chat.send_action(ChatAction.TYPING)
        pending = await update.effective_message.reply_text(localize(lang, "Thinking...", "Думаю..."))
        user_settings = db.get_settings(user_id)
        result = run_llm_agent(db=db, settings=settings, user_id=user_id, now=now, question=question, tier_override=user_settings.preferred_tier, is_chat_mode=True)
        answer = str(result.get("answer", "")).strip()
        model_used = str(result.get("model", "unknown"))
        if not answer:
            await pending.edit_text(localize(lang, "Could not respond right now. Try again later.", "Зараз не зміг відповісти. Спробуй пізніше."))
            return
        try:
            await pending.edit_text(f"{answer}\n\n`chat | {model_used}`", parse_mode="Markdown")
        except Exception:
            await pending.edit_text(f"{answer}\n\nchat | {model_used}")
        return

    if context.args and context.args[0].lower() == "clear":
        count = db.clear_coach_messages(user_id)
        await update.effective_message.reply_text(localize(lang, f"Conversation cleared ({count} messages removed).", f"Розмову очищено ({count} повідомлень видалено)."))
        return

    if context.args and context.args[0].lower() == "memory":
        memories = db.list_coach_memories(user_id)
        if not memories:
            await update.effective_message.reply_text(localize(lang, "No memories stored yet.", "Поки немає збережених спогадів."))
            return
        lines = [localize(lang, "Your memories:", "Твої спогади:")]
        for mem in memories:
            tag_text = f" [{mem.tags}]" if mem.tags else ""
            lines.append(f"{mem.id}. ({mem.category}{tag_text}) {mem.content}")
        await update.effective_message.reply_text("\n".join(lines))
        return

    if context.args and context.args[0].lower() == "forget":
        if len(context.args) < 2 or not context.args[1].isdigit():
            await update.effective_message.reply_text(localize(lang, "Usage: /llm forget <id>", "Використання: /llm forget <id>"))
            return
        ok = db.remove_coach_memory(user_id, int(context.args[1]))
        await update.effective_message.reply_text(
            localize(lang, "Memory removed.", "Спогад видалено.") if ok else localize(lang, "Memory not found.", "Спогад не знайдено.")
        )
        return

    # --- Tier subcommand ---
    tier_override: str | None = None
    model_preference: str | None = None
    question_args = context.args
    if context.args and context.args[0].lower() == "tier":
        valid_tiers = ("free", "open_source_cheap", "top_tier")
        if len(context.args) < 2:
            user_settings = db.get_settings(user_id)
            current = user_settings.preferred_tier or "default"
            await update.effective_message.reply_text(
                localize(lang, f"Current tier: {current}\nSet: /llm tier <{'|'.join(valid_tiers)}>\nReset: /llm tier default", f"Поточний рівень: {current}\nВстановити: /llm tier <{'|'.join(valid_tiers)}>\nСкинути: /llm tier default")
            )
            return
        requested = context.args[1].strip().lower()
        if requested == "default":
            db.update_preferred_tier(user_id, None)
            await update.effective_message.reply_text(localize(lang, "Tier reset to default.", "Рівень скинуто до стандартного."))
            return
        if requested not in valid_tiers:
            if len(context.args) >= 3:
                # /llm tier <name> <question>
                tier_override = requested
                question_args = context.args[2:]
            else:
                await update.effective_message.reply_text(localize(lang, f"Unknown tier. Choose: {', '.join(valid_tiers)}", f"Невідомий рівень. Обери: {', '.join(valid_tiers)}"))
                return
        elif len(context.args) >= 3:
            tier_override = requested
            question_args = context.args[2:]
        else:
            db.update_preferred_tier(user_id, requested)
            await update.effective_message.reply_text(localize(lang, f"Tier set to {requested}.", f"Рівень встановлено: {requested}."))
            return

    if not tier_override and context.args and len(context.args) >= 2 and context.args[0].lower() in ("gpt", "claude", "gemini"):
        model_preference = context.args[0].lower()
        tier_override = "top_tier"
        question_args = context.args[1:]

    # Use saved tier preference as fallback
    if not tier_override:
        user_settings = db.get_settings(user_id)
        if user_settings.preferred_tier:
            tier_override = user_settings.preferred_tier
    # Require at least one API key
    if not model_preference and not settings.openrouter_api_key:
        await update.effective_message.reply_text(t("llm_disabled_key", lang))
        return

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


async def handle_quest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    parts = data.split(":", maxsplit=2)
    if len(parts) < 3:
        return
    action, token = parts[1], parts[2]

    store = _quest_pending(context)
    entry = store.get(token)
    if not entry or int(entry.get("user_id") or 0) != user_id:
        await query.message.edit_text(localize(lang, "Expired or invalid request.", "Запит застарів або недійсний."))
        return
    expires_at = str(entry.get("expires_at") or "")
    if expires_at and expires_at <= now.isoformat():
        store.pop(token, None)
        await query.message.edit_text(localize(lang, "Quest proposal expired. Generate again.", "Пропозиція квесту застаріла. Згенеруй ще раз."))
        return

    proposal_id = int(entry.get("proposal_id") or 0)
    proposal = db.get_quest_proposal(proposal_id)
    if not proposal or proposal.get("status") != "pending":
        store.pop(token, None)
        await query.message.edit_text(localize(lang, "Quest proposal is no longer available.", "Пропозиція квесту більше недоступна."))
        return

    if action == "n":
        db.set_quest_proposal_status(proposal_id, "declined", now)
        store.pop(token, None)
        payload = proposal.get("payload", {})
        title = str(payload.get("title", "Quest")).strip()
        try:
            db.add_coach_memory(
                user_id=user_id,
                category="context",
                content=f"declined quest: {title}",
                tags="quest,declined",
                created_at=now,
            )
        except Exception:
            pass
        await query.message.edit_text(localize(lang, "Declined.", "Відхилено."))
        return

    if action != "y":
        await query.message.edit_text(localize(lang, "Invalid request.", "Невірний запит."))
        return

    active = db.list_active_quests(user_id, now)
    if len(active) >= 5:
        await query.message.edit_text(
            localize(
                lang,
                "Too many active quests (5). Complete or reset first.",
                "Забагато активних квестів (5). Спочатку заверши або скинь.",
            )
        )
        return

    payload = proposal.get("payload", {})
    if not isinstance(payload, dict):
        await query.message.edit_text(localize(lang, "Invalid quest payload.", "Невірний payload квесту."))
        return
    stats = _weekly_stats(db, user_id, now - timedelta(days=28), now)
    validated = _validate_llm_quest(
        payload,
        stats,
        random.Random(f"{user_id}:{proposal_id}:{now.isoformat()}"),
        difficulty_hint=str(payload.get("difficulty", "medium")),
        duration_days_hint=int(payload.get("duration_days", 7)),
    )
    if not validated:
        await query.message.edit_text(localize(lang, "Quest payload failed validation.", "Payload квесту не пройшов валідацію."))
        return

    duration_days = int(validated["duration_days"])
    quest = db.insert_quest(
        user_id=user_id,
        title=str(validated["title"]),
        description=str(validated["description"]),
        quest_type=str(validated["quest_type"]),
        difficulty=str(validated["difficulty"]),
        reward_fun_minutes=int(validated["reward_fun_minutes"]),
        penalty_fun_minutes=int(validated["penalty_fun_minutes"]),
        duration_days=duration_days,
        condition=dict(validated["condition"]),
        starts_at=now,
        expires_at=now + timedelta(days=duration_days),
        created_at=now,
        source="llm_manual",
        status="active",
    )
    db.set_quest_proposal_status(proposal_id, "accepted", now)
    store.pop(token, None)
    try:
        db.add_coach_memory(
            user_id=user_id,
            category="context",
            content=(
                f"accepted quest: [{quest.difficulty}] {quest.title} "
                f"({quest.duration_days}d, +{quest.reward_fun_minutes}/-{quest.penalty_fun_minutes})"
            ),
            tags=f"quest,accepted,{quest.difficulty}",
            created_at=now,
        )
    except Exception:
        pass
    await query.message.edit_text(
        (
            localize(lang, "Quest accepted.", "Квест прийнято.")
            + "\n"
            + f"{quest.title} ({quest.difficulty}, {quest.duration_days}d)\n"
            + f"Reward/Penalty: +{quest.reward_fun_minutes}m / -{quest.penalty_fun_minutes}m"
        )
    )


def _ff_pending(context: ContextTypes.DEFAULT_TYPE) -> dict[str, dict[str, object]]:
    store = context.application.bot_data.get(_FF_PENDING_KEY)
    if isinstance(store, dict):
        return store
    created: dict[str, dict[str, object]] = {}
    context.application.bot_data[_FF_PENDING_KEY] = created
    return created


def _ff_cleanup(context: ContextTypes.DEFAULT_TYPE, now_iso: str) -> None:
    store = _ff_pending(context)
    stale = [t for t, p in store.items() if str(p.get("expires_at", "")) <= now_iso]
    for t in stale:
        store.pop(t, None)


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

    _ff_cleanup(context, now.isoformat())
    token = secrets.token_urlsafe(8)
    cat = parsed.category or "build"
    _ff_pending(context)[token] = {
        "user_id": user_id,
        "action": parsed.action,
        "category": cat,
        "minutes": parsed.minutes,
        "note": parsed.note,
        "expires_at": (now + timedelta(minutes=_FF_TTL_MINUTES)).isoformat(),
    }

    if parsed.action == "log":
        note_part = f" — {parsed.note}" if parsed.note else ""
        desc = f"{parsed.minutes}m {cat}{note_part}"
    else:
        note_part = f" — {parsed.note}" if parsed.note else ""
        desc = f"{parsed.minutes}m fun spend{note_part}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✓ Accept", callback_data=f"ff:y:{token}"),
            InlineKeyboardButton("✗ Decline", callback_data=f"ff:n:{token}"),
        ]
    ])
    await update.effective_message.reply_text(
        localize(lang, "Parsed: {desc}\nConfirm?", "Розібрано: {desc}\nПідтвердити?", desc=desc),
        reply_markup=keyboard,
    )


async def handle_freeform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)
    data = query.data or ""

    # ff:y:<token> or ff:n:<token>
    parts = data.split(":", maxsplit=2)
    if len(parts) < 3:
        return
    action, token = parts[1], parts[2]

    store = _ff_pending(context)
    payload = store.get(token)
    if not payload or payload.get("user_id") != user_id:
        await query.message.edit_text(localize(lang, "Expired or invalid.", "Час вийшов або недійсне."))
        return

    if action == "n":
        store.pop(token, None)
        await query.message.edit_text(localize(lang, "Declined. Nothing logged.", "Відхилено. Нічого не записано."))
        return

    # Accept
    store.pop(token, None)
    p_action = str(payload["action"])
    p_cat = str(payload["category"])
    p_minutes = int(payload["minutes"])  # type: ignore[arg-type]
    p_note = payload.get("note")
    p_note_str = str(p_note) if p_note else None

    if p_action == "log":
        add_productive_entry(
            db=db,
            user_id=user_id,
            minutes=p_minutes,
            category=p_cat,
            note=p_note_str,
            created_at=now,
            source="llm",
            timer_mode=False,
        )
    else:
        db.add_entry(
            user_id=user_id,
            kind="spend",
            category="spend",
            minutes=p_minutes,
            note=p_note_str,
            created_at=now,
            source="llm",
        )

    sync_quests_for_user(db, user_id, now)
    view = compute_status(db, user_id, now)
    await query.message.edit_text(
        f"{localize(lang, 'Confirmed and logged.', 'Підтверджено та записано.')}\n\n{status_message(view, lang=lang)}"
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
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["timer", "t"], cmd_timer))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("llm", cmd_llm))
    app.add_handler(CommandHandler(["notes", "rules"], cmd_notes))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(log:|spend:|status$|undo$|timer:stop$)"))
    app.add_handler(CallbackQueryHandler(handle_quest_callback, pattern=r"^q2:"))
    app.add_handler(CallbackQueryHandler(handle_freeform_callback, pattern=r"^ff:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))


def register_unknown_handler(app: Application) -> None:
    # Register this after all command modules, in the default group, so it only
    # handles truly unknown commands.
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
