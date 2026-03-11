from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time

from telegram import Bot

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.db_constants import STREAK_MINUTES_REQUIRED
from tg_time_logger.gamification import format_minutes_hm
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import in_quiet_hours, now_local, week_range_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReminderDecision:
    inactivity: bool
    daily_goal: bool


def evaluate_reminders(
    now: datetime,
    productive_today_minutes: int,
    daily_goal_minutes: int,
    has_productive_log_today: bool,
) -> ReminderDecision:
    inactivity_due = now.time() >= time(hour=20, minute=0) and not has_productive_log_today
    goal_due = now.time() >= time(hour=21, minute=30) and productive_today_minutes < daily_goal_minutes
    return ReminderDecision(inactivity=inactivity_due, daily_goal=goal_due)


async def run_sunday_summary(db: Database, settings: Settings) -> None:
    if not db.is_job_enabled("sunday_summary"):
        logger.info("job disabled: sunday_summary")
        return
    now = now_local(settings.tz)
    bot = Bot(token=settings.telegram_bot_token)
    week = week_range_for(now)

    for profile in db.get_all_user_profiles():
        user_id = int(profile["user_id"])
        chat_id = int(profile["chat_id"])
        view = compute_status(db, user_id, now)

        categories = view.week_categories
        text = (
            "Weekly summary (Sunday)\n\n"
            f"Productive: {format_minutes_hm(view.week.productive_minutes)}\n"
            f"  Study: {format_minutes_hm(categories.get('study', 0))}\n"
            f"  Build: {format_minutes_hm(categories.get('build', 0))}\n"
            f"  Training: {format_minutes_hm(categories.get('training', 0))}\n"
            f"  Job: {format_minutes_hm(categories.get('job', 0))}\n\n"
            f"Fun spent: {format_minutes_hm(view.week.spent_minutes)}\n"
            f"Fun remaining: {format_minutes_hm(view.economy.remaining_fun_minutes)}\n\n"
            f"XP gained: {view.xp_week}\n"
            f"Streak: {view.streak_current} days\n"
            f"Deep work sessions (90+ min): {view.deep_sessions_week}"
        )
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info("sent sunday summary user_id=%s", user_id)


async def run_reminders(db: Database, settings: Settings) -> None:
    if not db.is_job_enabled("reminders"):
        logger.info("job disabled: reminders")
        return
    if not db.is_feature_enabled("reminders"):
        logger.info("feature disabled: reminders")
        return
    now = now_local(settings.tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    bot = Bot(token=settings.telegram_bot_token)

    for profile in db.get_all_user_profiles():
        user_id = int(profile["user_id"])
        chat_id = int(profile["chat_id"])
        reminders_enabled = bool(profile.get("reminders_enabled", 1))
        daily_goal = int(profile.get("daily_goal_minutes") or 60)
        quiet_hours = profile.get("quiet_hours")

        if not reminders_enabled:
            continue
        if in_quiet_hours(now, quiet_hours):
            continue

        productive_today = db.sum_minutes(user_id, "productive", start=day_start, end=now)
        has_any = db.has_productive_log_between(user_id, day_start, now)

        decision = evaluate_reminders(
            now=now,
            productive_today_minutes=productive_today,
            daily_goal_minutes=daily_goal,
            has_productive_log_today=has_any,
        )

        date_key = now.date().isoformat()
        if decision.inactivity:
            event_key = f"inactivity:{date_key}"
            if not db.was_event_sent(user_id, event_key):
                await bot.send_message(chat_id=chat_id, text="Reminder: no productive log yet today. Add one with /log.")
                db.mark_event_sent(user_id, event_key, now)
                logger.info("sent inactivity reminder user_id=%s", user_id)

        if decision.daily_goal:
            event_key = f"daily-goal:{date_key}"
            if not db.was_event_sent(user_id, event_key):
                missing = max(daily_goal - productive_today, 0)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Daily goal reminder: you are {format_minutes_hm(missing)} short of your goal.",
                )
                db.mark_event_sent(user_id, event_key, now)
                logger.info("sent daily goal reminder user_id=%s", user_id)

        # Streak risk warning: nudge if streak > 3 days and not enough today
        streak = db.get_streak(user_id, now)
        if streak.current_streak > 3 and productive_today < STREAK_MINUTES_REQUIRED:
            remaining = STREAK_MINUTES_REQUIRED - productive_today
            event_key = f"streak-risk:{date_key}"
            if not db.was_event_sent(user_id, event_key):
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"You're at {format_minutes_hm(productive_today)} today \u2014 "
                        f"{format_minutes_hm(remaining)} more to keep your "
                        f"{streak.current_streak}-day streak \U0001f525"
                    ),
                )
                db.mark_event_sent(user_id, event_key, now)
                logger.info("sent streak risk warning user_id=%s streak=%s", user_id, streak.current_streak)

        # Near-completion milestone nudges.
        total_productive = db.sum_minutes(user_id, "productive")
        next_block = ((total_productive // 600) + 1) * 600
        to_milestone = next_block - total_productive
        if 0 < to_milestone <= 120:
            event_key = f"near-milestone:{next_block}"
            if not db.was_event_sent(user_id, event_key):
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Milestone is close.\n"
                        f"Only {format_minutes_hm(to_milestone)} left to hit {next_block // 60}h all-time (+3h fun)."
                    ),
                )
                db.mark_event_sent(user_id, event_key, now)
                logger.info("sent milestone nudge user_id=%s block=%s", user_id, next_block)


