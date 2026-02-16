from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Protocol

from tg_time_logger.db_constants import DEFAULT_SHOP_ITEMS
from tg_time_logger.db_converters import _row_to_savings, _row_to_shop_item
from tg_time_logger.db_models import SavingsGoal, ShopItem


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...


class ShopMixin:
    def ensure_default_shop_items(self: DbProtocol, user_id: int, now: datetime) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM shop_items WHERE user_id = ?", (user_id,)).fetchone()
            if row and int(row["c"]) > 0:
                return
            for emoji, name, cost, nok in DEFAULT_SHOP_ITEMS:
                conn.execute(
                    """
                    INSERT INTO shop_items(user_id, name, emoji, cost_fun_minutes, nok_value, active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (user_id, name, emoji, cost, nok, now.isoformat()),
                )

    def list_shop_items(self: DbProtocol, user_id: int, active_only: bool = True) -> list[ShopItem]:
        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM shop_items WHERE user_id = ? AND active = 1 ORDER BY id ASC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shop_items WHERE user_id = ? ORDER BY id ASC",
                    (user_id,),
                ).fetchall()
        return [_row_to_shop_item(r) for r in rows]

    def add_shop_item(self: DbProtocol, user_id: int, name: str, emoji: str, cost_fun_minutes: int, nok_value: float | None, created_at: datetime) -> ShopItem:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO shop_items(user_id, name, emoji, cost_fun_minutes, nok_value, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (user_id, name, emoji, cost_fun_minutes, nok_value, created_at.isoformat()),
            )
            row = conn.execute("SELECT * FROM shop_items WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_shop_item(row)

    def deactivate_shop_item(self: DbProtocol, user_id: int, item_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE shop_items SET active = 0 WHERE user_id = ? AND id = ?", (user_id, item_id))
        return cur.rowcount > 0

    def find_shop_item(self: DbProtocol, user_id: int, identifier: str) -> ShopItem | None:
        with self._connect() as conn:
            row: sqlite3.Row | None
            if identifier.isdigit():
                row = conn.execute(
                    "SELECT * FROM shop_items WHERE user_id = ? AND id = ? AND active = 1",
                    (user_id, int(identifier)),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM shop_items WHERE user_id = ? AND lower(name) = lower(?) AND active = 1",
                    (user_id, identifier),
                ).fetchone()
        return _row_to_shop_item(row) if row else None

    def add_redemption(self: DbProtocol, user_id: int, shop_item_id: int, fun_minutes_spent: int, redeemed_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO redemptions(user_id, shop_item_id, fun_minutes_spent, redeemed_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, shop_item_id, fun_minutes_spent, redeemed_at.isoformat()),
            )

    def list_redemptions(self: DbProtocol, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.id, r.fun_minutes_spent, r.redeemed_at, s.name, s.emoji
                FROM redemptions r
                LEFT JOIN shop_items s ON s.id = r.shop_item_id
                WHERE r.user_id = ?
                ORDER BY r.redeemed_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def monthly_redemption_minutes(self: DbProtocol, user_id: int, year: int, month: int) -> int:
        prefix = f"{year:04d}-{month:02d}"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(fun_minutes_spent), 0) AS total
                FROM redemptions
                WHERE user_id = ? AND substr(redeemed_at, 1, 7) = ?
                """,
                (user_id, prefix),
            ).fetchone()
        return int(row["total"]) if row else 0

    def create_savings_goal(self: DbProtocol, user_id: int, name: str, target_fun_minutes: int, created_at: datetime) -> SavingsGoal:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO savings_goals(user_id, name, target_fun_minutes, saved_fun_minutes, status, created_at)
                VALUES (?, ?, ?, 0, 'active', ?)
                """,
                (user_id, name, target_fun_minutes, created_at.isoformat()),
            )
            row = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_savings(row)

    def get_active_savings_goal(self: DbProtocol, user_id: int) -> SavingsGoal | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM savings_goals
                WHERE user_id = ? AND status IN ('active', 'reached')
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return _row_to_savings(row) if row else None

    def upsert_active_savings_goal(self: DbProtocol, user_id: int, name: str, target_fun_minutes: int, now: datetime) -> SavingsGoal:
        target = max(1, target_fun_minutes)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM savings_goals
                WHERE user_id = ? AND status IN ('active', 'reached')
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    """
                    INSERT INTO savings_goals(user_id, name, target_fun_minutes, saved_fun_minutes, status, created_at)
                    VALUES (?, ?, ?, 0, 'active', ?)
                    """,
                    (user_id, name, target, now.isoformat()),
                )
                created = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (cur.lastrowid,)).fetchone()
                assert created is not None
                return _row_to_savings(created)

            goal = _row_to_savings(row)
            new_status = "reached" if goal.saved_fun_minutes >= target else "active"
            completed_at = now.isoformat() if new_status == "reached" else None
            conn.execute(
                """
                UPDATE savings_goals
                SET name = ?, target_fun_minutes = ?, status = ?, completed_at = ?
                WHERE id = ?
                """,
                (name, target, new_status, completed_at, goal.id),
            )
            updated = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (goal.id,)).fetchone()
        assert updated is not None
        return _row_to_savings(updated)

    def ensure_fund_goal(self: DbProtocol, user_id: int, now: datetime) -> SavingsGoal:
        goal = self.get_active_savings_goal(user_id)
        if goal:
            return goal
        return self.create_savings_goal(user_id, "Save fund", 1, now)

    def list_savings_goals(self: DbProtocol, user_id: int, active_only: bool = False) -> list[SavingsGoal]:
        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM savings_goals WHERE user_id = ? AND status = 'active' ORDER BY id ASC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM savings_goals WHERE user_id = ? ORDER BY id ASC",
                    (user_id,),
                ).fetchall()
        return [_row_to_savings(r) for r in rows]

    def get_savings_goal(self: DbProtocol, user_id: int, goal_id: int) -> SavingsGoal | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM savings_goals WHERE user_id = ? AND id = ?",
                (user_id, goal_id),
            ).fetchone()
        return _row_to_savings(row) if row else None

    def deposit_to_savings(self: DbProtocol, user_id: int, amount: int, now: datetime) -> SavingsGoal | None:
        if amount <= 0:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM savings_goals
                WHERE user_id = ? AND status IN ('active', 'reached')
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            goal = _row_to_savings(row)
            new_saved = goal.saved_fun_minutes + amount
            new_status = "reached" if new_saved >= goal.target_fun_minutes else "active"
            completed_at = now.isoformat() if new_status == "reached" else None
            conn.execute(
                """
                UPDATE savings_goals
                SET saved_fun_minutes = ?, status = ?, completed_at = ?
                WHERE id = ?
                """,
                (new_saved, new_status, completed_at, goal.id),
            )
            updated = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (goal.id,)).fetchone()
        assert updated is not None
        return _row_to_savings(updated)

    def withdraw_from_savings(self: DbProtocol, user_id: int, amount: int, now: datetime) -> int:
        if amount <= 0:
            return 0
        remaining = amount
        withdrawn = 0
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM savings_goals
                WHERE user_id = ? AND status IN ('active', 'reached') AND saved_fun_minutes > 0
                ORDER BY CASE status WHEN 'reached' THEN 0 ELSE 1 END, id ASC
                """,
                (user_id,),
            ).fetchall()
            for row in rows:
                if remaining <= 0:
                    break
                goal = _row_to_savings(row)
                take = min(remaining, goal.saved_fun_minutes)
                if take <= 0:
                    continue
                new_saved = goal.saved_fun_minutes - take
                if new_saved >= goal.target_fun_minutes:
                    new_status = "reached"
                    completed_at = goal.completed_at.isoformat() if goal.completed_at else now.isoformat()
                else:
                    new_status = "active"
                    completed_at = None
                conn.execute(
                    """
                    UPDATE savings_goals
                    SET saved_fun_minutes = ?, status = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (new_saved, new_status, completed_at, goal.id),
                )
                withdrawn += take
                remaining -= take
        return withdrawn

    def cancel_savings_goal(self: DbProtocol, user_id: int, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE savings_goals SET status = 'cancelled' WHERE user_id = ? AND id = ?",
                (user_id, goal_id),
            )
        return cur.rowcount > 0

    def complete_savings_goal(self: DbProtocol, user_id: int, goal_id: int, now: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE savings_goals SET status = 'reached', completed_at = ? WHERE user_id = ? AND id = ?",
                (now.isoformat(), user_id, goal_id),
            )
        return cur.rowcount > 0

    def sum_saved_locked(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(saved_fun_minutes), 0) AS total
                FROM savings_goals
                WHERE user_id = ? AND status IN ('active', 'reached')
                """,
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0
