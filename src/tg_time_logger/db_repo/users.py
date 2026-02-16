from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any, Protocol

from tg_time_logger.db_converters import _row_to_user_rule, _row_to_plan
from tg_time_logger.db_models import PlanTarget, UserRule, UserSettings


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...
    def ensure_default_shop_items(self, user_id: int, now: datetime) -> None: ...


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
            # Removed redundant INSERT OR IGNORE into user_settings
            # We should probably do it once if not exists, or rely on get_settings to handle it lazily?
            # get_settings handled it lazily via INSERT OR IGNORE.
            # Let's keep it here just in case, but usually we don't need to spam it.
            # Plan says: "Remove redundant 'insert default' logic" -> We remove it from setters.
            # But we must ensure it exists.
            conn.execute(
                "INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)",
                (user_id,),
            )
        self.ensure_default_shop_items(user_id, seen_at)

    def get_all_user_profiles(self: DbProtocol) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.user_id, p.chat_id, p.last_seen_at,
                       s.reminders_enabled, s.daily_goal_minutes, s.quiet_hours,
                       s.shop_budget_minutes, s.auto_save_minutes, s.sunday_fund_percent,
                       s.language_code
                FROM user_profiles p
                LEFT JOIN user_settings s ON s.user_id = p.user_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_settings(self: DbProtocol, user_id: int) -> UserSettings:
        with self._connect() as conn:
            # Keep this one to ensure settings exist when reading
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            row = conn.execute(
                """
                SELECT user_id, reminders_enabled, daily_goal_minutes, quiet_hours,
                       shop_budget_minutes, auto_save_minutes, sunday_fund_percent,
                       language_code, preferred_tier
                FROM user_settings WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        assert row is not None
        return UserSettings(
            user_id=row["user_id"],
            reminders_enabled=bool(row["reminders_enabled"]),
            daily_goal_minutes=row["daily_goal_minutes"],
            quiet_hours=row["quiet_hours"],
            shop_budget_minutes=row["shop_budget_minutes"],
            auto_save_minutes=int(row["auto_save_minutes"] or 0),
            sunday_fund_percent=int(row["sunday_fund_percent"] or 0),
            language_code=str(row["language_code"] or "en"),
            preferred_tier=row["preferred_tier"],
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

    def update_shop_budget(self: DbProtocol, user_id: int, budget_minutes: int | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_settings SET shop_budget_minutes = ? WHERE user_id = ?",
                (budget_minutes, user_id),
            )

    def update_auto_save_minutes(self: DbProtocol, user_id: int, minutes: int) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET auto_save_minutes = ? WHERE user_id = ?",
                (max(0, minutes), user_id),
            )

    def update_sunday_fund_percent(self: DbProtocol, user_id: int, percent: int) -> None:
        allowed = {0, 50, 60, 70}
        normalized = percent if percent in allowed else 0
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET sunday_fund_percent = ? WHERE user_id = ?",
                (normalized, user_id),
            )

    def update_preferred_tier(self: DbProtocol, user_id: int, tier: str | None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET preferred_tier = ? WHERE user_id = ?",
                (tier, user_id),
            )

    def update_language_code(self: DbProtocol, user_id: int, language_code: str) -> None:
        normalized = (language_code or "en").strip().lower()
        if normalized.startswith("uk"):
            normalized = "uk"
        elif normalized.startswith("en"):
            normalized = "en"
        else:
            normalized = "en"
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES (?)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET language_code = ? WHERE user_id = ?",
                (normalized, user_id),
            )

    def set_plan_target(
        self: DbProtocol,
        user_id: int,
        week_start: date,
        total_target_minutes: int,
        study_target_minutes: int = 0,
        build_target_minutes: int = 0,
        training_target_minutes: int = 0,
        job_target_minutes: int = 0,
    ) -> PlanTarget:
        week_key = week_start.isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO plan_targets_v2(
                    user_id, week_start_date, total_target_minutes, study_target_minutes,
                    build_target_minutes, training_target_minutes, job_target_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, week_start_date) DO UPDATE SET
                    total_target_minutes=excluded.total_target_minutes,
                    study_target_minutes=excluded.study_target_minutes,
                    build_target_minutes=excluded.build_target_minutes,
                    training_target_minutes=excluded.training_target_minutes,
                    job_target_minutes=excluded.job_target_minutes
                """,
                (
                    user_id,
                    week_key,
                    total_target_minutes,
                    study_target_minutes,
                    build_target_minutes,
                    training_target_minutes,
                    job_target_minutes,
                ),
            )
            row = conn.execute(
                "SELECT * FROM plan_targets_v2 WHERE user_id = ? AND week_start_date = ?",
                (user_id, week_key),
            ).fetchone()
        assert row is not None
        return _row_to_plan(row)

    def get_plan_target(self: DbProtocol, user_id: int, week_start: date) -> PlanTarget | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM plan_targets_v2 WHERE user_id = ? AND week_start_date = ?",
                (user_id, week_start.isoformat()),
            ).fetchone()
        return _row_to_plan(row) if row else None

    def add_user_rule(self: DbProtocol, user_id: int, rule_text: str, created_at: datetime) -> UserRule:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO user_rules(user_id, rule_text, created_at)
                VALUES (?, ?, ?)
                """,
                (user_id, rule_text.strip(), created_at.isoformat()),
            )
            row = conn.execute("SELECT * FROM user_rules WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_user_rule(row)

    def list_user_rules(self: DbProtocol, user_id: int) -> list[UserRule]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM user_rules
                WHERE user_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (user_id,),
            ).fetchall()
        return [_row_to_user_rule(r) for r in rows]

    def remove_user_rule(self: DbProtocol, user_id: int, rule_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM user_rules WHERE user_id = ? AND id = ?", (user_id, rule_id))
        return cur.rowcount > 0

    def clear_user_rules(self: DbProtocol, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM user_rules WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)
