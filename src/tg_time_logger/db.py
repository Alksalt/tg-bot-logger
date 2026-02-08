from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Entry:
    id: int
    user_id: int
    entry_type: str
    category: str | None
    minutes: int
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
class PlanTarget:
    user_id: int
    week_start_date: date
    work_minutes: int
    study_minutes: int
    learn_minutes: int


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            current = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}

            migrations: dict[int, str] = {
                1: """
                    CREATE TABLE entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        entry_type TEXT NOT NULL CHECK(entry_type IN ('productive', 'spend')),
                        category TEXT,
                        minutes INTEGER NOT NULL CHECK(minutes > 0),
                        note TEXT,
                        created_at TEXT NOT NULL,
                        deleted_at TEXT,
                        source TEXT NOT NULL DEFAULT 'manual'
                    );

                    CREATE INDEX idx_entries_user_created ON entries(user_id, created_at);
                    CREATE INDEX idx_entries_user_deleted ON entries(user_id, deleted_at);

                    CREATE TABLE timer_sessions (
                        user_id INTEGER PRIMARY KEY,
                        category TEXT NOT NULL,
                        note TEXT,
                        started_at TEXT NOT NULL
                    );

                    CREATE TABLE user_settings (
                        user_id INTEGER PRIMARY KEY,
                        reminders_enabled INTEGER NOT NULL DEFAULT 1,
                        daily_goal_minutes INTEGER NOT NULL DEFAULT 60,
                        quiet_hours TEXT
                    );

                    CREATE TABLE plan_targets (
                        user_id INTEGER NOT NULL,
                        week_start_date TEXT NOT NULL,
                        work_minutes INTEGER NOT NULL DEFAULT 0,
                        study_minutes INTEGER NOT NULL DEFAULT 0,
                        learn_minutes INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY(user_id, week_start_date)
                    );

                    CREATE TABLE user_profiles (
                        user_id INTEGER PRIMARY KEY,
                        chat_id INTEGER NOT NULL,
                        last_seen_at TEXT NOT NULL
                    );

                    CREATE TABLE reminder_events (
                        user_id INTEGER NOT NULL,
                        event_key TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, event_key)
                    );
                """,
            }

            now = datetime.now().isoformat(timespec="seconds")
            for version in sorted(migrations):
                if version in current:
                    continue
                conn.executescript(migrations[version])
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, now),
                )

    def upsert_user_profile(self, user_id: int, chat_id: int, seen_at: datetime) -> None:
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

    def get_all_user_profiles(self) -> list[dict[str, Any]]:
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

    def get_settings(self, user_id: int) -> UserSettings:
        with self._connect() as conn:
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

    def update_reminders_enabled(self, user_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET reminders_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id),
            )

    def update_quiet_hours(self, user_id: int, quiet_hours: str | None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET quiet_hours = ? WHERE user_id = ?",
                (quiet_hours, user_id),
            )

    def add_entry(
        self,
        user_id: int,
        entry_type: str,
        minutes: int,
        created_at: datetime,
        category: str | None = None,
        note: str | None = None,
        source: str = "manual",
    ) -> Entry:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO entries(user_id, entry_type, category, minutes, note, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, entry_type, category, minutes, note, created_at.isoformat(), source),
            )
            row = conn.execute("SELECT * FROM entries WHERE id = ?", (cursor.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_entry(row)

    def undo_last_entry(self, user_id: int, deleted_at: datetime) -> Entry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM entries
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE entries SET deleted_at = ? WHERE id = ?",
                (deleted_at.isoformat(), row["id"]),
            )
            updated = conn.execute("SELECT * FROM entries WHERE id = ?", (row["id"],)).fetchone()
        assert updated is not None
        return _row_to_entry(updated)

    def sum_minutes(
        self,
        user_id: int,
        entry_type: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        conditions = ["user_id = ?", "entry_type = ?", "deleted_at IS NULL"]
        params: list[Any] = [user_id, entry_type]
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        query = f"SELECT COALESCE(SUM(minutes), 0) AS total FROM entries WHERE {' AND '.join(conditions)}"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["total"]) if row else 0

    def sum_productive_by_category(
        self,
        user_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, int]:
        conditions = ["user_id = ?", "entry_type = 'productive'", "deleted_at IS NULL"]
        params: list[Any] = [user_id]
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        query = f"SELECT category, COALESCE(SUM(minutes), 0) AS total FROM entries WHERE {' AND '.join(conditions)} GROUP BY category"
        result = {"work": 0, "study": 0, "learn": 0}
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        for row in rows:
            category = row["category"]
            if category in result:
                result[category] = int(row["total"])
        return result

    def has_productive_log_between(self, user_id: int, start: datetime, end: datetime) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM entries
                WHERE user_id = ?
                  AND entry_type = 'productive'
                  AND deleted_at IS NULL
                  AND created_at >= ?
                  AND created_at < ?
                LIMIT 1
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()
        return row is not None

    def get_or_start_timer(
        self,
        user_id: int,
        category: str,
        started_at: datetime,
        note: str | None,
    ) -> tuple[TimerSession | None, TimerSession]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT user_id, category, note, started_at FROM timer_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if existing:
                return _row_to_timer(existing), _row_to_timer(existing)
            conn.execute(
                "INSERT INTO timer_sessions(user_id, category, note, started_at) VALUES (?, ?, ?, ?)",
                (user_id, category, note, started_at.isoformat()),
            )
            created = conn.execute(
                "SELECT user_id, category, note, started_at FROM timer_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        assert created is not None
        return None, _row_to_timer(created)

    def stop_timer(self, user_id: int) -> TimerSession | None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT user_id, category, note, started_at FROM timer_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if existing is None:
                return None
            conn.execute("DELETE FROM timer_sessions WHERE user_id = ?", (user_id,))
        return _row_to_timer(existing)

    def set_plan_target(
        self,
        user_id: int,
        week_start: date,
        work_minutes: int,
        study_minutes: int,
        learn_minutes: int,
    ) -> PlanTarget:
        week_key = week_start.isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO plan_targets(user_id, week_start_date, work_minutes, study_minutes, learn_minutes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, week_start_date) DO UPDATE SET
                    work_minutes=excluded.work_minutes,
                    study_minutes=excluded.study_minutes,
                    learn_minutes=excluded.learn_minutes
                """,
                (user_id, week_key, work_minutes, study_minutes, learn_minutes),
            )
            row = conn.execute(
                "SELECT * FROM plan_targets WHERE user_id = ? AND week_start_date = ?",
                (user_id, week_key),
            ).fetchone()
        assert row is not None
        return _row_to_plan(row)

    def get_plan_target(self, user_id: int, week_start: date) -> PlanTarget | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM plan_targets WHERE user_id = ? AND week_start_date = ?",
                (user_id, week_start.isoformat()),
            ).fetchone()
        return _row_to_plan(row) if row else None

    def was_event_sent(self, user_id: int, event_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reminder_events WHERE user_id = ? AND event_key = ?",
                (user_id, event_key),
            ).fetchone()
        return row is not None

    def mark_event_sent(self, user_id: int, event_key: str, sent_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO reminder_events(user_id, event_key, sent_at)
                VALUES (?, ?, ?)
                """,
                (user_id, event_key, sent_at.isoformat()),
            )


def _row_to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        user_id=row["user_id"],
        entry_type=row["entry_type"],
        category=row["category"],
        minutes=row["minutes"],
        note=row["note"],
        created_at=datetime.fromisoformat(row["created_at"]),
        deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        source=row["source"],
    )


def _row_to_timer(row: sqlite3.Row) -> TimerSession:
    return TimerSession(
        user_id=row["user_id"],
        category=row["category"],
        note=row["note"],
        started_at=datetime.fromisoformat(row["started_at"]),
    )


def _row_to_plan(row: sqlite3.Row) -> PlanTarget:
    return PlanTarget(
        user_id=row["user_id"],
        week_start_date=date.fromisoformat(row["week_start_date"]),
        work_minutes=row["work_minutes"],
        study_minutes=row["study_minutes"],
        learn_minutes=row["learn_minutes"],
    )
