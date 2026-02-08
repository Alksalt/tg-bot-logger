from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time

from telegram import Bot

from tg_time_logger.db import Database
from tg_time_logger.economy import format_minutes_hm
from tg_time_logger.messages import week_message
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import in_quiet_hours, now_local, week_range_for, week_start_date

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


async def run_sunday_summary(db: Database, token: str, tz_name: str) -> None:
    now = now_local(tz_name)
    bot = Bot(token=token)
    profiles = db.get_all_user_profiles()
    for profile in profiles:
        user_id = int(profile["user_id"])
        chat_id = int(profile["chat_id"])
        view = compute_status(db, user_id, now)
        by_category = db.sum_productive_by_category(user_id, start=week_range_for(now).start, end=now)
        plan = db.get_plan_target(user_id, week_start_date(now))
        text = "Weekly summary (Sunday)\n" + week_message(view, plan, by_category)
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info("sent sunday summary user_id=%s", user_id)


async def run_reminders(db: Database, token: str, tz_name: str) -> None:
    now = now_local(tz_name)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    bot = Bot(token=token)

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


async def run_midweek(db: Database, token: str, tz_name: str) -> None:
    now = now_local(tz_name)
    bot = Bot(token=token)
    week = week_range_for(now)

    for profile in db.get_all_user_profiles():
        user_id = int(profile["user_id"])
        chat_id = int(profile["chat_id"])
        quiet_hours = profile.get("quiet_hours")

        if in_quiet_hours(now, quiet_hours):
            continue

        event_key = f"midweek:{week.start.date().isoformat()}"
        if db.was_event_sent(user_id, event_key):
            continue

        by_category = db.sum_productive_by_category(user_id, start=week.start, end=now)
        plan = db.get_plan_target(user_id, week_start_date(now))
        if not plan:
            continue

        lines = ["Midweek progress (Wednesday 19:00)"]
        for category in ("work", "study", "learn"):
            done = by_category.get(category, 0)
            target = getattr(plan, f"{category}_minutes")
            remaining = max(target - done, 0)
            lines.append(
                f"{category}: done {format_minutes_hm(done)} / target {format_minutes_hm(target)} / remaining {format_minutes_hm(remaining)}"
            )
        await bot.send_message(chat_id=chat_id, text="\n".join(lines))
        db.mark_event_sent(user_id, event_key, now)
        logger.info("sent midweek message user_id=%s", user_id)


def run_job(job_name: str, db: Database, token: str, tz_name: str) -> None:
    if job_name == "sunday_summary":
        asyncio.run(run_sunday_summary(db, token, tz_name))
    elif job_name == "reminders":
        asyncio.run(run_reminders(db, token, tz_name))
    elif job_name == "midweek":
        asyncio.run(run_midweek(db, token, tz_name))
    else:
        raise SystemExit(f"Unknown job '{job_name}'. Expected one of: sunday_summary, reminders, midweek")
