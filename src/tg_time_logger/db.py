from __future__ import annotations

from tg_time_logger.db_models import (
    CoachMemory,
    CoachMessage,
    Entry,
    LevelUpEvent,
    LlmUsage,
    PlanTarget,
    Quest,
    SavingsGoal,
    ShopItem,
    Streak,
    TimerSession,
    TodoItem,
    UserRule,
    UserSettings,
)
from tg_time_logger.db_repo import (
    BaseDatabase,
    GamificationMixin,
    HistoryMixin,
    LogMixin,
    ShopMixin,
    SystemMixin,
    TodoMixin,
    UserMixin,
)


class Database(
    UserMixin,
    LogMixin,
    GamificationMixin,
    ShopMixin,
    HistoryMixin,
    SystemMixin,
    TodoMixin,
    BaseDatabase,
):
    """
    Main Database class combining all repository mixins.
    Inherits from specific mixins and the BaseDatabase for connection handling.
    """
    pass

__all__ = [
    "CoachMemory",
    "CoachMessage",
    "Entry",
    "LevelUpEvent",
    "LlmUsage",
    "PlanTarget",
    "Quest",
    "SavingsGoal",
    "ShopItem",
    "Streak",
    "TimerSession",
    "TodoItem",
    "UserRule",
    "UserSettings",
    "Database",
]
