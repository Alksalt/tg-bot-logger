from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tg_time_logger.db import Database
from tg_time_logger.economy import FunEconomySnapshot, calculate_fun_economy
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
    economy: FunEconomySnapshot


def compute_status(db: Database, user_id: int, now: datetime) -> StatusView:
    week = week_range_for(now)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_productive = db.sum_minutes(user_id, "productive", start=day_start, end=now)
    today_spent = db.sum_minutes(user_id, "spend", start=day_start, end=now)

    week_productive = db.sum_minutes(user_id, "productive", start=week.start, end=now)
    week_spent = db.sum_minutes(user_id, "spend", start=week.start, end=now)

    all_productive = db.sum_minutes(user_id, "productive")
    all_spent = db.sum_minutes(user_id, "spend")

    return StatusView(
        today=PeriodTotals(today_productive, today_spent),
        week=PeriodTotals(week_productive, week_spent),
        all_time=PeriodTotals(all_productive, all_spent),
        economy=calculate_fun_economy(all_productive, all_spent),
    )
