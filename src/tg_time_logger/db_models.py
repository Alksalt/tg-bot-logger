from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Entry:
    id: int
    user_id: int
    kind: str
    category: str
    minutes: int
    xp_earned: int
    fun_earned: int
    deep_work_multiplier: float
    note: str | None
    created_at: datetime
    deleted_at: datetime | None
    source: str


@dataclass(frozen=True)
class TimerSession:
    user_id: int
    category: str
    note: str | None
    started_at: datetime


@dataclass(frozen=True)
class UserSettings:
    user_id: int
    reminders_enabled: bool
    daily_goal_minutes: int
    quiet_hours: str | None


@dataclass(frozen=True)
class LevelUpEvent:
    id: int
    user_id: int
    level: int
    bonus_fun_minutes: int
    created_at: datetime


@dataclass(frozen=True)
class Streak:
    user_id: int
    current_streak: int
    longest_streak: int
    last_productive_date: date | None
    updated_at: datetime
