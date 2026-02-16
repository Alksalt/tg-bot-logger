from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from tg_time_logger.db import Database, Quest
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, level_from_xp


@dataclass(frozen=True)
class QuestProgress:
    quest: Quest
    current: int
    target: int
    unit: str
    complete: bool


@dataclass(frozen=True)
class QuestSyncResult:
    completed: list[QuestProgress]
    failed: list[Quest]
    penalty_minutes_applied: int


QUEST_ALLOWED_DURATIONS = (3, 5, 7, 14, 21)

QUEST_DIFFICULTY_RULES: dict[str, dict[str, Any]] = {
    "easy": {
        "min_minutes_7d": 300,
        "reward_7d": (30, 45),
    },
    "medium": {
        "min_minutes_7d": 720,
        "reward_7d": (60, 90),
    },
    "hard": {
        "min_minutes_7d": 1200,
        "reward_7d": (120, 180),
    },
}

# Kept broad for backward compatibility with old quests.
ALLOWED_CONDITION_TYPES = {
    "total_minutes",
    "daily_hours",
    "weekly_hours",
    "no_fun_day",
    "streak_days",
    "category_hours",
    "consecutive_days",
}


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _normalize_duration_days(value: int | None) -> int:
    if value in QUEST_ALLOWED_DURATIONS:
        return int(value)
    return 7


def _difficulty_rule(difficulty: str) -> dict[str, Any]:
    return QUEST_DIFFICULTY_RULES.get(difficulty, QUEST_DIFFICULTY_RULES["medium"])


def _scale_for_duration(value_7d: int, duration_days: int) -> int:
    return max(1, int(math.ceil((value_7d * duration_days) / 7)))


def quest_min_target_minutes(difficulty: str, duration_days: int) -> int:
    d = difficulty if difficulty in QUEST_DIFFICULTY_RULES else "medium"
    dur = _normalize_duration_days(duration_days)
    base = int(_difficulty_rule(d)["min_minutes_7d"])
    return _scale_for_duration(base, dur)


def quest_reward_bounds(difficulty: str, duration_days: int) -> tuple[int, int]:
    d = difficulty if difficulty in QUEST_DIFFICULTY_RULES else "medium"
    dur = _normalize_duration_days(duration_days)
    lo7, hi7 = _difficulty_rule(d)["reward_7d"]
    lo = _scale_for_duration(int(lo7), dur)
    hi = _scale_for_duration(int(hi7), dur)
    return lo, max(lo, hi)


def _weekly_stats(db: Database, user_id: int, week_start: datetime, week_end: datetime) -> dict[str, Any]:
    total_minutes = db.sum_minutes(user_id, "productive", start=week_start, end=week_end)
    job_minutes = db.sum_minutes(user_id, "productive", start=week_start, end=week_end, category="job")
    focused_total = max(0, total_minutes - job_minutes)

    avg_daily = (focused_total / 60) / max(1, (week_end.date() - week_start.date()).days)
    categories = db.sum_productive_by_category(user_id, start=week_start, end=week_end)
    top_category = max(categories, key=lambda k: categories[k]) if categories else "build"
    top_hours = categories.get(top_category, 0) / 60
    streak = db.get_streak(user_id, week_end).current_streak
    level = level_from_xp(db.sum_xp(user_id))
    fun_spent = db.sum_minutes(user_id, "spend", start=week_start, end=week_end)
    build_share = (categories.get("build", 0) / focused_total) if focused_total > 0 else 0.0
    return {
        "weekly_hours": focused_total / 60,
        "avg_daily": avg_daily,
        "top_category": top_category,
        "top_hours": top_hours,
        "streak": streak,
        "level": level,
        "fun_spent": fun_spent,
        "build_share": build_share,
    }


def _normalize_condition(
    payload_condition: dict[str, Any],
    *,
    stats: dict[str, Any],
    min_target_minutes: int,
) -> dict[str, Any]:
    ctype = str(payload_condition.get("type", "total_minutes")).strip().lower()

    if ctype == "total_minutes":
        target_minutes = int(payload_condition.get("target_minutes", 0))
        category = str(payload_condition.get("category", "build")).strip().lower()
        if category not in PRODUCTIVE_CATEGORIES and category != "all":
            category = "build"
        return {
            "type": "total_minutes",
            "target_minutes": max(min_target_minutes, target_minutes),
            "category": category,
        }

    if ctype == "weekly_hours":
        target_minutes = int(payload_condition.get("target", 0) * 60)
        return {
            "type": "total_minutes",
            "target_minutes": max(min_target_minutes, target_minutes),
            "category": "all",
        }

    if ctype == "category_hours":
        category = str(payload_condition.get("category", stats.get("top_category", "build"))).strip().lower()
        if category not in PRODUCTIVE_CATEGORIES:
            category = "build"
        target_minutes = int(payload_condition.get("target", 0) * 60)
        return {
            "type": "total_minutes",
            "target_minutes": max(min_target_minutes, target_minutes),
            "category": category,
        }

    # Backward-compatible fallback for older condition types:
    # normalize to a measurable total-minutes quest.
    default_category = "build" if stats.get("build_share", 0.0) <= 0.7 else "all"
    return {
        "type": "total_minutes",
        "target_minutes": min_target_minutes,
        "category": default_category,
    }


