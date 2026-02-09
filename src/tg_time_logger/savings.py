from __future__ import annotations

from datetime import datetime

from tg_time_logger.db import Database, SavingsGoal


def auto_deposit(db: Database, user_id: int, amount: int, now: datetime) -> SavingsGoal | None:
    if amount <= 0:
        return None
    return db.deposit_to_savings(user_id, amount, now)
