from __future__ import annotations

from tg_time_logger.db_models import (
    Entry,
    LevelUpEvent,
    Streak,
    TimerSession,
    UserSettings,
)
from tg_time_logger.db_repo import (
    BaseDatabase,
    GamificationMixin,
    LogMixin,
    SystemMixin,
    UserMixin,
)


class Database(
    UserMixin,
    LogMixin,
    GamificationMixin,
    SystemMixin,
    BaseDatabase,
):
    """
    Main Database class combining all repository mixins.
    Inherits from specific mixins and the BaseDatabase for connection handling.
    """
    pass

__all__ = [
    "Entry",
    "LevelUpEvent",
    "Streak",
    "TimerSession",
    "UserSettings",
    "Database",
]
