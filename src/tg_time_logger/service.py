from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from tg_time_logger.db import Database, Entry, LevelUpEvent, Streak
from tg_time_logger.gamification import (
    EconomyBreakdown,
    PRODUCTIVE_CATEGORIES,
    build_economy,
    deep_work_multiplier,
    fun_from_minutes,
    level_from_xp,
    level_progress,
    streak_multiplier,
)
from datetime import timedelta
from tg_time_logger.time_utils import week_range_for


@dataclass(frozen=True)
class PeriodTotals:
    productive_minutes: int
    spent_minutes: int


@dataclass(frozen=True)
class StatusView:
    today: PeriodTotals
    week: PeriodTotals
    all_time: PeriodTotals
    week_categories: dict[str, int]
    all_time_categories: dict[str, int]
    xp_total: int
    xp_week: int
    level: int
    title: str
    xp_current_level: int
    xp_next_level: int
    xp_progress_ratio: float
    xp_remaining_to_next: int
    streak_current: int
    streak_longest: int
    streak_multiplier: float
    deep_sessions_week: int
    active_quests: int
    week_plan_done_minutes: int
    week_plan_target_minutes: int
    week_plan_remaining_minutes: int
    fun_earned_this_week: int
    economy: EconomyBreakdown


@dataclass(frozen=True)
class ProductiveLogOutcome:
    entry: Entry
    streak: Streak
    streak_mult: float
    deep_mult: float
    xp_earned: int
    level_ups: list[LevelUpEvent]
    top_week_category: str


def normalize_category(raw: str | None) -> str:
    if raw in PRODUCTIVE_CATEGORIES:
        return str(raw)
    return "build"


def _check_level_ups(db: Database, user_id: int, now: datetime) -> list[LevelUpEvent]:
    tuning = db.get_economy_tuning()
    total_xp = db.sum_xp(user_id)
    current_level = level_from_xp(total_xp, tuning=tuning)
    max_recorded = db.max_level_event_level(user_id)
    created: list[LevelUpEvent] = []
    for lvl in range(max_recorded + 1, current_level + 1):
        if lvl < 2:
            continue
        event = db.add_level_up_event(user_id, lvl, now, tuning=tuning)
        if event:
            created.append(event)
    return created


def add_productive_entry(
    db: Database,
    user_id: int,
    minutes: int,
    category: str,
    note: str | None,
    created_at: datetime,
    source: str,
    timer_mode: bool = False,
) -> ProductiveLogOutcome:
    tuning = db.get_economy_tuning()
    economy_enabled = db.is_feature_enabled("economy")
    normalized = normalize_category(category)
    deep_mult = deep_work_multiplier(minutes) if timer_mode else 1.0
    fun_earned = fun_from_minutes(normalized, minutes, tuning=tuning) if economy_enabled else 0

    entry = db.add_entry(
        user_id=user_id,
        kind="productive",
        category=normalized,
        minutes=minutes,
        note=note,
        created_at=created_at,
        source=source,
        xp_earned=minutes if economy_enabled else 0,
        fun_earned=fun_earned,
        deep_work_multiplier=deep_mult,
    )

    if normalized == "job":
        streak = db.get_streak(user_id, created_at)
    else:
        streak = db.refresh_streak(user_id, created_at)

    s_mult = streak_multiplier(streak.current_streak)
    if not economy_enabled or normalized == "job":
        final_xp = 0
    else:
        final_xp = math.floor(minutes * s_mult * deep_mult)
    if final_xp != entry.xp_earned:
        db.update_entry_xp(entry.id, final_xp)
        entry = Entry(
            id=entry.id,
            user_id=entry.user_id,
            kind=entry.kind,
            category=entry.category,
            minutes=entry.minutes,
            xp_earned=final_xp,
            fun_earned=entry.fun_earned,
            deep_work_multiplier=entry.deep_work_multiplier,
            note=entry.note,
            created_at=entry.created_at,
            deleted_at=entry.deleted_at,
            source=entry.source,
        )

    level_ups = _check_level_ups(db, user_id, created_at)
    week = week_range_for(created_at)
    top_category = db.top_category_for_week(user_id, week.start, created_at)

    return ProductiveLogOutcome(
        entry=entry,
        streak=streak,
        streak_mult=s_mult,
        deep_mult=deep_mult,
        xp_earned=entry.xp_earned,
        level_ups=level_ups,
        top_week_category=top_category,
    )


