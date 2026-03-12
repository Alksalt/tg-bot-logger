from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from tg_time_logger.db_constants import STREAK_MINUTES_REQUIRED
from tg_time_logger.db_converters import _row_to_level, _row_to_streak
from tg_time_logger.db_models import LevelUpEvent, Streak
from tg_time_logger.gamification import level_up_bonus_minutes


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...
    def productive_minutes_for_date(self, user_id: int, day: date, category: str | None = None) -> int: ...
    def sum_minutes(
        self,
        user_id: int,
        kind: str,
        start: datetime | None = None,
        end: datetime | None = None,
        category: str | None = None,
    ) -> int: ...


class GamificationMixin:
    def get_streak(self: DbProtocol, user_id: int, now: datetime) -> Streak:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, current_streak, longest_streak, last_productive_date, updated_at FROM streaks WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row:
                return _row_to_streak(row)

            created = now.isoformat()
            conn.execute(
                "INSERT INTO streaks(user_id, current_streak, longest_streak, updated_at) VALUES (?, 0, 0, ?)",
                (user_id, created),
            )
            row2 = conn.execute(
                "SELECT user_id, current_streak, longest_streak, last_productive_date, updated_at FROM streaks WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        assert row2 is not None
        return _row_to_streak(row2)

    def has_freeze_on_date(self: DbProtocol, user_id: int, freeze_date: date) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM streak_freezes WHERE user_id = ? AND freeze_date = ?",
                (user_id, freeze_date.isoformat()),
            ).fetchone()
        return row is not None

    def create_freeze(self: DbProtocol, user_id: int, freeze_date: date, created_at: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO streak_freezes(user_id, freeze_date, created_at) VALUES (?, ?, ?)",
                (user_id, freeze_date.isoformat(), created_at.isoformat()),
            )
        return cur.rowcount > 0

    def refresh_streak(self: DbProtocol, user_id: int, now: datetime) -> Streak:
        streak = self.get_streak(user_id, now)
        today = now.date()
        if self.productive_minutes_for_date(user_id, today) < STREAK_MINUTES_REQUIRED:
            return streak

        last_date = streak.last_productive_date
        current = streak.current_streak

        if last_date == today:
            return streak

        yesterday = today - timedelta(days=1)
        preserved = self.has_freeze_on_date(user_id, yesterday)

        if last_date is None:
            new_current = 1
        elif last_date == yesterday or preserved:
            new_current = current + 1
        else:
            new_current = 1

        new_longest = max(streak.longest_streak, new_current)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE streaks
                SET current_streak = ?, longest_streak = ?, last_productive_date = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (new_current, new_longest, today.isoformat(), now.isoformat(), user_id),
            )
            row = conn.execute(
                "SELECT user_id, current_streak, longest_streak, last_productive_date, updated_at FROM streaks WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        assert row is not None
        return _row_to_streak(row)

    def productive_minutes_for_date(self: DbProtocol, user_id: int, day: date, category: str | None = None) -> int:
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        return self.sum_minutes(user_id, "productive", start=start, end=end, category=category)

    def daily_totals(self: DbProtocol, user_id: int, kind: str, start_date: date, end_date_exclusive: date, category: str | None = None) -> dict[date, int]:
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date_exclusive, datetime.min.time())

        conditions = ["user_id = ?", "kind = ?", "deleted_at IS NULL", "created_at >= ?", "created_at < ?"]
        params: list[Any] = [user_id, kind, start.isoformat(), end.isoformat()]
        if category is not None:
            conditions.append("category = ?")
            params.append(category)

        query = (
            "SELECT substr(created_at, 1, 10) AS d, COALESCE(SUM(minutes), 0) AS total "
            f"FROM entries WHERE {' AND '.join(conditions)} GROUP BY d"
        )
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        result: dict[date, int] = {}
        for row in rows:
            result[date.fromisoformat(row["d"])] = int(row["total"])
        return result

    def max_level_event_level(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(level), 1) AS lvl FROM level_up_events WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["lvl"]) if row else 1

    def add_level_up_event(
        self: DbProtocol,
        user_id: int,
        level: int,
        created_at: datetime,
        tuning: dict[str, int] | None = None,
    ) -> LevelUpEvent | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO level_up_events(user_id, level, bonus_fun_minutes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, level, level_up_bonus_minutes(level, tuning=tuning), created_at.isoformat()),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM level_up_events WHERE user_id = ? AND level = ?", (user_id, level)).fetchone()
        assert row is not None
        return _row_to_level(row)

    def list_level_up_events(self: DbProtocol, user_id: int) -> list[LevelUpEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM level_up_events WHERE user_id = ? ORDER BY level ASC",
                (user_id,),
            ).fetchall()
        return [_row_to_level(r) for r in rows]

    def delete_level_up_event(self: DbProtocol, event_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM level_up_events WHERE id = ?", (event_id,))
        return cur.rowcount > 0

    def reset_streak(self: DbProtocol, user_id: int, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE streaks
                SET current_streak = 0, last_productive_date = NULL, updated_at = ?
                WHERE user_id = ?
                """,
                (now.isoformat(), user_id),
            )

    def sum_level_bonus(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT level FROM level_up_events WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        try:
            tuning = getattr(self, "get_economy_tuning")()
        except AttributeError:
            tuning = None

        total = 0
        for row in rows:
            total += level_up_bonus_minutes(int(row["level"]), tuning=tuning)
        return total

    def get_distinct_level_up_user_ids(self: DbProtocol) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT user_id FROM level_up_events ORDER BY user_id ASC"
            ).fetchall()
        return [int(row["user_id"]) for row in rows]

    def recalculate_level_bonuses(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, level FROM level_up_events WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            count = 0
            for row in rows:
                new_bonus = level_up_bonus_minutes(int(row["level"]))
                conn.execute(
                    "UPDATE level_up_events SET bonus_fun_minutes = ? WHERE id = ?",
                    (new_bonus, row["id"]),
                )
                count += 1
        return count

    def set_user_level(self: DbProtocol, user_id: int, target_level: int, now: datetime) -> int:
        with self._connect() as conn:
            conn.execute("DELETE FROM level_up_events WHERE user_id = ?", (user_id,))
            count = 0
            for lvl in range(2, target_level + 1):
                bonus = level_up_bonus_minutes(lvl)
                conn.execute(
                    "INSERT INTO level_up_events(user_id, level, bonus_fun_minutes, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, lvl, bonus, now.isoformat()),
                )
                count += 1
        return count

    def count_deep_sessions(self: DbProtocol, user_id: int, start: datetime, end: datetime, minimum_minutes: int = 90) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM entries
                WHERE user_id = ?
                  AND kind = 'productive'
                  AND source = 'timer'
                  AND deleted_at IS NULL
                  AND minutes >= ?
                  AND created_at >= ?
                  AND created_at < ?
                """,
                (user_id, minimum_minutes, start.isoformat(), end.isoformat()),
            ).fetchone()
        return int(row["total"]) if row else 0
