from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from tg_time_logger.db import Database, Quest
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, level_from_xp
from tg_time_logger.llm_router import LlmRoute, call_text
from tg_time_logger.time_utils import week_range_for


@dataclass(frozen=True)
class QuestProgress:
    quest: Quest
    current: int
    target: int
    unit: str
    complete: bool


REWARD_RANGES = {
    "easy": (60, 120),
    "medium": (120, 240),
    "hard": (240, 400),
}

ALLOWED_CONDITION_TYPES = {
    "daily_hours",
    "weekly_hours",
    "no_fun_day",
    "streak_days",
    "category_hours",
    "consecutive_days",
}

EASY_QUESTS: list[dict[str, Any]] = [
    {"title": "Study Spark", "description": "Log 2h study in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "study", "target": 2}},
    {"title": "Builder Burst", "description": "Build for 2h in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "build", "target": 2}},
    {"title": "Training Tap", "description": "Train 90m in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "training", "target": 2}},
    {"title": "Job Anchor", "description": "Log 3h job time in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "job", "target": 3}},
    {"title": "Mini Marathon", "description": "Hit 10h productive this week.", "quest_type": "weekly", "condition": {"type": "weekly_hours", "target": 10}},
    {"title": "No-Snack Day", "description": "Spend zero fun for 1 day.", "quest_type": "restraint", "condition": {"type": "no_fun_day", "days": 1}},
    {"title": "Warm Streak", "description": "Reach a 3-day streak.", "quest_type": "streak", "condition": {"type": "streak_days", "target": 3}},
    {"title": "Daily Focus", "description": "Log 4h in one day.", "quest_type": "daily", "condition": {"type": "daily_hours", "target": 4}},
    {"title": "Two-Day Chain", "description": "2 days with at least 3h.", "quest_type": "streak", "condition": {"type": "consecutive_days", "min_hours": 3, "target": 2}},
    {"title": "Balanced Shift", "description": "Log 1h study and 1h build in a day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "build", "target": 1}},
]

MEDIUM_QUESTS: list[dict[str, Any]] = [
    {"title": "Scholar's Drive", "description": "Log 4h study in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "study", "target": 4}},
    {"title": "Builder's Push", "description": "Log 5h build in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "build", "target": 5}},
    {"title": "Training Block", "description": "Log 4h training in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "training", "target": 4}},
    {"title": "Workhorse", "description": "Log 6h job in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "job", "target": 6}},
    {"title": "Week Commander", "description": "Reach 20h this week.", "quest_type": "weekly", "condition": {"type": "weekly_hours", "target": 20}},
    {"title": "Iron Restraint", "description": "No fun spending for 2 days.", "quest_type": "restraint", "condition": {"type": "no_fun_day", "days": 2}},
    {"title": "Streak Seven", "description": "Reach a 7-day streak.", "quest_type": "streak", "condition": {"type": "streak_days", "target": 7}},
    {"title": "6h Day", "description": "Hit 6h in a single day.", "quest_type": "daily", "condition": {"type": "daily_hours", "target": 6}},
    {"title": "Three-Day Chain", "description": "3 days with at least 4h.", "quest_type": "streak", "condition": {"type": "consecutive_days", "min_hours": 4, "target": 3}},
    {"title": "Study Sprint Week", "description": "Total 8h study this week.", "quest_type": "weekly", "condition": {"type": "weekly_hours", "target": 24}},
]

HARD_QUESTS: list[dict[str, Any]] = [
    {"title": "Master Scholar", "description": "Log 6h study in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "study", "target": 6}},
    {"title": "Builder Marathon", "description": "Log 8h build in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "build", "target": 8}},
    {"title": "Training Gauntlet", "description": "Log 6h training in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "training", "target": 6}},
    {"title": "Job Titan", "description": "Log 9h job in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "job", "target": 9}},
    {"title": "Forty-Hour Forge", "description": "Reach 40h this week.", "quest_type": "weekly", "condition": {"type": "weekly_hours", "target": 40}},
    {"title": "No-Fun Discipline", "description": "No fun spending for 3 days.", "quest_type": "restraint", "condition": {"type": "no_fun_day", "days": 3}},
    {"title": "Streak Ten", "description": "Reach a 10-day streak.", "quest_type": "streak", "condition": {"type": "streak_days", "target": 10}},
    {"title": "8h Deep Day", "description": "Hit 8h in a single day.", "quest_type": "daily", "condition": {"type": "daily_hours", "target": 8}},
    {"title": "Four-Day Chain", "description": "4 days with at least 5h.", "quest_type": "streak", "condition": {"type": "consecutive_days", "min_hours": 5, "target": 4}},
    {"title": "Category Specialist", "description": "7h in top category in one day.", "quest_type": "daily", "condition": {"type": "category_hours", "category": "build", "target": 7}},
]

QUEST_POOLS: dict[str, list[dict[str, Any]]] = {
    "easy": EASY_QUESTS,
    "medium": MEDIUM_QUESTS,
    "hard": HARD_QUESTS,
}


def _reward_for_difficulty(diff: str, rng: random.Random) -> int:
    lo, hi = REWARD_RANGES.get(diff, REWARD_RANGES["medium"])
    return rng.randint(lo, hi)


def _weekly_stats(db: Database, user_id: int, week_start: datetime, week_end: datetime) -> dict[str, Any]:
    total_minutes = db.sum_minutes(user_id, "productive", start=week_start, end=week_end)
    avg_daily = (total_minutes / 60) / 7 if total_minutes > 0 else 0.0
    categories = db.sum_productive_by_category(user_id, start=week_start, end=week_end)
    top_category = max(categories, key=lambda k: categories[k]) if categories else "build"
    top_hours = categories.get(top_category, 0) / 60
    streak = db.get_streak(user_id, week_end).current_streak
    level = level_from_xp(db.sum_xp(user_id))
    fun_spent = db.sum_minutes(user_id, "spend", start=week_start, end=week_end)
    return {
        "weekly_hours": total_minutes / 60,
        "avg_daily": avg_daily,
        "top_category": top_category,
        "top_hours": top_hours,
        "streak": streak,
        "level": level,
        "fun_spent": fun_spent,
    }


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _validate_llm_quest(payload: dict[str, Any], stats: dict[str, Any], rng: random.Random) -> dict[str, Any] | None:
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    difficulty = str(payload.get("difficulty", "medium")).lower()
    condition = payload.get("condition")
    quest_type = str(payload.get("quest_type", "weekly")).lower()

    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    if not title or not description or not isinstance(condition, dict):
        return None

    ctype = condition.get("type")
    if ctype not in ALLOWED_CONDITION_TYPES:
        return None

    avg_daily = max(float(stats.get("avg_daily", 0.0)), 1.0)

    normalized = dict(condition)
    if ctype == "daily_hours":
        normalized["target"] = _clamp_int(int(condition.get("target", 4)), 2, int(avg_daily * 2))
    elif ctype == "weekly_hours":
        normalized["target"] = _clamp_int(int(condition.get("target", 20)), 8, int(avg_daily * 7 * 2))
    elif ctype == "no_fun_day":
        normalized["days"] = _clamp_int(int(condition.get("days", 1)), 1, 3)
    elif ctype == "streak_days":
        normalized["target"] = _clamp_int(int(condition.get("target", 7)), 3, max(7, int(stats.get("streak", 0)) + 7))
    elif ctype == "category_hours":
        cat = str(condition.get("category", stats.get("top_category", "build"))).lower()
        normalized["category"] = cat if cat in PRODUCTIVE_CATEGORIES else "build"
        normalized["target"] = _clamp_int(int(condition.get("target", 4)), 2, int(avg_daily * 2))
    elif ctype == "consecutive_days":
        normalized["min_hours"] = _clamp_int(int(condition.get("min_hours", 4)), 2, 8)
        normalized["target"] = _clamp_int(int(condition.get("target", 3)), 2, 5)

    return {
        "title": title,
        "description": description,
        "quest_type": quest_type,
        "difficulty": difficulty,
        "reward": _reward_for_difficulty(difficulty, rng),
        "condition": normalized,
    }


def _generate_llm_bonus_quest(
    db: Database,
    user_id: int,
    now: datetime,
    route: LlmRoute,
    rng: random.Random,
) -> dict[str, Any] | None:
    if not route.api_key:
        return None

    week = week_range_for(now)
    prev_start = week.start - timedelta(days=7)
    prev_end = week.start
    stats = _weekly_stats(db, user_id, prev_start, prev_end)

    prompt = (
        "You are a quest master for a productivity game. Generate exactly one quest as JSON object.\n\n"
        "Player stats (last 7 days):\n"
        f"- Total productive hours: {stats['weekly_hours']:.2f}\n"
        f"- Daily average: {stats['avg_daily']:.2f}h\n"
        f"- Top category: {stats['top_category']} ({stats['top_hours']:.2f}h)\n"
        f"- Current streak: {stats['streak']} days\n"
        f"- Current level: {stats['level']}\n"
        f"- Fun minutes spent: {stats['fun_spent']}\n\n"
        "Available quest condition types: daily_hours, weekly_hours, no_fun_day, streak_days, category_hours, consecutive_days.\n"
        "Keep target within realistic range (at most 2x last-week average).\n"
        "Return JSON only with keys: title, description, quest_type, difficulty, condition."
    )

    content = call_text(route, prompt, max_tokens=220)
    if not content:
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    return _validate_llm_quest(payload, stats, rng)


def ensure_weekly_quests(
    db: Database,
    user_id: int,
    now: datetime,
    llm_enabled: bool = False,
    llm_route: LlmRoute | None = None,
) -> None:
    if db.list_active_quests(user_id, now):
        return

    week = week_range_for(now)
    expires_at = week.end - timedelta(seconds=1)

    rng = random.Random(f"{user_id}:{week.start.date().isoformat()}")
    recent_titles = db.list_recent_quest_titles(user_id, since=week.start - timedelta(days=14))

    for difficulty in ("easy", "medium", "hard"):
        pool = QUEST_POOLS[difficulty]
        filtered = [q for q in pool if q["title"] not in recent_titles]
        pick_pool = filtered if filtered else pool
        tpl = rng.choice(pick_pool)
        db.insert_quest(
            user_id=user_id,
            title=str(tpl["title"]),
            description=str(tpl["description"]),
            quest_type=str(tpl["quest_type"]),
            difficulty=difficulty,
            reward_fun_minutes=_reward_for_difficulty(difficulty, rng),
            condition=dict(tpl["condition"]),
            expires_at=expires_at,
            created_at=now,
        )

    if llm_enabled and llm_route:
        bonus = _generate_llm_bonus_quest(db, user_id, now, llm_route, rng)
        if bonus and bonus["title"] not in recent_titles:
            db.insert_quest(
                user_id=user_id,
                title=str(bonus["title"]),
                description=str(bonus["description"]),
                quest_type=str(bonus["quest_type"]),
                difficulty=str(bonus["difficulty"]),
                reward_fun_minutes=int(bonus["reward"]),
                condition=dict(bonus["condition"]),
                expires_at=expires_at,
                created_at=now,
            )


def evaluate_quest_progress(db: Database, user_id: int, quest: Quest, now: datetime) -> QuestProgress:
    condition = json.loads(quest.condition_json)
    ctype = condition.get("type")

    if ctype == "daily_hours":
        target_minutes = int(condition.get("target", 0) * 60)
        week = week_range_for(now)
        totals = db.daily_totals(user_id, "productive", week.start.date(), week.end.date())
        # Subtract job minutes from totals
        job_totals = db.daily_totals(user_id, "productive", week.start.date(), week.end.date(), category="job")
        for day, m in job_totals.items():
            if day in totals:
                totals[day] = max(0, totals[day] - m)

        best = max(totals.values(), default=0)
        return QuestProgress(quest, best, target_minutes, "min", best >= target_minutes)

    if ctype == "weekly_hours":
        target_minutes = int(condition.get("target", 0) * 60)
        week = week_range_for(now)
        current = db.sum_minutes(user_id, "productive", start=week.start, end=now)
        # Exclude job minutes
        job_minutes = db.sum_minutes(user_id, "productive", start=week.start, end=now, category="job")
        current = max(0, current - job_minutes)
        return QuestProgress(quest, current, target_minutes, "min", current >= target_minutes)

    if ctype == "no_fun_day":
        days = int(condition.get("days", 1))
        start = now.date() - timedelta(days=days - 1)
        totals = db.daily_totals(user_id, "spend", start, now.date() + timedelta(days=1))
        passed = all(totals.get(start + timedelta(days=i), 0) == 0 for i in range(days))
        return QuestProgress(quest, days if passed else 0, days, "days", passed)

    if ctype == "streak_days":
        target = int(condition.get("target", 0))
        streak = db.get_streak(user_id, now)
        return QuestProgress(quest, streak.current_streak, target, "days", streak.current_streak >= target)

    if ctype == "category_hours":
        category = str(condition.get("category", "build"))
        if category not in PRODUCTIVE_CATEGORIES:
            category = "build"
        target_minutes = int(condition.get("target", 0) * 60)
        week = week_range_for(now)
        totals = db.daily_totals(user_id, "productive", week.start.date(), week.end.date(), category=category)
        best = max(totals.values(), default=0)
        return QuestProgress(quest, best, target_minutes, "min", best >= target_minutes)

    if ctype == "consecutive_days":
        min_hours = int(condition.get("min_hours", 1))
        target_days = int(condition.get("target", 1))
        min_minutes = min_hours * 60
        week = week_range_for(now)
        totals = db.daily_totals(user_id, "productive", week.start.date(), week.end.date())
        job_totals = db.daily_totals(user_id, "productive", week.start.date(), week.end.date(), category="job")
        for day, m in job_totals.items():
            if day in totals:
                totals[day] = max(0, totals[day] - m)

        longest = 0
        running = 0
        day = week.start.date()
        while day < week.end.date():
            if totals.get(day, 0) >= min_minutes:
                running += 1
                longest = max(longest, running)
            else:
                running = 0
            day += timedelta(days=1)
        return QuestProgress(quest, longest, target_days, "days", longest >= target_days)

    return QuestProgress(quest, 0, 1, "", False)


def check_quests_for_user(db: Database, user_id: int, now: datetime) -> list[QuestProgress]:
    completions: list[QuestProgress] = []
    for quest in db.list_active_quests(user_id, now):
        if quest.expires_at < now:
            db.update_quest_status(quest.id, "expired")
            continue

        progress = evaluate_quest_progress(db, user_id, quest, now)
        if progress.complete:
            db.update_quest_status(quest.id, "completed", now)
            completions.append(progress)
    return completions
