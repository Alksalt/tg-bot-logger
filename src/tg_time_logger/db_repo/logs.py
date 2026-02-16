from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any, Protocol

from tg_time_logger.db_converters import _row_to_entry, _row_to_llm_usage, _row_to_timer
from tg_time_logger.db_models import Entry, LlmUsage, TimerSession
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, fun_from_minutes


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...
    def get_economy_tuning(self) -> dict[str, int]: ...
    def is_feature_enabled(self, feature_name: str) -> bool: ...


class LogMixin:
    def add_entry(
        self: DbProtocol,
        user_id: int,
        kind: str,
        minutes: int,
        created_at: datetime,
        note: str | None = None,
        source: str = "manual",
        category: str | None = None,
        xp_earned: int | None = None,
        fun_earned: int | None = None,
        deep_work_multiplier: float = 1.0,
    ) -> Entry:
        if kind not in {"productive", "spend", "other"}:
            raise ValueError("kind must be productive, spend, or other")

        tuning = self.get_economy_tuning()
        economy_enabled = self.is_feature_enabled("economy")
        if kind == "productive":
            normalized_category = category if category in PRODUCTIVE_CATEGORIES else "build"
            default_xp = 0 if normalized_category == "job" else minutes
            if not economy_enabled:
                default_xp = 0
            computed_xp = max(0, xp_earned if xp_earned is not None else default_xp)
            default_fun = fun_from_minutes(normalized_category, minutes, tuning=tuning) if economy_enabled else 0
            computed_fun = max(0, fun_earned if fun_earned is not None else default_fun)
        elif kind == "other":
            normalized_category = category or "other"
            computed_xp = 0
            computed_fun = 0
        else:
            normalized_category = "spend"
            computed_xp = 0
            computed_fun = 0

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO entries(
                    user_id, entry_type, category, kind, minutes, xp_earned, fun_earned,
                    deep_work_multiplier, note, created_at, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    kind,
                    normalized_category,
                    kind,
                    minutes,
                    computed_xp,
                    computed_fun,
                    deep_work_multiplier,
                    note,
                    created_at.isoformat(),
                    source,
                ),
            )
            row = conn.execute("SELECT * FROM entries WHERE id = ?", (cursor.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_entry(row)

    def update_entry_xp(self: DbProtocol, entry_id: int, xp_earned: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE entries SET xp_earned = ? WHERE id = ?", (max(0, xp_earned), entry_id))

    def undo_last_entry(self: DbProtocol, user_id: int, deleted_at: datetime) -> Entry | None:
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

    def list_recent_entries(self: DbProtocol, user_id: int, limit: int = 200) -> list[Entry]:
        capped = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM entries
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, capped),
            ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def sum_minutes(
        self: DbProtocol,
        user_id: int,
        kind: str,
        start: datetime | None = None,
        end: datetime | None = None,
        category: str | None = None,
    ) -> int:
        conditions = ["user_id = ?", "kind = ?", "deleted_at IS NULL"]
        params: list[Any] = [user_id, kind]
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
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

    def sum_minutes_by_note(
        self: DbProtocol,
        user_id: int,
        note_query: str,
        kind: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[int, int]:
        query_text = note_query.strip().lower()
        if not query_text:
            return 0, 0

        conditions = ["user_id = ?", "deleted_at IS NULL", "note IS NOT NULL", "lower(note) LIKE ?"]
        params: list[Any] = [user_id, f"%{query_text}%"]
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        sql = (
            "SELECT COALESCE(SUM(minutes), 0) AS total_minutes, COUNT(*) AS match_count "
            f"FROM entries WHERE {' AND '.join(conditions)}"
        )
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        if not row:
            return 0, 0
        return int(row["total_minutes"]), int(row["match_count"])

    def list_entries_by_note(
        self: DbProtocol,
        user_id: int,
        note_query: str,
        kind: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
    ) -> list[Entry]:
        query_text = note_query.strip().lower()
        if not query_text:
            return []

        capped = max(1, min(int(limit), 200))
        conditions = ["user_id = ?", "deleted_at IS NULL", "note IS NOT NULL", "lower(note) LIKE ?"]
        params: list[Any] = [user_id, f"%{query_text}%"]
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        sql = (
            "SELECT * FROM entries "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC, id DESC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [*params, capped]).fetchall()
        return [_row_to_entry(r) for r in rows]

    def sum_xp(self: DbProtocol, user_id: int, start: datetime | None = None, end: datetime | None = None) -> int:
        conditions = ["user_id = ?", "kind = 'productive'", "deleted_at IS NULL"]
        params: list[Any] = [user_id]
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        query = f"SELECT COALESCE(SUM(COALESCE(xp_earned, minutes)), 0) AS total FROM entries WHERE {' AND '.join(conditions)}"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["total"]) if row else 0

    def sum_fun_earned_entries(self: DbProtocol, user_id: int, start: datetime | None = None, end: datetime | None = None) -> int:
        conditions = ["user_id = ?", "kind = 'productive'", "deleted_at IS NULL"]
        params: list[Any] = [user_id]
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        query = f"SELECT COALESCE(SUM(COALESCE(fun_earned, 0)), 0) AS total FROM entries WHERE {' AND '.join(conditions)}"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["total"]) if row else 0

    def sum_productive_by_category(
        self: DbProtocol,
        user_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, int]:
        conditions = ["user_id = ?", "kind = 'productive'", "deleted_at IS NULL"]
        params: list[Any] = [user_id]
        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("created_at < ?")
            params.append(end.isoformat())

        query = f"SELECT category, COALESCE(SUM(minutes), 0) AS total FROM entries WHERE {' AND '.join(conditions)} GROUP BY category"
        result = {"study": 0, "build": 0, "training": 0, "job": 0}
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        for row in rows:
            category = row["category"]
            if category in result:
                result[category] = int(row["total"])
        return result

    def top_category_for_week(self: DbProtocol, user_id: int, start: datetime, end: datetime) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT category, COALESCE(SUM(minutes), 0) AS total
                FROM entries
                WHERE user_id = ?
                  AND kind = 'productive'
                  AND deleted_at IS NULL
                  AND created_at >= ?
                  AND created_at < ?
                GROUP BY category
                ORDER BY total DESC, category ASC
                LIMIT 1
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchone()
        if row and row["category"]:
            return str(row["category"])
        return "build"

    def has_productive_log_between(self: DbProtocol, user_id: int, start: datetime, end: datetime) -> bool:
        return self.sum_minutes(user_id, "productive", start=start, end=end) > 0

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

    def get_or_start_timer(
        self: DbProtocol,
        user_id: int,
        category: str,
        started_at: datetime,
        note: str | None,
    ) -> tuple[TimerSession | None, TimerSession]:
        if category not in PRODUCTIVE_CATEGORIES and category != "spend":
            category = "build"

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

    def stop_timer(self: DbProtocol, user_id: int) -> TimerSession | None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT user_id, category, note, started_at FROM timer_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if existing is None:
                return None
            conn.execute("DELETE FROM timer_sessions WHERE user_id = ?", (user_id,))
        return _row_to_timer(existing)

    def get_run_minutes_for_timer(self: DbProtocol, user_id: int, now: datetime) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT started_at FROM timer_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return 0
            start_dt = datetime.fromisoformat(str(row["started_at"]))
            return int((now - start_dt).total_seconds() / 60)

    def get_llm_usage(self: DbProtocol, user_id: int, day_key: str) -> LlmUsage:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO llm_usage(user_id, day_key, request_count, last_request_at) VALUES (?, ?, 0, NULL)",
                (user_id, day_key),
            )
            row = conn.execute(
                "SELECT user_id, day_key, request_count, last_request_at FROM llm_usage WHERE user_id = ? AND day_key = ?",
                (user_id, day_key),
            ).fetchone()
        assert row is not None
        return _row_to_llm_usage(row)

    def increment_llm_usage(self: DbProtocol, user_id: int, day_key: str, now: datetime) -> LlmUsage:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO llm_usage(user_id, day_key, request_count, last_request_at) VALUES (?, ?, 0, NULL)",
                (user_id, day_key),
            )
            conn.execute(
                """
                UPDATE llm_usage
                SET request_count = request_count + 1,
                last_request_at = ?
                WHERE user_id = ? AND day_key = ?
                """,
                (now.isoformat(), user_id, day_key),
            )
            row = conn.execute(
                "SELECT user_id, day_key, request_count, last_request_at FROM llm_usage WHERE user_id = ? AND day_key = ?",
                (user_id, day_key),
            ).fetchone()
        assert row is not None
        return _row_to_llm_usage(row)
