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


def _has_any_llm_key(settings) -> bool:
    return bool(
        settings.openrouter_api_key
        or settings.openai_api_key
        or settings.google_api_key
        or settings.anthropic_api_key
    )


def _quest_candidate_tiers(settings, active_tier: str, available_tiers: list[str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    available = set(available_tiers)

    def add(tier: str) -> None:
        if tier in available and tier not in seen:
            candidates.append(tier)
            seen.add(tier)

    add(active_tier)
    if settings.openai_api_key:
        add("gpt")
    if settings.anthropic_api_key:
        add("claude")
    if settings.google_api_key:
        add("gemini")
    if settings.openrouter_api_key:
        add("open_source")
        add("free")
        add("top")
    return candidates[:6]


def _build_quest_json_repair_prompt(
    *,
    raw_answer: str,
    difficulty: str,
    duration_days: int,
    min_target: int,
    reward_lo: int,
    reward_hi: int,
) -> str:
    raw = raw_answer.strip()
    if len(raw) > 3500:
        raw = raw[:3500]
    return (
        "Convert the text below into exactly one valid JSON object for a quest.\n"
        "If the text is incomplete, infer missing fields while following constraints.\n"
        "Return JSON object only. No markdown.\n\n"
        "Constraints:\n"
        f"- difficulty must be {difficulty}\n"
        f"- duration_days must be {duration_days}\n"
        f"- condition.type must be total_minutes\n"
        f"- condition.target_minutes must be >= {min_target}\n"
        "- condition.category must be build|study|training|all\n"
        f"- reward_fun_minutes must be integer in [{reward_lo}, {reward_hi}]\n"
        "- penalty_fun_minutes must equal reward_fun_minutes\n\n"
        "Required keys:\n"
        "{\n"
        '  "title": "short unique title",\n'
        '  "description": "one sentence",\n'
        '  "quest_type": "challenge",\n'
        f'  "difficulty": "{difficulty}",\n'
        f'  "duration_days": {duration_days},\n'
        f'  "condition": {{"type":"total_minutes","target_minutes":{min_target},"category":"all"}},\n'
        f'  "reward_fun_minutes": {reward_lo},\n'
        f'  "penalty_fun_minutes": {reward_lo},\n'
        '  "extra_benefit": "optional text"\n'
        "}\n\n"
        "Source text:\n"
        f"{raw}"
    )


def _llm_limits(db) -> tuple[int, int]:
    cfg = db.get_app_config()
    try:
        daily_limit = int(cfg.get("llm.daily_limit", 0) or 0)
    except (TypeError, ValueError):
        daily_limit = 0
    try:
        cooldown_seconds = int(cfg.get("llm.cooldown_seconds", 0) or 0)
    except (TypeError, ValueError):
        cooldown_seconds = 0
    return max(0, daily_limit), max(0, cooldown_seconds)


def _check_and_consume_llm_quota(
    db,
    *,
    user_id: int,
    now,
    lang: str,
    cooldown_message_en: str,
    cooldown_message_uk: str,
) -> str | None:
    day_key = now.date().isoformat()
    usage = db.get_llm_usage(user_id, day_key)
    daily_limit, cooldown_seconds = _llm_limits(db)

    if daily_limit > 0 and usage.request_count >= daily_limit:
        return localize(
            lang,
            f"Daily /llm limit reached ({daily_limit}). Try again tomorrow.",
            f"Денний ліміт /llm вичерпано ({daily_limit}). Спробуй завтра.",
        )
    if cooldown_seconds > 0 and usage.last_request_at and (now - usage.last_request_at).total_seconds() < cooldown_seconds:
        return localize(lang, cooldown_message_en, cooldown_message_uk)

    db.increment_llm_usage(user_id, day_key, now)
    return None


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
    for token in stale:
        store.pop(token, None)


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
) -> str:
    recent_block = "\n".join(f"- {x}" for x in recent_quest_lines) if recent_quest_lines else "- none"
    memory_block = "\n".join(f"- {x}" for x in memory_lines) if memory_lines else "- none"
    return (
        "Create exactly one quest proposal as JSON object only (no markdown, no commentary).\n"
        "Return strictly valid JSON. All numeric fields must be integers.\n"
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
        "Rules:\n"
        f"- condition.target_minutes must be >= {min_target}\n"
        "- condition.category must be 'all', 'build', 'study', or 'training'. Use 'all' for hard quests.\n"
        f"- reward_fun_minutes must be an integer in [{reward_lo}, {reward_hi}]\n"
        "- penalty_fun_minutes must equal reward_fun_minutes\n\n"
        "Return JSON with keys:\n"
        "{\n"
        '  "title": "short unique title",\n'
        '  "description": "one sentence",\n'
        '  "quest_type": "challenge",\n'
        f'  "difficulty": "{difficulty}",\n'
        f'  "duration_days": {duration_days},\n'
        f'  "condition": {{"type":"total_minutes","target_minutes":{min_target},"category":"all"}},\n'
        f'  "reward_fun_minutes": {reward_lo},\n'
        f'  "penalty_fun_minutes": {reward_lo},\n'
        '  "extra_benefit": "optional text, especially for hard quests"\n'
        "}\n"
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

    model_cfg = load_model_config(settings.agent_models_path)
    available_tiers = list(model_cfg.tiers.keys())
    app_default_raw = str(db.get_app_config_value("agent.default_tier") or model_cfg.default_tier)
    app_default_tier = resolve_available_tier(app_default_raw, available_tiers) or model_cfg.default_tier
    user_settings = db.get_settings(user_id)
    preferred_tier = resolve_available_tier(user_settings.preferred_tier, available_tiers)
    active_tier = preferred_tier or app_default_tier

    if context.args and context.args[0].lower() == "models":
        rows = [f"Default tier: {model_cfg.default_tier}"]
        for tier_name, tier in model_cfg.tiers.items():
            ids = ", ".join(m.id for m in tier.models[:4])
            rows.append(f"- {tier_name}: {ids}")
        await update.effective_message.reply_text("\n".join(rows))
        return

    if context.args and context.args[0].lower() == "health":
        tier_spec = model_cfg.get_tier(active_tier)
        primary_model = tier_spec.models[0].id if tier_spec and tier_spec.models else "n/a"
        daily_limit, cooldown_seconds = _llm_limits(db)
        key_rows = [
            f"- OpenRouter key: {'set' if settings.openrouter_api_key else 'missing'}",
            f"- OpenAI key: {'set' if settings.openai_api_key else 'missing'}",
            f"- Google key: {'set' if settings.google_api_key else 'missing'}",
            f"- Anthropic key: {'set' if settings.anthropic_api_key else 'missing'}",
        ]
        last = db.get_last_user_llm_audit(user_id)
        if last:
            payload = last.get("payload") if isinstance(last.get("payload"), dict) else {}
            last_status = str(payload.get("status", "unknown"))
            last_model = str(payload.get("model", "unknown"))
            last_tier = str(payload.get("tier", "unknown"))
            last_line = (
                f"- Last: {last_status} | {last_model} | tier={last_tier} | {last.get('created_at')}"
            )
        else:
            last_line = "- Last: no LLM calls yet"

        await update.effective_message.reply_text(
            (
                "LLM Health\n"
                f"- Active tier: {active_tier}\n"
                f"- Preferred tier: {preferred_tier or 'default'}\n"
                f"- Default tier: {app_default_tier}\n"
                f"- Primary model: {primary_model}\n"
                f"- Daily limit: {'unlimited' if daily_limit == 0 else daily_limit}\n"
                f"- Cooldown: {cooldown_seconds}s\n"
                "Keys:\n"
                f"{chr(10).join(key_rows)}\n"
                f"{last_line}"
            )
        )
        return

    if context.args and context.args[0].lower() == "tier":
        await update.effective_message.reply_text(
            localize(
                lang,
                "Tier control moved to /settings tier. Example: /settings tier open_source",
                "Керування tier перенесено в /settings tier. Приклад: /settings tier open_source",
            )
        )
        return

    if context.args and context.args[0].lower() in {"gpt", "claude", "gemini"}:
        await update.effective_message.reply_text(
            localize(
                lang,
                "Provider shortcuts were removed. Use /settings tier gpt|claude|gemini, then /llm <question>.",
                "Скорочення провайдерів прибрано. Використай /settings tier gpt|claude|gemini, потім /llm <запит>.",
            )
        )
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

        if not _has_any_llm_key(settings):
            await update.effective_message.reply_text(t("llm_disabled_key", lang))
            return

        limit_msg = _check_and_consume_llm_quota(
            db,
            user_id=user_id,
            now=now,
            lang=lang,
            cooldown_message_en="Please wait a bit before the next /llm request.",
            cooldown_message_uk="Зачекай трохи перед наступним /llm запитом.",
        )
        if limit_msg:
            await update.effective_message.reply_text(limit_msg)
            return
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

        prompt = _build_quest_generation_prompt(
            difficulty=difficulty,
            duration_days=duration_days,
            min_target=min_target,
            reward_lo=reward_lo,
            reward_hi=reward_hi,
            stats=stats,
            recent_quest_lines=recent_lines[:8],
            memory_lines=memory_lines[:6],
        )

        compact_prompt = _build_quest_generation_prompt(
            difficulty=difficulty,
            duration_days=duration_days,
            min_target=min_target,
            reward_lo=reward_lo,
            reward_hi=reward_hi,
            stats=stats,
            recent_quest_lines=[],
            memory_lines=[],
        )
        quest_system_prompt = (
            "You create productivity quests. "
            "Output exactly one valid JSON object. No markdown, no prose."
        )
        repair_system_prompt = (
            "You normalize output into strict JSON objects. "
            "Return exactly one JSON object, no prose."
        )
        candidate_tiers = _quest_candidate_tiers(settings, active_tier, available_tiers)

        answer = ""
        model_used = "unknown"
        status = "unknown"
        payload = None
        attempt_lines: list[str] = []

        for attempt_tier in candidate_tiers:
            for prompt_label, prompt_text in (("full", prompt), ("compact", compact_prompt)):
                result = run_llm_text(
                    db=db,
                    settings=settings,
                    user_id=user_id,
                    now=now,
                    prompt=prompt_text,
                    system_prompt=quest_system_prompt,
                    tier_override=attempt_tier,
                    allow_tier_escalation=False,
                    max_tokens=520,
                )
                answer = str(result.get("answer", "")).strip()
                model_used = str(result.get("model", "unknown"))
                status = str(result.get("status", "unknown"))
                attempt_lines.append(f"{attempt_tier}/{prompt_label}:{status}:{model_used}")
                payload = extract_quest_payload(answer)
                if payload:
                    break

                if answer:
                    repair_prompt = _build_quest_json_repair_prompt(
                        raw_answer=answer,
                        difficulty=difficulty,
                        duration_days=duration_days,
                        min_target=min_target,
                        reward_lo=reward_lo,
                        reward_hi=reward_hi,
                    )
                    repair_result = run_llm_text(
                        db=db,
                        settings=settings,
                        user_id=user_id,
                        now=now,
                        prompt=repair_prompt,
                        system_prompt=repair_system_prompt,
                        tier_override=attempt_tier,
                        allow_tier_escalation=False,
                        max_tokens=420,
                    )
                    repair_answer = str(repair_result.get("answer", "")).strip()
                    repair_model = str(repair_result.get("model", "unknown"))
                    repair_status = str(repair_result.get("status", "unknown"))
                    attempt_lines.append(f"{attempt_tier}/repair:{repair_status}:{repair_model}")
                    repair_payload = extract_quest_payload(repair_answer)
                    if repair_payload:
                        payload = repair_payload
                        answer = repair_answer
                        model_used = repair_model
                        status = repair_status
                        break
            if payload:
                break

        if not payload:
            attempts_short = "; ".join(attempt_lines[-6:]) if attempt_lines else "none"
            await pending.edit_text(
                localize(
                    lang,
                    f"Could not parse quest JSON. Try again. (status: {status}, attempts: {attempts_short})",
                    f"Не вдалося розібрати JSON квесту. Спробуй ще раз. (status: {status}, спроби: {attempts_short})",
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
        start_str = now.strftime('%Y-%m-%d')
        end_str = (now + timedelta(days=proposal_payload['duration_days'])).strftime('%Y-%m-%d')
        await pending.edit_text(
            (
                "🧩 Quest Proposal\n"
                f"Title: {proposal_payload['title']}\n"
                f"Difficulty: {proposal_payload['difficulty']}\n"
                f"Duration: {start_str} to {end_str}\n"
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
        if not _has_any_llm_key(settings):
            await update.effective_message.reply_text(t("llm_disabled_key", lang))
            return
        limit_msg = _check_and_consume_llm_quota(
            db,
            user_id=user_id,
            now=now,
            lang=lang,
            cooldown_message_en="Please wait a bit before the next message.",
            cooldown_message_uk="Зачекай трохи перед наступним повідомленням.",
        )
        if limit_msg:
            await update.effective_message.reply_text(limit_msg)
            return
        if update.effective_chat:
            await update.effective_chat.send_action(ChatAction.TYPING)
        pending = await update.effective_message.reply_text(localize(lang, "Thinking...", "Думаю..."))
        result = run_llm_agent(
            db=db,
            settings=settings,
            user_id=user_id,
            now=now,
            question=question,
            tier_override=active_tier,
            is_chat_mode=True,
        )
        answer = str(result.get("answer", "")).strip()
        model_used = str(result.get("model", "unknown"))
        fallback_occurred = bool(result.get("fallback_occurred", False))
        tier_used = str(result.get("tier", "unknown"))
        
        if not answer:
            await pending.edit_text(localize(lang, "Could not respond right now. Try again later.", "Зараз не зміг відповісти. Спробуй пізніше."))
            return
            
        fallback_warning = f"\n⚠️ _Fell back to {tier_used} tier ({model_used})_\n" if fallback_occurred else ""
        
        try:
            await pending.edit_text(f"{answer}\n{fallback_warning}\n`chat | {model_used}`", parse_mode="Markdown")
        except Exception:
            await pending.edit_text(f"{answer}\n{fallback_warning}\nchat | {model_used}")
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

    if not _has_any_llm_key(settings):
        await update.effective_message.reply_text(t("llm_disabled_key", lang))
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.effective_message.reply_text(t("llm_usage", lang))
        return

    limit_msg = _check_and_consume_llm_quota(
        db,
        user_id=user_id,
        now=now,
        lang=lang,
        cooldown_message_en="Please wait a bit before the next /llm question.",
        cooldown_message_uk="Зачекай трохи перед наступним /llm запитом.",
    )
    if limit_msg:
        await update.effective_message.reply_text(limit_msg)
        return

    pending = await update.effective_message.reply_text(f"🤖 {t('llm_working', lang)}")
    result = run_llm_agent(
        db=db,
        settings=settings,
        user_id=user_id,
        now=now,
        question=question,
        tier_override=active_tier,
    )
    answer = str(result.get("answer", "")).strip()
    model_used = str(result.get("model", "unknown"))
    tier_used = str(result.get("tier", "unknown"))
    status = str(result.get("status", "unknown"))
    fallback_occurred = bool(result.get("fallback_occurred", False))
    prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
    completion_tokens = int(result.get("completion_tokens", 0) or 0)
    
    if not answer:
        await pending.edit_text(localize(lang, "LLM could not answer right now. Try again later.", "LLM зараз не зміг відповісти. Спробуй пізніше."))
        return
        
    fallback_warning = f"\n\n⚠️ _Note: Requested tier failed. Fell back to {tier_used} tier ({model_used})._" if fallback_occurred else ""
    
    await pending.edit_text(
        f"{answer}{fallback_warning}\n\n`model: {model_used} | tier: {tier_used} | status: {status} | tok: {prompt_tokens}/{completion_tokens}`"
    )



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
    start_str = quest.starts_at.strftime('%Y-%m-%d')
    end_str = quest.expires_at.strftime('%Y-%m-%d')
    try:
        db.add_coach_memory(
            user_id=user_id,
            category="context",
            content=(
                f"accepted quest: [{quest.difficulty}] {quest.title} "
                f"({start_str} to {end_str}, +{quest.reward_fun_minutes}/-{quest.penalty_fun_minutes})"
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
            + f"{quest.title} ({quest.difficulty}, {start_str} to {end_str})\n"
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
    for token in stale:
        store.pop(token, None)


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




def register_llm_handlers(app: Application) -> None:
    app.add_handler(CommandHandler('llm', cmd_llm))
    app.add_handler(CallbackQueryHandler(handle_quest_callback, pattern=r'^q2:'))
    app.add_handler(CallbackQueryHandler(handle_freeform_callback, pattern=r'^ff:'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_form))
