from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from tg_time_logger.db import Database, Quest
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES
from tg_time_logger.time_utils import week_range_for


@dataclass(frozen=True)
class QuestProgress:
    quest: Quest
    current: int
    target: int
    unit: str
    complete: bool


QUEST_TEMPLATES: list[dict[str, object]] = [
    {
        "title": "Scholar's Sprint",
        "description": "Log focused study time in a single day.",
        "quest_type": "daily",
        "difficulty": "easy",
        "reward": 90,
        "condition": {"type": "category_hours", "category": "study", "target": 3},
    },
    {
        "title": "Builder's Week",
        "description": "Push meaningful hours this week.",
        "quest_type": "weekly",
        "difficulty": "medium",
        "reward": 180,
        "condition": {"type": "weekly_hours", "target": 24},
    },
    {
        "title": "Steady Flame",
        "description": "Hold your streak and stay consistent.",
        "quest_type": "streak",
        "difficulty": "medium",
        "reward": 160,
        "condition": {"type": "streak_days", "target": 7},
    },
]


def ensure_weekly_quests(db: Database, user_id: int, now: datetime) -> None:
    if db.list_active_quests(user_id, now):
        return

    week = week_range_for(now)
    expires_at = week.end - timedelta(seconds=1)
    for tpl in QUEST_TEMPLATES:
        db.insert_quest(
            user_id=user_id,
            title=str(tpl["title"]),
            description=str(tpl["description"]),
            quest_type=str(tpl["quest_type"]),
            difficulty=str(tpl["difficulty"]),
            reward_fun_minutes=int(tpl["reward"]),
            condition=dict(tpl["condition"]),
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
        best = max(totals.values(), default=0)
        return QuestProgress(quest, best, target_minutes, "min", best >= target_minutes)

    if ctype == "weekly_hours":
        target_minutes = int(condition.get("target", 0) * 60)
        week = week_range_for(now)
        current = db.sum_minutes(user_id, "productive", start=week.start, end=now)
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
