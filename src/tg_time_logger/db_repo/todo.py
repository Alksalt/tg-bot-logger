from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Protocol

from tg_time_logger.db_converters import _row_to_todo
from tg_time_logger.db_models import TodoItem


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...


class TodoMixin:
    def next_todo_position(self: DbProtocol, user_id: int, plan_date: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(position) AS mx FROM todo_items WHERE user_id = ? AND plan_date = ?",
                (user_id, plan_date),
            ).fetchone()
        if row and row["mx"] is not None:
            return int(row["mx"]) + 1
        return 0

    def add_todo(
        self: DbProtocol,
        user_id: int,
        plan_date: str,
        title: str,
        duration_minutes: int | None,
        position: int,
        now: datetime,
    ) -> TodoItem:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO todo_items(user_id, plan_date, title, duration_minutes, position, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, plan_date, title, duration_minutes, position, now.isoformat()),
            )
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_todo(row)

    def list_todos(self: DbProtocol, user_id: int, plan_date: str) -> list[TodoItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM todo_items WHERE user_id = ? AND plan_date = ? ORDER BY position ASC",
                (user_id, plan_date),
            ).fetchall()
        return [_row_to_todo(r) for r in rows]

    def get_todo(self: DbProtocol, todo_id: int) -> TodoItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (todo_id,)).fetchone()
        return _row_to_todo(row) if row else None

    def mark_todo_done(self: DbProtocol, todo_id: int, now: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE todo_items SET status = 'done', completed_at = ? WHERE id = ? AND status = 'pending'",
                (now.isoformat(), todo_id),
            )
        return cur.rowcount > 0

    def delete_todo(self: DbProtocol, user_id: int, todo_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM todo_items WHERE id = ? AND user_id = ?",
                (todo_id, user_id),
            )
        return cur.rowcount > 0

    def clear_pending_todos(self: DbProtocol, user_id: int, plan_date: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM todo_items WHERE user_id = ? AND plan_date = ? AND status = 'pending'",
                (user_id, plan_date),
            )
        return int(cur.rowcount)
