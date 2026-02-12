from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from tg_time_logger.agents.orchestration.coach_runner import run_coach_agent
from tg_time_logger.commands_core import LLM_COOLDOWN_SECONDS, LLM_DAILY_LIMIT
from tg_time_logger.commands_shared import (
    get_db,
    get_settings,
    get_user_language,
    touch_user,
)
from tg_time_logger.i18n import localize, t


async def cmd_coach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    settings = get_settings(context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    if not db.is_feature_enabled("llm"):
        await update.effective_message.reply_text(
            localize(lang, "LLM features are currently disabled by admin.",
                     "LLM-функції зараз вимкнені адміністратором.")
        )
        return
    if not db.is_feature_enabled("agent"):
        await update.effective_message.reply_text(
            localize(lang, "Agent runtime is currently disabled by admin.",
                     "Середовище агента зараз вимкнено адміністратором.")
        )
        return
    if not settings.openrouter_api_key:
        await update.effective_message.reply_text(t("llm_disabled_key", lang))
        return

    # Subcommands (no LLM quota consumed)
    if context.args and context.args[0].lower() == "clear":
        count = db.clear_coach_messages(user_id)
        await update.effective_message.reply_text(
            localize(lang,
                     f"Conversation cleared ({count} messages removed).",
                     f"Розмову очищено ({count} повідомлень видалено).")
        )
        return

    if context.args and context.args[0].lower() == "memory":
        memories = db.list_coach_memories(user_id)
        if not memories:
            await update.effective_message.reply_text(
                localize(lang, "No memories stored yet.", "Поки немає збережених спогадів.")
            )
            return
        lines = [localize(lang, "Your memories:", "Твої спогади:")]
        for mem in memories:
            tag_text = f" [{mem.tags}]" if mem.tags else ""
            lines.append(f"{mem.id}. ({mem.category}{tag_text}) {mem.content}")
        await update.effective_message.reply_text("\n".join(lines))
        return

    if context.args and context.args[0].lower() == "forget":
        if len(context.args) < 2 or not context.args[1].isdigit():
            await update.effective_message.reply_text(
                localize(lang, "Usage: /coach forget <id>", "Використання: /coach forget <id>")
            )
            return
        ok = db.remove_coach_memory(user_id, int(context.args[1]))
        await update.effective_message.reply_text(
            localize(lang, "Memory removed.", "Спогад видалено.")
            if ok
            else localize(lang, "Memory not found.", "Спогад не знайдено.")
        )
        return

    # Main coach interaction
    message = " ".join(context.args).strip() if context.args else ""
    if not message:
        await update.effective_message.reply_text(
            localize(
                lang,
                "Usage: /coach <message>\n\n"
                "Subcommands:\n"
                "/coach clear - clear conversation history\n"
                "/coach memory - view saved memories\n"
                "/coach forget <id> - remove a memory",
                "Використання: /coach <повідомлення>\n\n"
                "Підкоманди:\n"
                "/coach clear - очистити історію розмови\n"
                "/coach memory - переглянути збережені спогади\n"
                "/coach forget <id> - видалити спогад",
            )
        )
        return

    # Shared rate limiting with /llm
    day_key = now.date().isoformat()
    usage = db.get_llm_usage(user_id, day_key)
    if usage.request_count >= LLM_DAILY_LIMIT:
        await update.effective_message.reply_text(
            localize(lang, "Daily LLM limit reached. Try again tomorrow.",
                     "Денний ліміт LLM вичерпано. Спробуй завтра.")
        )
        return
    if usage.last_request_at and (now - usage.last_request_at).total_seconds() < LLM_COOLDOWN_SECONDS:
        await update.effective_message.reply_text(
            localize(lang, "Please wait a bit before the next message.",
                     "Зачекай трохи перед наступним повідомленням.")
        )
        return

    db.increment_llm_usage(user_id, day_key, now)

    if update.effective_chat:
        await update.effective_chat.send_action(ChatAction.TYPING)

    pending = await update.effective_message.reply_text(
        localize(lang, "Thinking...", "Думаю...")
    )

    result = run_coach_agent(
        db=db,
        settings=settings,
        user_id=user_id,
        now=now,
        message=message,
    )

    answer = str(result.get("answer", "")).strip()
    model_used = str(result.get("model", "unknown"))
    if not answer:
        await pending.edit_text(
            localize(lang, "Coach could not respond right now. Try again later.",
                     "Коуч зараз не зміг відповісти. Спробуй пізніше.")
        )
        return

    try:
        await pending.edit_text(f"{answer}\n\n`coach | {model_used}`", parse_mode="Markdown")
    except Exception:
        await pending.edit_text(f"{answer}\n\ncoach | {model_used}")


def register_coach_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("coach", cmd_coach))
