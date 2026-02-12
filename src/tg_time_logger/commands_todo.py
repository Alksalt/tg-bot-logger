from __future__ import annotations

import logging
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from tg_time_logger.agents.execution.config import load_model_config
from tg_time_logger.agents.execution.llm_client import call_openrouter, parse_json_object
from tg_time_logger.commands_shared import get_db, get_settings, get_user_language, touch_user
from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.i18n import localize
from tg_time_logger.service import add_productive_entry

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"study", "build", "training", "other"}


# ── LLM categorizer ──────────────────────────────────────────────


def _suggest_category(title: str, settings) -> dict | None:
    """Call free-tier model to classify a completed task into a log category."""
    model_cfg = load_model_config(settings.agent_models_path)
    tier = model_cfg.get_tier("free")
    if not tier or not settings.openrouter_api_key:
        return None
    messages = [
        {
            "role": "system",
            "content": (
                "Classify this completed task into ONE category: study, build, training, or other.\n"
                'Return JSON only: {"category": "study|build|training|other", "note": "brief description"}\n'
                "Rules:\n"
                "- study = learning, reading, courses, homework\n"
                "- build = coding, creating, projects, writing\n"
                "- training = exercise, sports, physical activity\n"
                "- other = everything else (meals, errands, meetings)"
            ),
        },
        {"role": "user", "content": title},
    ]
    for model in tier.models:
        try:
            resp = call_openrouter(
                model=model,
                messages=messages,
                api_key=settings.openrouter_api_key,
                max_tokens=80,
                reasoning_enabled=False,
            )
        except Exception:
            continue
        if resp:
            parsed = parse_json_object(resp.text)
            if parsed and parsed.get("category") in _VALID_CATEGORIES:
                return parsed
    return None


# ── Rendering ─────────────────────────────────────────────────────


def _format_duration(minutes: int) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes // 60}h"
    if minutes >= 60:
        return f"{minutes // 60}h{minutes % 60}m"
    return f"{minutes}m"


