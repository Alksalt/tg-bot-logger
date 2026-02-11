from __future__ import annotations

import sqlite3
from datetime import date, datetime

from tg_time_logger.db_models import (
    Entry,
    LevelUpEvent,
    LlmUsage,
    PlanTarget,
    Quest,
    SavingsGoal,
    ShopItem,
    Streak,
    TimerSession,
    UserRule,
)


def _row_to_entry(row: sqlite3.Row) -> Entry:
    kind = row["kind"] if "kind" in row.keys() and row["kind"] else row["entry_type"]
    category = row["category"] or ("spend" if kind == "spend" else "build")
    xp_earned = int(row["xp_earned"] if "xp_earned" in row.keys() and row["xp_earned"] is not None else (row["minutes"] if kind == "productive" else 0))
    fun_earned = int(row["fun_earned"] if "fun_earned" in row.keys() and row["fun_earned"] is not None else 0)
    deep_mult = float(row["deep_work_multiplier"] if "deep_work_multiplier" in row.keys() and row["deep_work_multiplier"] is not None else 1.0)

    return Entry(
        id=row["id"],
        user_id=row["user_id"],
        kind=kind,
        category=category,
        minutes=row["minutes"],
        xp_earned=xp_earned,
        fun_earned=fun_earned,
        deep_work_multiplier=deep_mult,
        note=row["note"],
        created_at=datetime.fromisoformat(row["created_at"]),
        deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        source=row["source"],
    )


def _row_to_timer(row: sqlite3.Row) -> TimerSession:
    return TimerSession(
        user_id=row["user_id"],
        category=row["category"] or "build",
        note=row["note"],
        started_at=datetime.fromisoformat(row["started_at"]),
    )


def _row_to_plan(row: sqlite3.Row) -> PlanTarget:
    return PlanTarget(
        user_id=row["user_id"],
        week_start_date=date.fromisoformat(row["week_start_date"]),
        total_target_minutes=row["total_target_minutes"],
        study_target_minutes=row["study_target_minutes"],
        build_target_minutes=row["build_target_minutes"],
        training_target_minutes=row["training_target_minutes"],
        job_target_minutes=row["job_target_minutes"],
    )


def _row_to_level(row: sqlite3.Row) -> LevelUpEvent:
    return LevelUpEvent(
        id=row["id"],
        user_id=row["user_id"],
        level=row["level"],
        bonus_fun_minutes=row["bonus_fun_minutes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_streak(row: sqlite3.Row) -> Streak:
    return Streak(
        user_id=row["user_id"],
        current_streak=int(row["current_streak"]),
        longest_streak=int(row["longest_streak"]),
        last_productive_date=date.fromisoformat(row["last_productive_date"]) if row["last_productive_date"] else None,
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_quest(row: sqlite3.Row) -> Quest:
    return Quest(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        quest_type=row["quest_type"],
        difficulty=row["difficulty"],
        reward_fun_minutes=row["reward_fun_minutes"],
        condition_json=row["condition_json"],
        status=row["status"],
        expires_at=datetime.fromisoformat(row["expires_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_shop_item(row: sqlite3.Row) -> ShopItem:
    return ShopItem(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        emoji=row["emoji"] or "\U0001f381",
        cost_fun_minutes=row["cost_fun_minutes"],
        nok_value=row["nok_value"],
        active=bool(row["active"]),
    )


def _row_to_savings(row: sqlite3.Row) -> SavingsGoal:
    return SavingsGoal(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        target_fun_minutes=row["target_fun_minutes"],
        saved_fun_minutes=row["saved_fun_minutes"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )


def _row_to_llm_usage(row: sqlite3.Row) -> LlmUsage:
    return LlmUsage(
        user_id=row["user_id"],
        day_key=row["day_key"],
        request_count=int(row["request_count"]),
        last_request_at=datetime.fromisoformat(row["last_request_at"]) if row["last_request_at"] else None,
    )


def _row_to_user_rule(row: sqlite3.Row) -> UserRule:
    return UserRule(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        rule_text=str(row["rule_text"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
