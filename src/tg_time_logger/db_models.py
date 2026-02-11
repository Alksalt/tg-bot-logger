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
    shop_budget_minutes: int | None
    auto_save_minutes: int
    sunday_fund_percent: int
    language_code: str


@dataclass(frozen=True)
class PlanTarget:
    user_id: int
    week_start_date: date
    total_target_minutes: int
    study_target_minutes: int
    build_target_minutes: int
    training_target_minutes: int
    job_target_minutes: int


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


@dataclass(frozen=True)
class Quest:
    id: int
    user_id: int
    title: str
    description: str
    quest_type: str
    difficulty: str
    reward_fun_minutes: int
    condition_json: str
    status: str
    expires_at: datetime
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ShopItem:
    id: int
    user_id: int
    name: str
    emoji: str
    cost_fun_minutes: int
    nok_value: float | None
    active: bool


@dataclass(frozen=True)
class SavingsGoal:
    id: int
    user_id: int
    name: str
    target_fun_minutes: int
    saved_fun_minutes: int
    status: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class LlmUsage:
    user_id: int
    day_key: str
    request_count: int
    last_request_at: datetime | None


@dataclass(frozen=True)
class UserRule:
    id: int
    user_id: int
    rule_text: str
    created_at: datetime
