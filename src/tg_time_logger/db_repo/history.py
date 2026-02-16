from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Protocol

from tg_time_logger.db_converters import _row_to_coach_memory, _row_to_coach_message
from tg_time_logger.db_models import CoachMemory, CoachMessage


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...


class HistoryMixin:
    def add_coach_message(
        self: DbProtocol, user_id: int, role: str, content: str, created_at: datetime
    ) -> CoachMessage:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO coach_messages(user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (user_id, role, content.strip(), created_at.isoformat()),
            )
            row = conn.execute(
                "SELECT * FROM coach_messages WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        assert row is not None
        return _row_to_coach_message(row)

    def list_coach_messages(self: DbProtocol, user_id: int, limit: int = 10) -> list[CoachMessage]:
        """Return last *limit* messages in chronological order (oldest first)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM coach_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                ) sub ORDER BY created_at ASC, id ASC
                """,
                (user_id, max(1, limit)),
            ).fetchall()
        return [_row_to_coach_message(r) for r in rows]

    def prune_coach_messages(self: DbProtocol, user_id: int, keep: int = 20) -> int:
        """Delete oldest messages beyond *keep* count. Returns deleted count."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM coach_messages
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM coach_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                )
                """,
                (user_id, user_id, keep),
            )
        return int(cur.rowcount)

    def clear_coach_messages(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM coach_messages WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)

    # -- Coach Memory (long-term facts) ----------------------------------------

    def add_coach_memory(
        self: DbProtocol,
        user_id: int,
        category: str,
        content: str,
        tags: str | None,
        created_at: datetime,
    ) -> CoachMemory:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO coach_memory(user_id, category, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, category, content.strip(), tags, created_at.isoformat()),
            )
            row = conn.execute(
                "SELECT * FROM coach_memory WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        assert row is not None
        return _row_to_coach_memory(row)

    def list_coach_memories(
        self: DbProtocol, user_id: int, category: str | None = None, limit: int = 50
    ) -> list[CoachMemory]:
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM coach_memory WHERE user_id = ? AND category = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, category, max(1, limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM coach_memory WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, max(1, limit)),
                ).fetchall()
        return [_row_to_coach_memory(r) for r in rows]

    def remove_coach_memory(self: DbProtocol, user_id: int, memory_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM coach_memory WHERE user_id = ? AND id = ?",
                (user_id, memory_id),
            )
        return cur.rowcount > 0

    def clear_coach_memories(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM coach_memory WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)