def compute_status(db: Database, user_id: int, now: datetime) -> StatusView:
    tuning = db.get_economy_tuning()
    week = week_range_for(now)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    today_productive = db.sum_minutes(user_id, "productive", start=day_start, end=day_end)
    today_spent = db.sum_minutes(user_id, "spend", start=day_start, end=day_end)

    week_productive = db.sum_minutes(user_id, "productive", start=week.start, end=week.end)
    week_spent = db.sum_minutes(user_id, "spend", start=week.start, end=week.end)

    all_productive = db.sum_minutes(user_id, "productive")
    all_spent = db.sum_minutes(user_id, "spend")

    week_categories = db.sum_productive_by_category(user_id, start=week.start, end=week.end)
    all_categories = db.sum_productive_by_category(user_id)

    xp_total = db.sum_xp(user_id)
    xp_week = db.sum_xp(user_id, start=week.start, end=week.end)
    lp = level_progress(xp_total, tuning=tuning)

    streak = db.get_streak(user_id, now)
    streak_mult = streak_multiplier(streak.current_streak)
    plan = db.get_plan_target(user_id, week.start.date())
    plan_target = int(plan.total_target_minutes) if plan else 0
    # Exclude job minutes from plan progress
    week_job_minutes = week_categories.get("job", 0)
    plan_done = max(0, int(week_productive) - week_job_minutes)
    plan_remaining = max(plan_target - plan_done, 0)

    base_fun = db.sum_fun_earned_entries(user_id)
    # Fun earned this week
    fun_earned_this_week = db.sum_fun_earned_entries(user_id, start=week.start, end=week.end)
    level_bonus = db.sum_level_bonus(user_id)
    quest_bonus = db.sum_completed_quest_rewards(user_id)
    wheel_bonus = db.sum_wheel_bonus(user_id)
    saved = db.sum_saved_locked(user_id)

    milestone_productive = all_productive - all_categories.get("job", 0)

    economy = build_economy(
        base_fun_minutes=base_fun,
        productive_minutes=milestone_productive,
        level_bonus_minutes=level_bonus,
        quest_bonus_minutes=quest_bonus,
        wheel_bonus_minutes=wheel_bonus,
        spent_fun_minutes=all_spent,
        saved_fun_minutes=saved,
        tuning=tuning,
    )

    return StatusView(
        today=PeriodTotals(today_productive, today_spent),
        week=PeriodTotals(week_productive, week_spent),
        all_time=PeriodTotals(all_productive, all_spent),
        week_categories=week_categories,
        all_time_categories=all_categories,
        xp_total=xp_total,
        xp_week=xp_week,
        level=lp.level,
        title=lp.title,
        xp_current_level=lp.current_level_xp,
        xp_next_level=lp.next_level_xp,
        xp_progress_ratio=lp.progress_ratio,
        xp_remaining_to_next=lp.remaining_to_next,
        streak_current=streak.current_streak,
        streak_longest=streak.longest_streak,
        streak_multiplier=streak_mult,
        deep_sessions_week=db.count_deep_sessions(user_id, week.start, week.end),
        active_quests=len(db.list_active_quests(user_id, now)),
        week_plan_done_minutes=plan_done,
        week_plan_target_minutes=plan_target,
        week_plan_remaining_minutes=plan_remaining,
        fun_earned_this_week=fun_earned_this_week,
        economy=economy,
    )
