from __future__ import annotations

import sqlite3
from datetime import date, datetime

from tg_time_logger.db_models import (
    Entry,
    LevelUpEvent,
    Streak,
    TimerSession,
    UserSettings,
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
