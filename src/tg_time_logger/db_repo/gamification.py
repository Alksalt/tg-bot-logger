from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from tg_time_logger.db_constants import STREAK_MINUTES_REQUIRED
from tg_time_logger.db_converters import _row_to_level, _row_to_quest, _row_to_streak
from tg_time_logger.db_models import LevelUpEvent, Quest, Streak
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

    def sum_completed_quest_rewards(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(reward_fun_minutes), 0) AS total
                FROM quests
                WHERE user_id = ? AND status = 'completed'
                """,
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def sum_wheel_bonus(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(result_fun_minutes), 0) AS total FROM wheel_spins WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def list_active_quests(self: DbProtocol, user_id: int, now: datetime) -> list[Quest]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM quests
                WHERE user_id = ? AND status = 'active' AND expires_at >= ?
                ORDER BY created_at ASC
                """,
                (user_id, now.isoformat()),
            ).fetchall()
        return [_row_to_quest(r) for r in rows]

    def list_quest_history(self: DbProtocol, user_id: int, start: datetime, end: datetime) -> list[Quest]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM quests
                WHERE user_id = ?
                  AND status IN ('completed', 'expired', 'failed', 'cancelled')
                  AND created_at >= ?
                  AND created_at < ?
                ORDER BY created_at DESC
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchall()
        return [_row_to_quest(r) for r in rows]

    def list_recent_quest_titles(self: DbProtocol, user_id: int, since: datetime) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT title
                FROM quests
                WHERE user_id = ? AND created_at >= ?
                """,
                (user_id, since.isoformat()),
            ).fetchall()
        return {str(r["title"]) for r in rows}

    def list_recent_quests(self: DbProtocol, user_id: int, limit: int = 30) -> list[Quest]:
        capped = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM quests
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, capped),
            ).fetchall()
        return [_row_to_quest(r) for r in rows]

    def insert_quest(
        self: DbProtocol,
        user_id: int,
        title: str,
        description: str,
        quest_type: str,
        difficulty: str,
        reward_fun_minutes: int,
        condition: dict[str, Any],
        expires_at: datetime,
        created_at: datetime,
        starts_at: datetime | None = None,
        duration_days: int = 7,
        penalty_fun_minutes: int | None = None,
        source: str = "manual_llm",
        status: str = "active",
    ) -> Quest:
        payload = json.dumps(condition)
        start_dt = starts_at or created_at
        reward = max(1, int(reward_fun_minutes))
        penalty = reward if penalty_fun_minutes is None else max(0, int(penalty_fun_minutes))
        duration = max(1, int(duration_days))
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quests(
                    user_id, title, description, quest_type, difficulty, reward_fun_minutes,
                    duration_days, penalty_fun_minutes, condition_json,
                    status, starts_at, expires_at, completed_at, failed_at,
                    penalty_applied_at, created_at, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (
                    user_id,
                    title,
                    description,
                    quest_type,
                    difficulty,
                    reward,
                    duration,
                    penalty,
                    payload,
                    status,
                    start_dt.isoformat(),
                    expires_at.isoformat(),
                    created_at.isoformat(),
                    source,
                ),
            )
            row = conn.execute("SELECT * FROM quests WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_quest(row)

    def update_quest_status(self: DbProtocol, quest_id: int, status: str, at: datetime | None = None) -> None:
        ts = at.isoformat() if at else None
        with self._connect() as conn:
            if status == "completed":
                conn.execute(
                    """
                    UPDATE quests
                    SET status = ?, completed_at = ?, failed_at = NULL
                    WHERE id = ?
                    """,
                    (status, ts, quest_id),
                )
                return
            if status in {"failed", "expired"}:
                conn.execute(
                    """
                    UPDATE quests
                    SET status = ?, failed_at = ?, completed_at = NULL
                    WHERE id = ?
                    """,
                    (status, ts, quest_id),
                )
                return
            conn.execute("UPDATE quests SET status = ? WHERE id = ?", (status, quest_id))

    def mark_quest_penalty_applied(self: DbProtocol, quest_id: int, at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE quests SET penalty_applied_at = ? WHERE id = ?",
                (at.isoformat(), quest_id),
            )

    def list_quests_by_status(self: DbProtocol, user_id: int, status: str) -> list[Quest]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM quests
                WHERE user_id = ? AND status = ?
                ORDER BY created_at ASC, id ASC
                """,
                (user_id, status),
            ).fetchall()
        return [_row_to_quest(r) for r in rows]

    def delete_user_quests(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM quests WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)

    def create_quest_proposal(
        self: DbProtocol,
        *,
        user_id: int,
        payload: dict[str, Any],
        created_at: datetime,
        source: str = "llm",
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quest_proposals(
                    user_id, payload_json, status, source, model, prompt_version, created_at
                )
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    user_id,
                    json.dumps(payload),
                    source,
                    model,
                    prompt_version,
                    created_at.isoformat(),
                ),
            )
        return int(cur.lastrowid)

    def get_quest_proposal(self: DbProtocol, proposal_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, payload_json, status, source, model, prompt_version, created_at, responded_at
                FROM quest_proposals
                WHERE id = ?
                """,
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"]))
            if not isinstance(payload, dict):
                payload = {}
        except json.JSONDecodeError:
            payload = {}
        return {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "payload": payload,
            "status": str(row["status"]),
            "source": str(row["source"] or "llm"),
            "model": row["model"],
            "prompt_version": row["prompt_version"],
            "created_at": str(row["created_at"]),
            "responded_at": str(row["responded_at"]) if row["responded_at"] else None,
        }

    def set_quest_proposal_status(self: DbProtocol, proposal_id: int, status: str, now: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE quest_proposals
                SET status = ?, responded_at = ?
                WHERE id = ?
                """,
                (status, now.isoformat(), proposal_id),
            )
        return cur.rowcount > 0

    def clear_user_quest_proposals(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM quest_proposals WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)

    def list_recent_quest_payloads(self: DbProtocol, user_id: int, limit: int = 30) -> list[dict[str, Any]]:
        capped = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json, status, source, model, prompt_version, created_at, responded_at
                FROM quest_proposals
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, capped),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"]))
                if not isinstance(payload, dict):
                    payload = {}
            except json.JSONDecodeError:
                payload = {}
            result.append(
                {
                    "payload": payload,
                    "status": str(row["status"]),
                    "source": str(row["source"] or "llm"),
                    "model": row["model"],
                    "prompt_version": row["prompt_version"],
                    "created_at": str(row["created_at"]),
                    "responded_at": str(row["responded_at"]) if row["responded_at"] else None,
                }
            )
        return result

    def has_wheel_spin(self: DbProtocol, user_id: int, week_start: date) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM wheel_spins WHERE user_id = ? AND week_start = ?",
                (user_id, week_start.isoformat()),
            ).fetchone()
        return row is not None

    def add_wheel_spin(self: DbProtocol, user_id: int, week_start: date, result_fun_minutes: int, spun_at: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO wheel_spins(user_id, week_start, result_fun_minutes, spun_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, week_start.isoformat(), result_fun_minutes, spun_at.isoformat()),
            )
        return cur.rowcount > 0