async def run_daily_digest(db: Database, settings: Settings) -> None:
    if not db.is_job_enabled("daily_digest"):
        logger.info("job disabled: daily_digest")
        return
    now = now_local(settings.tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    bot = Bot(token=settings.telegram_bot_token)

    for profile in db.get_all_user_profiles():
        user_id = int(profile["user_id"])
        chat_id = int(profile["chat_id"])

        productive_today = db.sum_minutes(user_id, "productive", start=day_start, end=now)
        if productive_today == 0:
            continue

        date_key = now.date().isoformat()
        event_key = f"daily-digest:{date_key}"
        if db.was_event_sent(user_id, event_key):
            continue

        categories = db.sum_productive_by_category(user_id, start=day_start, end=now)
        cat_parts = []
        for key in ("study", "build", "training", "job"):
            mins = categories.get(key, 0)
            if mins > 0:
                cat_parts.append(f"{key.capitalize()} {format_minutes_hm(mins)}")
        cat_text = f" ({', '.join(cat_parts)})" if cat_parts else ""

        xp_today = db.sum_xp(user_id, start=day_start, end=now)
        streak = db.get_streak(user_id, now)
        view = compute_status(db, user_id, now)

        text = (
            f"Today: {format_minutes_hm(productive_today)}{cat_text} "
            f"\u00b7 +{xp_today} XP "
            f"\u00b7 \U0001f525 {streak.current_streak}d "
            f"\u00b7 Fun: {view.economy.remaining_fun_minutes}m"
        )
        await bot.send_message(chat_id=chat_id, text=text)
        db.mark_event_sent(user_id, event_key, now)
        logger.info("sent daily digest user_id=%s", user_id)


def run_job(job_name: str, db: Database, settings: Settings) -> None:
    if not db.is_job_enabled(job_name):
        logger.info("job disabled: %s", job_name)
        return
    if job_name == "sunday_summary":
        asyncio.run(run_sunday_summary(db, settings))
    elif job_name == "reminders":
        asyncio.run(run_reminders(db, settings))
    elif job_name == "daily_digest":
        asyncio.run(run_daily_digest(db, settings))
    else:
        raise SystemExit(
            "Unknown job "
            f"'{job_name}'. Expected one of: sunday_summary, reminders, daily_digest"
        )