def _render_todo_list(items: list, plan_date: str, lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    done_count = sum(1 for i in items if i.status == "done")
    total = len(items)

    # Format date as DD.MM
    parts = plan_date.split("-")
    date_label = f"{parts[2]}.{parts[1]}" if len(parts) == 3 else plan_date

    if not items:
        text = localize(
            lang,
            f"Plan for {date_label}: empty\n\nAdd tasks with /todo add <title>",
            f"План на {date_label}: порожній\n\nДодай завдання: /todo add <назва>",
        )
        return text, None

    header = localize(
        lang,
        f"Plan for {date_label} ({done_count}/{total}):",
        f"План на {date_label} ({done_count}/{total}):",
    )
    lines = [header]
    for idx, item in enumerate(items, 1):
        icon = "\u2705" if item.status == "done" else "\u2b1c"
        dur = f" ({_format_duration(item.duration_minutes)})" if item.duration_minutes else ""
        lines.append(f"{idx}. {icon} {item.title}{dur}")

    text = "\n".join(lines)

    # Build tick buttons for pending items
    pending = [(idx, item) for idx, item in enumerate(items, 1) if item.status == "pending"]
    if not pending:
        return text, None

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, item in pending:
        row.append(InlineKeyboardButton(f"\u2705{idx}", callback_data=f"todo:done:{item.id}"))
        if len(row) >= 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return text, InlineKeyboardMarkup(rows)


# ── Command handler ───────────────────────────────────────────────


async def cmd_todo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    lang = get_user_language(context, user_id)

    args = context.args or []
    if not args:
        # Show today's list
        plan_date = now.date().isoformat()
        items = db.list_todos(user_id, plan_date)
        text, keyboard = _render_todo_list(items, plan_date, lang)
        await update.effective_message.reply_text(text, reply_markup=keyboard)
        return

    sub = args[0].lower()

    if sub == "tomorrow":
        plan_date = (now.date() + timedelta(days=1)).isoformat()
        items = db.list_todos(user_id, plan_date)
        text, keyboard = _render_todo_list(items, plan_date, lang)
        await update.effective_message.reply_text(text, reply_markup=keyboard)
        return

    if sub == "add":
        tail = args[1:]
        if not tail:
            await update.effective_message.reply_text(
                localize(lang, "Usage: /todo add [duration] <title>", "Використання: /todo add [тривалість] <назва>")
            )
            return
        # Try to parse first arg as duration
        duration_minutes: int | None = None
        try:
            duration_minutes = parse_duration_to_minutes(tail[0])
            tail = tail[1:]
        except DurationParseError:
            pass
        title = " ".join(tail).strip()
        if not title:
            await update.effective_message.reply_text(
                localize(lang, "Please provide a task title.", "Вкажи назву завдання.")
            )
            return
        plan_date = now.date().isoformat()
        pos = db.next_todo_position(user_id, plan_date)
        item = db.add_todo(user_id, plan_date, title, duration_minutes, pos, now)
        dur_text = f" ({_format_duration(item.duration_minutes)})" if item.duration_minutes else ""
        await update.effective_message.reply_text(
            localize(lang, f"Added: {item.title}{dur_text}", f"Додано: {item.title}{dur_text}")
        )
        return

    if sub == "done":
        if len(args) < 2 or not args[1].isdigit():
            await update.effective_message.reply_text(
                localize(lang, "Usage: /todo done <id>", "Використання: /todo done <id>")
            )
            return
        ok = db.mark_todo_done(int(args[1]), now)
        await update.effective_message.reply_text(
            localize(lang, "Marked done.", "Позначено виконаним.")
            if ok
            else localize(lang, "Task not found or already done.", "Завдання не знайдено або вже виконане.")
        )
        return

    if sub == "rm":
        if len(args) < 2 or not args[1].isdigit():
            await update.effective_message.reply_text(
                localize(lang, "Usage: /todo rm <id>", "Використання: /todo rm <id>")
            )
            return
        ok = db.delete_todo(user_id, int(args[1]))
        await update.effective_message.reply_text(
            localize(lang, "Removed.", "Видалено.")
            if ok
            else localize(lang, "Task not found.", "Завдання не знайдено.")
        )
        return

    if sub == "clear":
        plan_date = now.date().isoformat()
        count = db.clear_pending_todos(user_id, plan_date)
        await update.effective_message.reply_text(
            localize(lang, f"Cleared {count} pending task(s).", f"Очищено {count} завдань.")
        )
        return

    # Unknown subcommand → show usage
    await update.effective_message.reply_text(
        localize(
            lang,
            "Usage: /todo, /todo tomorrow, /todo add, /todo done, /todo rm, /todo clear",
            "Використання: /todo, /todo tomorrow, /todo add, /todo done, /todo rm, /todo clear",
        )
    )


# ── Callback handler ─────────────────────────────────────────────


async def handle_todo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    user_id, _, now = touch_user(update, context)
    db = get_db(context)
    settings = get_settings(context)
    lang = get_user_language(context, user_id)

    data = query.data
    parts = data.split(":")

    if parts[1] == "done" and len(parts) == 3:
        todo_id = int(parts[2])
        item = db.get_todo(todo_id)
        if not item or item.user_id != user_id:
            return

        db.mark_todo_done(todo_id, now)

        # Re-render the todo list in the original message
        items = db.list_todos(user_id, item.plan_date)
        text, keyboard = _render_todo_list(items, item.plan_date, lang)
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except BadRequest:
            pass

        # If item has duration, suggest a category via LLM
        if item.duration_minutes:
            suggestion = _suggest_category(item.title, settings)
            cat = suggestion.get("category", "other") if suggestion else None
            if cat and cat in _VALID_CATEGORIES:
                dur_text = _format_duration(item.duration_minutes)
                btn_row = [
                    InlineKeyboardButton(
                        localize(lang, "Accept", "Прийняти"),
                        callback_data=f"todo:yes:{todo_id}:{cat}",
                    ),
                    InlineKeyboardButton(
                        localize(lang, "Decline", "Відхилити"),
                        callback_data=f"todo:no:{todo_id}",
                    ),
                ]
                await query.message.reply_text(
                    localize(
                        lang,
                        f"\u2705 {item.title} ({dur_text}) \u2014 done!\nLog as {item.duration_minutes}m {cat}?",
                        f"\u2705 {item.title} ({dur_text}) \u2014 виконано!\nЗаписати як {item.duration_minutes}m {cat}?",
                    ),
                    reply_markup=InlineKeyboardMarkup([btn_row]),
                )
            else:
                dur_text = _format_duration(item.duration_minutes)
                await query.message.reply_text(
                    localize(
                        lang,
                        f"\u2705 {item.title} ({dur_text}) \u2014 done!",
                        f"\u2705 {item.title} ({dur_text}) \u2014 виконано!",
                    )
                )
        return

    if parts[1] == "yes" and len(parts) == 4:
        todo_id = int(parts[2])
        cat = parts[3]
        item = db.get_todo(todo_id)
        if not item or item.user_id != user_id or not item.duration_minutes:
            return
        if cat not in _VALID_CATEGORIES:
            return

        if cat in ("study", "build", "training"):
            add_productive_entry(
                db=db,
                user_id=user_id,
                minutes=item.duration_minutes,
                category=cat,
                note=item.title,
                created_at=now,
                source="todo",
            )
        else:
            db.add_entry(
                user_id=user_id,
                kind="other",
                category="other",
                minutes=item.duration_minutes,
                note=item.title,
                created_at=now,
                source="todo",
            )

        dur_text = _format_duration(item.duration_minutes)
        try:
            await query.edit_message_text(
                localize(
                    lang,
                    f"Logged {item.duration_minutes}m {cat} \u2705",
                    f"Записано {item.duration_minutes}m {cat} \u2705",
                )
            )
        except BadRequest:
            pass
        return

    if parts[1] == "no" and len(parts) == 3:
        try:
            await query.edit_message_text(
                localize(lang, "Skipped", "Пропущено")
            )
        except BadRequest:
            pass
        return


def register_todo_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("todo", cmd_todo))
    app.add_handler(CallbackQueryHandler(handle_todo_callback, pattern=r"^todo:"))
