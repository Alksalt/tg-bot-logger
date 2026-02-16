from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from telegram import Bot

from tg_time_logger.config import Settings
from tg_time_logger.db import Database
from tg_time_logger.gamification import format_minutes_hm, spin_wheel
from tg_time_logger.llm_messages import LlmContext, weekly_summary_message
from tg_time_logger.llm_router import LlmRoute
from tg_time_logger.notion_backup import run_notion_backup_job
from tg_time_logger.quests import evaluate_quest_progress, sync_quests_for_user
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import in_quiet_hours, now_local, week_range_for, week_start_date

logger = logging.getLogger(__name__)
SUNDAY_FUND_ALLOWED = {50, 60, 70}


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


def sunday_fund_deposit_amount(available_fun_minutes: int, percent: int) -> int:
    if percent not in SUNDAY_FUND_ALLOWED:
        return 0
    if available_fun_minutes <= 0:
        return 0
    return max(0, (available_fun_minutes * percent) // 100)


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
        sync_quests_for_user(db, user_id, now)
        view = compute_status(db, user_id, now)

        plan = db.get_plan_target(user_id, week.start.date())
        target = plan.total_target_minutes if plan else 0
        met = target > 0 and view.week.productive_minutes >= target

        wheel_msg = ""
        if met and not db.has_wheel_spin(user_id, week.start.date()):
            result_text, bonus = spin_wheel()
            if db.add_wheel_spin(user_id, week.start.date(), bonus, now):
                wheel_msg = (
                    "\n\n🎡 Weekly Wheel Spin!\n"
                    "You hit your target this week — time to spin!\n\n"
                    f"{result_text} +{bonus} fun minutes!"
                )

        sunday_percent = int(profile.get("sunday_fund_percent") or 0)
        auto_msg = ""
        auto_key = f"sunday-fund:{week.start.date().isoformat()}"
        if sunday_percent in SUNDAY_FUND_ALLOWED and not db.was_event_sent(user_id, auto_key):
            available = max(view.economy.remaining_fun_minutes, 0)
            amount = sunday_fund_deposit_amount(available, sunday_percent)
            if amount > 0:
                db.ensure_fund_goal(user_id, now)
                goal = db.deposit_to_savings(user_id, amount, now)
                if goal:
                    auto_msg = (
                        f"\n\n🏦 Sunday auto-transfer: moved {amount}m ({sunday_percent}%) "
                        f"to '{goal.name}'."
                    )
            db.mark_event_sent(user_id, auto_key, now)

        categories = view.week_categories
        facts = (
            f"- Total productive: {view.week.productive_minutes / 60:.2f}h "
            f"(study: {categories['study'] / 60:.2f}h, build: {categories['build'] / 60:.2f}h, "
            f"training: {categories['training'] / 60:.2f}h, job: {categories['job'] / 60:.2f}h)\n"
            f"- Fun spent: {view.week.spent_minutes} min\n"
            f"- Plan target: {target / 60:.2f}h — {'MET ✅' if met else 'MISSED ❌'} ({view.week.productive_minutes / 60:.2f}h)\n"
            f"- XP gained: {view.xp_week}\n"
            f"- Streak: {view.streak_current} days\n"
            f"- Quests active: {view.active_quests}\n"
            f"- Deep work sessions (90+ min): {view.deep_sessions_week}"
        )

        ctx = LlmContext(
            enabled=settings.llm_enabled and db.is_feature_enabled("llm"),
            route=LlmRoute(
                provider=settings.llm_provider,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
            ),
        )
        summary = weekly_summary_message(ctx, facts)

        text = (
            "Weekly summary (Sunday)\n"
            f"Productive: {format_minutes_hm(view.week.productive_minutes)}\n"
            f"Spent: {format_minutes_hm(view.week.spent_minutes)}\n"
            f"Fun remaining: {format_minutes_hm(view.economy.remaining_fun_minutes)}\n\n"
            f"{summary}"
            f"{wheel_msg}"
            f"{auto_msg}"
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
        sync_quests_for_user(db, user_id, now)
        reminders_enabled = bool(profile.get("reminders_enabled", 1))
        daily_goal = int(profile.get("daily_goal_minutes") or 60)
        quiet_hours = profile.get("quiet_hours")

        # Auto-save deposit once per day.
        auto_save = int(profile.get("auto_save_minutes") or 0)
        auto_event = f"autosave:{now.date().isoformat()}"
        if auto_save > 0 and not db.was_event_sent(user_id, auto_event):
            status = compute_status(db, user_id, now)
            available = max(status.economy.remaining_fun_minutes, 0)
            amount = min(auto_save, available)
            if amount > 0:
                db.ensure_fund_goal(user_id, now)
                goal = db.deposit_to_savings(user_id, amount, now)
                if goal:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"🏦 Auto-saved {amount} fun minutes into '{goal.name}'.",
                    )
            db.mark_event_sent(user_id, auto_event, now)

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

        # Near-completion nudges (once per milestone/quest).
        total_productive = db.sum_minutes(user_id, "productive")
        next_block = ((total_productive // 600) + 1) * 600
        to_milestone = next_block - total_productive
        if 0 < to_milestone <= 120:
            event_key = f"near-milestone:{next_block}"
            if not db.was_event_sent(user_id, event_key):
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⏳ Milestone is close.\n"
                        f"Only {format_minutes_hm(to_milestone)} left to hit {next_block // 60}h all-time (+3h fun)."
                    ),
                )
                db.mark_event_sent(user_id, event_key, now)
                logger.info("sent milestone nudge user_id=%s block=%s", user_id, next_block)

        near_sent = 0
        for quest in db.list_active_quests(user_id, now):
            if near_sent >= 2:
                break
            progress = evaluate_quest_progress(db, user_id, quest, now)
            if progress.complete or progress.target <= 0:
                continue
            remaining = max(progress.target - progress.current, 0)
            is_near = (
                (progress.unit == "min" and 0 < remaining <= 120)
                or (progress.unit == "days" and remaining == 1)
            )
            if not is_near:
                continue
            event_key = f"near-quest:{quest.id}"
            if db.was_event_sent(user_id, event_key):
                continue
            remaining_txt = format_minutes_hm(remaining) if progress.unit == "min" else f"{remaining} day"
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎯 Quest almost done: {quest.title}\n"
                    f"Only {remaining_txt} left for +{quest.reward_fun_minutes} fun minutes."
                ),
            )
            db.mark_event_sent(user_id, event_key, now)
            near_sent += 1


