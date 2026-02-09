from __future__ import annotations

from datetime import datetime

from tg_time_logger.db import Database, ShopItem


def monthly_budget_remaining(db: Database, user_id: int, now: datetime) -> int | None:
    settings = db.get_settings(user_id)
    if settings.shop_budget_minutes is None:
        return None
    used = db.monthly_redemption_minutes(user_id, now.year, now.month)
    return max(settings.shop_budget_minutes - used, 0)


def resolve_item(db: Database, user_id: int, identifier: str) -> ShopItem | None:
    return db.find_shop_item(user_id, identifier)
