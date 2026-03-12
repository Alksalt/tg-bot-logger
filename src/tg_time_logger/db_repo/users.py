from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Protocol

from tg_time_logger.db_models import UserSettings


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...


class UserMixin:
    def upsert_user_profile(self: DbProtocol, user_id: int, chat_id: int, seen_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles(user_id, chat_id, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id=excluded.chat_id,
                    last_seen_at=excluded.last_seen_at
                """,
                (user_id, chat_id, seen_at.isoformat()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)",
                (user_id,),
            )

    def get_all_user_profiles(self: DbProtocol) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.user_id, p.chat_id, p.last_seen_at,
                       s.reminders_enabled, s.daily_goal_minutes, s.quiet_hours
                FROM user_profiles p
                LEFT JOIN user_settings s ON s.user_id = p.user_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_settings(self: DbProtocol, user_id: int) -> UserSettings:
        with self._connect() as conn:
            # Keep this one to ensure settings exist when reading
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            row = conn.execute(
                "SELECT user_id, reminders_enabled, daily_goal_minutes, quiet_hours FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        assert row is not None
        return UserSettings(
            user_id=row["user_id"],
            reminders_enabled=bool(row["reminders_enabled"]),
            daily_goal_minutes=row["daily_goal_minutes"],
            quiet_hours=row["quiet_hours"],
        )

    def update_reminders_enabled(self: DbProtocol, user_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET reminders_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id),
            )

    def update_quiet_hours(self: DbProtocol, user_id: int, quiet_hours: str | None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET quiet_hours = ? WHERE user_id = ?",
                (quiet_hours, user_id),
            )

    def update_daily_goal(self: DbProtocol, user_id: int, minutes: int) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET daily_goal_minutes = ? WHERE user_id = ?",
                (minutes, user_id),
            )