def _validate_llm_quest(
    payload: dict[str, Any],
    stats: dict[str, Any],
    rng: random.Random,
    *,
    difficulty_hint: str | None = None,
    duration_days_hint: int | None = None,
) -> dict[str, Any] | None:
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    quest_type = str(payload.get("quest_type", "challenge")).strip().lower() or "challenge"

    difficulty_raw = str(payload.get("difficulty", difficulty_hint or "medium")).strip().lower()
    difficulty = difficulty_raw if difficulty_raw in QUEST_DIFFICULTY_RULES else "medium"
    if difficulty_hint in QUEST_DIFFICULTY_RULES:
        difficulty = str(difficulty_hint)

    duration_raw = payload.get("duration_days", duration_days_hint if duration_days_hint else 7)
    try:
        duration_days = _normalize_duration_days(int(duration_raw))
    except (TypeError, ValueError):
        duration_days = _normalize_duration_days(duration_days_hint if duration_days_hint else 7)

    if not title or not description:
        return None

    condition = payload.get("condition")
    if not isinstance(condition, dict):
        return None

    min_target_minutes = quest_min_target_minutes(difficulty, duration_days)
    normalized_condition = _normalize_condition(
        condition,
        stats=stats,
        min_target_minutes=min_target_minutes,
    )

    reward_lo, reward_hi = quest_reward_bounds(difficulty, duration_days)
    reward_raw = payload.get("reward_fun_minutes", payload.get("reward", reward_lo))
    try:
        reward_fun = int(reward_raw)
    except (TypeError, ValueError):
        reward_fun = reward_lo
    reward_fun = _clamp_int(reward_fun, reward_lo, reward_hi)

    # Product rule: penalty mirrors reward.
    penalty_fun = reward_fun

    extra_benefit = str(payload.get("extra_benefit", "")).strip() or None

    return {
        "title": title,
        "description": description,
        "quest_type": quest_type,
        "difficulty": difficulty,
        "duration_days": duration_days,
        "condition": normalized_condition,
        "reward": reward_fun,
        "reward_fun_minutes": reward_fun,
        "penalty": penalty_fun,
        "penalty_fun_minutes": penalty_fun,
        "extra_benefit": extra_benefit,
    }