async def run_midweek(db: Database, settings: Settings) -> None:
    if not db.is_job_enabled("midweek"):
        logger.info("job disabled: midweek")
        return
    now = now_local(settings.tz)
    bot = Bot(token=settings.telegram_bot_token)
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

        plan = db.get_plan_target(user_id, week_start_date(now))
        if not plan:
            continue

        target = plan.total_target_minutes
        done = db.sum_minutes(user_id, "productive", start=week.start, end=now)
        remaining = max(target - done, 0)
        cats = db.sum_productive_by_category(user_id, start=week.start, end=now)

        text = (
            "Midweek progress (Wednesday 19:00)\n"
            f"Total: {format_minutes_hm(done)} / {format_minutes_hm(target)} (remaining {format_minutes_hm(remaining)})\n"
            f"Study {format_minutes_hm(cats['study'])}, Build {format_minutes_hm(cats['build'])}, "
            f"Training {format_minutes_hm(cats['training'])}, Job {format_minutes_hm(cats['job'])}"
        )
        await bot.send_message(chat_id=chat_id, text=text)
        db.mark_event_sent(user_id, event_key, now)
        logger.info("sent midweek message user_id=%s", user_id)


def run_notion_backup(db: Database, settings: Settings) -> None:
    if not db.is_job_enabled("notion_backup"):
        logger.info("job disabled: notion_backup")
        return
    if not db.is_feature_enabled("notion_backup"):
        logger.info("feature disabled: notion_backup")
        return
    now = now_local(settings.tz)
    records = run_notion_backup_job(db, settings, now)
    logger.info("notion backup scaffold completed: users=%s", len(records))


def run_job(job_name: str, db: Database, settings: Settings) -> None:
    if not db.is_job_enabled(job_name):
        logger.info("job disabled: %s", job_name)
        return
    if job_name == "sunday_summary":
        asyncio.run(run_sunday_summary(db, settings))
    elif job_name == "reminders":
        asyncio.run(run_reminders(db, settings))
    elif job_name == "midweek":
        asyncio.run(run_midweek(db, settings))
    elif job_name == "notion_backup":
        run_notion_backup(db, settings)
    else:
        raise SystemExit(
            "Unknown job "
            f"'{job_name}'. Expected one of: sunday_summary, reminders, midweek, notion_backup"
        )