def extract_quest_payload(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None

    # Try plain JSON first.
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try fenced JSON block.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            data = json.loads(fenced.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Last resort: first object-like range.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ensure_weekly_quests(
    db: Database,
    user_id: int,
    now: datetime,
    llm_enabled: bool = False,
    llm_route: Any | None = None,
) -> None:
    # Quests 2.0: no automatic generation.
    return None


def _quest_window(quest: Quest, now: datetime) -> tuple[datetime, datetime]:
    start = quest.starts_at
    end = min(now, quest.expires_at)
    if end < start:
        end = start
    return start, end


def _daily_totals_in_window(
    db: Database,
    user_id: int,
    kind: str,
    start: datetime,
    end: datetime,
    category: str | None = None,
) -> dict[date, int]:
    start_date = start.date()
    end_date_exclusive = (end + timedelta(days=1)).date()
    return db.daily_totals(user_id, kind, start_date, end_date_exclusive, category=category)


def evaluate_quest_progress(db: Database, user_id: int, quest: Quest, now: datetime) -> QuestProgress:
    condition = json.loads(quest.condition_json)
    ctype = str(condition.get("type", "")).strip().lower()
    window_start, window_end = _quest_window(quest, now)

    if ctype == "total_minutes":
        target = int(condition.get("target_minutes", 0))
        category = str(condition.get("category", "all")).strip().lower()
        if category in PRODUCTIVE_CATEGORIES:
            current = db.sum_minutes(user_id, "productive", start=window_start, end=window_end, category=category)
        else:
            current = db.sum_minutes(user_id, "productive", start=window_start, end=window_end)
            job_minutes = db.sum_minutes(user_id, "productive", start=window_start, end=window_end, category="job")
            current = max(0, current - job_minutes)
        return QuestProgress(quest, current, target, "min", current >= target)

    if ctype == "daily_hours":
        target_minutes = int(condition.get("target", 0) * 60)
        totals = _daily_totals_in_window(db, user_id, "productive", window_start, window_end)
        job_totals = _daily_totals_in_window(db, user_id, "productive", window_start, window_end, category="job")
        for day, m in job_totals.items():
            if day in totals:
                totals[day] = max(0, totals[day] - m)
        best = max(totals.values(), default=0)
        return QuestProgress(quest, best, target_minutes, "min", best >= target_minutes)

    if ctype == "weekly_hours":
        target_minutes = int(condition.get("target", 0) * 60)
        current = db.sum_minutes(user_id, "productive", start=window_start, end=window_end)
        job_minutes = db.sum_minutes(user_id, "productive", start=window_start, end=window_end, category="job")
        current = max(0, current - job_minutes)
        return QuestProgress(quest, current, target_minutes, "min", current >= target_minutes)

    if ctype == "no_fun_day":
        days = int(condition.get("days", 1))
        start_day = max(window_start.date(), now.date() - timedelta(days=days - 1))
        totals = db.daily_totals(user_id, "spend", start_day, now.date() + timedelta(days=1))
        passed = all(totals.get(start_day + timedelta(days=i), 0) == 0 for i in range(days))
        return QuestProgress(quest, days if passed else 0, days, "days", passed)

    if ctype == "streak_days":
        target = int(condition.get("target", 0))
        streak = db.get_streak(user_id, now)
        return QuestProgress(quest, streak.current_streak, target, "days", streak.current_streak >= target)

    if ctype == "category_hours":
        category = str(condition.get("category", "build")).lower()
        if category not in PRODUCTIVE_CATEGORIES:
            category = "build"
        target_minutes = int(condition.get("target", 0) * 60)
        totals = _daily_totals_in_window(db, user_id, "productive", window_start, window_end, category=category)
        best = max(totals.values(), default=0)
        return QuestProgress(quest, best, target_minutes, "min", best >= target_minutes)

    if ctype == "consecutive_days":
        min_hours = int(condition.get("min_hours", 1))
        target_days = int(condition.get("target", 1))
        min_minutes = min_hours * 60
        totals = _daily_totals_in_window(db, user_id, "productive", window_start, window_end)
        job_totals = _daily_totals_in_window(db, user_id, "productive", window_start, window_end, category="job")
        for day, m in job_totals.items():
            if day in totals:
                totals[day] = max(0, totals[day] - m)

        longest = 0
        running = 0
        day = window_start.date()
        while day <= window_end.date():
            if totals.get(day, 0) >= min_minutes:
                running += 1
                longest = max(longest, running)
            else:
                running = 0
            day += timedelta(days=1)
        return QuestProgress(quest, longest, target_days, "days", longest >= target_days)

    return QuestProgress(quest, 0, 1, "", False)


def _remember_quest_memory(db: Database, user_id: int, now: datetime, event: str, quest: Quest) -> None:
    text = (
        f"{event}: [{quest.difficulty}] {quest.title} "
        f"({quest.duration_days}d, reward {quest.reward_fun_minutes}m, penalty {quest.penalty_fun_minutes}m)"
    )
    tags = f"quest,{event},{quest.difficulty}"
    try:
        db.add_coach_memory(
            user_id=user_id,
            category="context",
            content=text[:500],
            tags=tags,
            created_at=now,
        )
    except Exception:
        # Quest sync must never fail because memory write failed.
        return


def sync_quests_for_user(db: Database, user_id: int, now: datetime) -> QuestSyncResult:
    completed: list[QuestProgress] = []
    failed: list[Quest] = []
    penalty_total = 0

    for quest in db.list_quests_by_status(user_id, "active"):
        progress = evaluate_quest_progress(db, user_id, quest, now)
        if progress.complete:
            db.update_quest_status(quest.id, "completed", now)
            completed.append(progress)
            _remember_quest_memory(db, user_id, now, "completed", quest)
            continue

        if quest.expires_at < now:
            db.update_quest_status(quest.id, "failed", now)
            failed.append(quest)
            _remember_quest_memory(db, user_id, now, "failed", quest)
            if quest.penalty_fun_minutes > 0 and quest.penalty_applied_at is None:
                db.add_entry(
                    user_id=user_id,
                    kind="spend",
                    category="spend",
                    minutes=quest.penalty_fun_minutes,
                    note=f"Quest penalty: {quest.title}",
                    created_at=now,
                    source="quest_penalty",
                )
                db.mark_quest_penalty_applied(quest.id, now)
                penalty_total += quest.penalty_fun_minutes

    return QuestSyncResult(
        completed=completed,
        failed=failed,
        penalty_minutes_applied=penalty_total,
    )


def check_quests_for_user(db: Database, user_id: int, now: datetime) -> list[QuestProgress]:
    # Backward-compatible alias.
    return sync_quests_for_user(db, user_id, now).completed
