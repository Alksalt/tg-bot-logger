from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES, fun_from_minutes, level_from_xp, level_up_bonus_minutes


@dataclass(frozen=True)
class Entry:
    id: int
    user_id: int
    kind: str
    category: str
    minutes: int
    xp_earned: int
    fun_earned: int
    deep_work_multiplier: float
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
    shop_budget_minutes: int | None
    auto_save_minutes: int


@dataclass(frozen=True)
class PlanTarget:
    user_id: int
    week_start_date: date
    total_target_minutes: int
    study_target_minutes: int
    build_target_minutes: int
    training_target_minutes: int
    job_target_minutes: int


@dataclass(frozen=True)
class LevelUpEvent:
    id: int
    user_id: int
    level: int
    bonus_fun_minutes: int
    created_at: datetime


@dataclass(frozen=True)
class Streak:
    user_id: int
    current_streak: int
    longest_streak: int
    last_productive_date: date | None
    updated_at: datetime


@dataclass(frozen=True)
class Quest:
    id: int
    user_id: int
    title: str
    description: str
    quest_type: str
    difficulty: str
    reward_fun_minutes: int
    condition_json: str
    status: str
    expires_at: datetime
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ShopItem:
    id: int
    user_id: int
    name: str
    emoji: str
    cost_fun_minutes: int
    nok_value: float | None
    active: bool


@dataclass(frozen=True)
class SavingsGoal:
    id: int
    user_id: int
    name: str
    target_fun_minutes: int
    saved_fun_minutes: int
    status: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class LlmUsage:
    user_id: int
    day_key: str
    request_count: int
    last_request_at: datetime | None


@dataclass(frozen=True)
class UserRule:
    id: int
    user_id: int
    rule_text: str
    created_at: datetime


DEFAULT_SHOP_ITEMS: list[tuple[str, str, int, float]] = [
    ("☕", "Nice coffee / tea", 60, 80.0),
    ("🍔", "Burger meal", 200, 180.0),
    ("🍣", "Sushi dinner", 400, 350.0),
    ("🎬", "Movie / streaming night", 150, 130.0),
    ("🎮", "New game (Steam/PS)", 800, 500.0),
    ("📱", "Device fund +500 NOK", 2000, 500.0),
    ("🍕", "Pizza night", 180, 160.0),
    ("🧁", "Cheat meal / dessert", 120, 100.0),
]

STREAK_MINUTES_REQUIRED = 120


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
                2: """
                    ALTER TABLE entries ADD COLUMN kind TEXT;

                    UPDATE entries
                    SET kind = CASE
                        WHEN lower(COALESCE(category, '')) IN ('work', 'study', 'learn') THEN 'productive'
                        WHEN lower(COALESCE(category, '')) = 'spend' THEN 'spend'
                        WHEN lower(COALESCE(entry_type, '')) = 'spend' THEN 'spend'
                        ELSE 'productive'
                    END
                    WHERE kind IS NULL;

                    CREATE INDEX IF NOT EXISTS idx_entries_user_kind_created ON entries(user_id, kind, created_at);
                """,
                3: """
                    ALTER TABLE entries ADD COLUMN xp_earned INTEGER;
                    ALTER TABLE entries ADD COLUMN fun_earned INTEGER;
                    ALTER TABLE entries ADD COLUMN deep_work_multiplier REAL;

                    UPDATE entries
                    SET category = CASE
                        WHEN kind = 'productive' AND (category IS NULL OR trim(category) = '') THEN 'build'
                        WHEN kind = 'spend' THEN 'spend'
                        ELSE category
                    END;

                    UPDATE entries
                    SET xp_earned = CASE
                        WHEN kind = 'productive' THEN minutes
                        ELSE 0
                    END
                    WHERE xp_earned IS NULL;

                    UPDATE entries
                    SET fun_earned = CASE
                        WHEN kind = 'productive' THEN CAST((minutes * 20) / 60 AS INTEGER)
                        ELSE 0
                    END
                    WHERE fun_earned IS NULL;

                    UPDATE entries
                    SET deep_work_multiplier = 1.0
                    WHERE deep_work_multiplier IS NULL;

                    CREATE INDEX IF NOT EXISTS idx_entries_user_category_created ON entries(user_id, category, created_at);
                """,
                4: """
                    CREATE TABLE level_up_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        bonus_fun_minutes INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(user_id, level)
                    );
                """,
                5: """
                    CREATE TABLE streaks (
                        user_id INTEGER PRIMARY KEY,
                        current_streak INTEGER NOT NULL DEFAULT 0,
                        longest_streak INTEGER NOT NULL DEFAULT 0,
                        last_productive_date TEXT,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE streak_freezes (
                        user_id INTEGER NOT NULL,
                        freeze_date TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(user_id, freeze_date)
                    );
                """,
                6: """
                    CREATE TABLE quests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        quest_type TEXT NOT NULL,
                        difficulty TEXT NOT NULL,
                        reward_fun_minutes INTEGER NOT NULL,
                        condition_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        expires_at TEXT NOT NULL,
                        completed_at TEXT,
                        created_at TEXT NOT NULL
                    );
                """,
                7: """
                    CREATE TABLE shop_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        emoji TEXT DEFAULT '🎁',
                        cost_fun_minutes INTEGER NOT NULL,
                        nok_value REAL,
                        active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE redemptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        shop_item_id INTEGER NOT NULL,
                        fun_minutes_spent INTEGER NOT NULL,
                        redeemed_at TEXT NOT NULL,
                        FOREIGN KEY (shop_item_id) REFERENCES shop_items(id)
                    );

                    ALTER TABLE user_settings ADD COLUMN shop_budget_minutes INTEGER;
                    ALTER TABLE user_settings ADD COLUMN auto_save_minutes INTEGER NOT NULL DEFAULT 0;
                """,
                8: """
                    CREATE TABLE wheel_spins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        week_start TEXT NOT NULL,
                        result_fun_minutes INTEGER NOT NULL,
                        spun_at TEXT NOT NULL,
                        UNIQUE(user_id, week_start)
                    );
                """,
                9: """
                    CREATE TABLE savings_goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        target_fun_minutes INTEGER NOT NULL,
                        saved_fun_minutes INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TEXT NOT NULL,
                        completed_at TEXT
                    );
                """,
                10: """
                    CREATE TABLE IF NOT EXISTS plan_targets_v2 (
                        user_id INTEGER NOT NULL,
                        week_start_date TEXT NOT NULL,
                        total_target_minutes INTEGER NOT NULL DEFAULT 0,
                        study_target_minutes INTEGER NOT NULL DEFAULT 0,
                        build_target_minutes INTEGER NOT NULL DEFAULT 0,
                        training_target_minutes INTEGER NOT NULL DEFAULT 0,
                        job_target_minutes INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY(user_id, week_start_date)
                    );

                    INSERT OR IGNORE INTO plan_targets_v2(
                        user_id,
                        week_start_date,
                        total_target_minutes,
                        study_target_minutes,
                        build_target_minutes,
                        training_target_minutes,
                        job_target_minutes
                    )
                    SELECT
                        user_id,
                        week_start_date,
                        COALESCE(work_minutes, 0) + COALESCE(study_minutes, 0) + COALESCE(learn_minutes, 0),
                        COALESCE(study_minutes, 0),
                        COALESCE(work_minutes, 0),
                        COALESCE(learn_minutes, 0),
                        0
                    FROM plan_targets;
                """,
                11: """
                    CREATE TABLE IF NOT EXISTS llm_usage (
                        user_id INTEGER NOT NULL,
                        day_key TEXT NOT NULL,
                        request_count INTEGER NOT NULL DEFAULT 0,
                        last_request_at TEXT,
                        PRIMARY KEY(user_id, day_key)
                    );
                """,
                12: """
                    CREATE TABLE IF NOT EXISTS user_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        rule_text TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_user_rules_user_created
                    ON user_rules(user_id, created_at DESC);
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

            self._backfill_level_up_events(conn, now)
            self._sync_level_up_event_bonuses(conn)

    def _backfill_level_up_events(self, conn: sqlite3.Connection, created_at: str) -> None:
        users = conn.execute(
            """
            SELECT user_id, COALESCE(SUM(COALESCE(xp_earned, minutes)), 0) AS total_xp
            FROM entries
            WHERE kind = 'productive' AND deleted_at IS NULL
            GROUP BY user_id
            """
        ).fetchall()
        for row in users:
            user_id = int(row["user_id"])
            level = level_from_xp(int(row["total_xp"]))
            for lvl in range(2, level + 1):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO level_up_events(user_id, level, bonus_fun_minutes, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, lvl, level_up_bonus_minutes(lvl), created_at),
                )

    def _sync_level_up_event_bonuses(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT id, level, bonus_fun_minutes FROM level_up_events").fetchall()
        for row in rows:
            expected = level_up_bonus_minutes(int(row["level"]))
            if int(row["bonus_fun_minutes"]) != expected:
                conn.execute(
                    "UPDATE level_up_events SET bonus_fun_minutes = ? WHERE id = ?",
                    (expected, row["id"]),
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
                "INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)",
                (user_id,),
            )
        self.ensure_default_shop_items(user_id, seen_at)

    def get_all_user_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.user_id, p.chat_id, p.last_seen_at,
                       s.reminders_enabled, s.daily_goal_minutes, s.quiet_hours,
                       s.shop_budget_minutes, s.auto_save_minutes
                FROM user_profiles p
                LEFT JOIN user_settings s ON s.user_id = p.user_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_settings(self, user_id: int) -> UserSettings:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            row = conn.execute(
                """
                SELECT user_id, reminders_enabled, daily_goal_minutes, quiet_hours,
                       shop_budget_minutes, auto_save_minutes
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
        )

    def update_reminders_enabled(self, user_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET reminders_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id),
            )

    def update_quiet_hours(self, user_id: int, quiet_hours: str | None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET quiet_hours = ? WHERE user_id = ?",
                (quiet_hours, user_id),
            )

    def update_shop_budget(self, user_id: int, budget_minutes: int | None) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET shop_budget_minutes = ? WHERE user_id = ?",
                (budget_minutes, user_id),
            )

    def update_auto_save_minutes(self, user_id: int, minutes: int) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO user_settings(user_id, auto_save_minutes) VALUES (?, 0)", (user_id,))
            conn.execute(
                "UPDATE user_settings SET auto_save_minutes = ? WHERE user_id = ?",
                (max(0, minutes), user_id),
            )

    def add_entry(
        self,
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
        if kind not in {"productive", "spend"}:
            raise ValueError("kind must be productive or spend")

        if kind == "productive":
            normalized_category = category if category in PRODUCTIVE_CATEGORIES else "build"
            default_xp = 0 if normalized_category == "job" else minutes
            computed_xp = max(0, xp_earned if xp_earned is not None else default_xp)
            computed_fun = max(0, fun_earned if fun_earned is not None else fun_from_minutes(normalized_category, minutes))
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

    def update_entry_xp(self, entry_id: int, xp_earned: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE entries SET xp_earned = ? WHERE id = ?", (max(0, xp_earned), entry_id))

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

    def sum_xp(self, user_id: int, start: datetime | None = None, end: datetime | None = None) -> int:
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

    def sum_fun_earned_entries(self, user_id: int, start: datetime | None = None, end: datetime | None = None) -> int:
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

    def sum_level_bonus(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(bonus_fun_minutes), 0) AS total FROM level_up_events WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def sum_completed_quest_rewards(self, user_id: int) -> int:
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

    def sum_wheel_bonus(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(result_fun_minutes), 0) AS total FROM wheel_spins WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def sum_saved_locked(self, user_id: int) -> int:
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

    def sum_productive_by_category(
        self,
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

    def top_category_for_week(self, user_id: int, start: datetime, end: datetime) -> str:
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

    def has_productive_log_between(self, user_id: int, start: datetime, end: datetime) -> bool:
        return self.sum_minutes(user_id, "productive", start=start, end=end) > 0

    def count_deep_sessions(self, user_id: int, start: datetime, end: datetime, minimum_minutes: int = 90) -> int:
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
        self,
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

    def get_plan_target(self, user_id: int, week_start: date) -> PlanTarget | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM plan_targets_v2 WHERE user_id = ? AND week_start_date = ?",
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

    def get_llm_usage(self, user_id: int, day_key: str) -> LlmUsage:
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

    def increment_llm_usage(self, user_id: int, day_key: str, now: datetime) -> LlmUsage:
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

    def get_streak(self, user_id: int, now: datetime) -> Streak:
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

    def has_freeze_on_date(self, user_id: int, freeze_date: date) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM streak_freezes WHERE user_id = ? AND freeze_date = ?",
                (user_id, freeze_date.isoformat()),
            ).fetchone()
        return row is not None

    def create_freeze(self, user_id: int, freeze_date: date, created_at: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO streak_freezes(user_id, freeze_date, created_at) VALUES (?, ?, ?)",
                (user_id, freeze_date.isoformat(), created_at.isoformat()),
            )
        return cur.rowcount > 0

    def refresh_streak(self, user_id: int, now: datetime) -> Streak:
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

    def productive_minutes_for_date(self, user_id: int, day: date, category: str | None = None) -> int:
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        return self.sum_minutes(user_id, "productive", start=start, end=end, category=category)

    def daily_totals(self, user_id: int, kind: str, start_date: date, end_date_exclusive: date, category: str | None = None) -> dict[date, int]:
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

    def max_level_event_level(self, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(level), 1) AS lvl FROM level_up_events WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["lvl"]) if row else 1

    def add_level_up_event(self, user_id: int, level: int, created_at: datetime) -> LevelUpEvent | None:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO level_up_events(user_id, level, bonus_fun_minutes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, level, level_up_bonus_minutes(level), created_at.isoformat()),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM level_up_events WHERE user_id = ? AND level = ?", (user_id, level)).fetchone()
        assert row is not None
        return _row_to_level(row)

    def list_active_quests(self, user_id: int, now: datetime) -> list[Quest]:
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

    def list_quest_history(self, user_id: int, start: datetime, end: datetime) -> list[Quest]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM quests
                WHERE user_id = ?
                  AND status IN ('completed', 'expired', 'failed')
                  AND created_at >= ?
                  AND created_at < ?
                ORDER BY created_at DESC
                """,
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchall()
        return [_row_to_quest(r) for r in rows]

    def list_recent_quest_titles(self, user_id: int, since: datetime) -> set[str]:
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

    def insert_quest(
        self,
        user_id: int,
        title: str,
        description: str,
        quest_type: str,
        difficulty: str,
        reward_fun_minutes: int,
        condition: dict[str, Any],
        expires_at: datetime,
        created_at: datetime,
    ) -> Quest:
        payload = json.dumps(condition)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quests(
                    user_id, title, description, quest_type, difficulty, reward_fun_minutes,
                    condition_json, status, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    user_id,
                    title,
                    description,
                    quest_type,
                    difficulty,
                    reward_fun_minutes,
                    payload,
                    expires_at.isoformat(),
                    created_at.isoformat(),
                ),
            )
            row = conn.execute("SELECT * FROM quests WHERE id = ?", (cur.lastrowid,)).fetchone()
        assert row is not None
        return _row_to_quest(row)

    def update_quest_status(self, quest_id: int, status: str, at: datetime | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE quests SET status = ?, completed_at = ? WHERE id = ?",
                (status, at.isoformat() if at else None, quest_id),
            )

    def ensure_default_shop_items(self, user_id: int, now: datetime) -> None:
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

    def list_shop_items(self, user_id: int, active_only: bool = True) -> list[ShopItem]:
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

    def add_shop_item(self, user_id: int, name: str, emoji: str, cost_fun_minutes: int, nok_value: float | None, created_at: datetime) -> ShopItem:
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

    def deactivate_shop_item(self, user_id: int, item_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE shop_items SET active = 0 WHERE user_id = ? AND id = ?", (user_id, item_id))
        return cur.rowcount > 0

    def find_shop_item(self, user_id: int, identifier: str) -> ShopItem | None:
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

    def add_redemption(self, user_id: int, shop_item_id: int, fun_minutes_spent: int, redeemed_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO redemptions(user_id, shop_item_id, fun_minutes_spent, redeemed_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, shop_item_id, fun_minutes_spent, redeemed_at.isoformat()),
            )

    def list_redemptions(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
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

    def monthly_redemption_minutes(self, user_id: int, year: int, month: int) -> int:
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

    def create_savings_goal(self, user_id: int, name: str, target_fun_minutes: int, created_at: datetime) -> SavingsGoal:
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

    def get_active_savings_goal(self, user_id: int) -> SavingsGoal | None:
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

    def upsert_active_savings_goal(self, user_id: int, name: str, target_fun_minutes: int, now: datetime) -> SavingsGoal:
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

    def list_savings_goals(self, user_id: int, active_only: bool = False) -> list[SavingsGoal]:
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

    def get_savings_goal(self, user_id: int, goal_id: int) -> SavingsGoal | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM savings_goals WHERE user_id = ? AND id = ?",
                (user_id, goal_id),
            ).fetchone()
        return _row_to_savings(row) if row else None

    def deposit_to_savings(self, user_id: int, amount: int, now: datetime) -> SavingsGoal | None:
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

    def withdraw_from_savings(self, user_id: int, amount: int, now: datetime) -> int:
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

    def cancel_savings_goal(self, user_id: int, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE savings_goals SET status = 'cancelled' WHERE user_id = ? AND id = ?",
                (user_id, goal_id),
            )
        return cur.rowcount > 0

    def complete_savings_goal(self, user_id: int, goal_id: int, now: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE savings_goals SET status = 'reached', completed_at = ? WHERE user_id = ? AND id = ?",
                (now.isoformat(), user_id, goal_id),
            )
        return cur.rowcount > 0

    def add_user_rule(self, user_id: int, rule_text: str, created_at: datetime) -> UserRule:
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

    def list_user_rules(self, user_id: int) -> list[UserRule]:
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

    def remove_user_rule(self, user_id: int, rule_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM user_rules WHERE user_id = ? AND id = ?", (user_id, rule_id))
        return cur.rowcount > 0

    def clear_user_rules(self, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM user_rules WHERE user_id = ?", (user_id,))
        return int(cur.rowcount)

    def has_wheel_spin(self, user_id: int, week_start: date) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM wheel_spins WHERE user_id = ? AND week_start = ?",
                (user_id, week_start.isoformat()),
            ).fetchone()
        return row is not None

    def add_wheel_spin(self, user_id: int, week_start: date, result_fun_minutes: int, spun_at: datetime) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO wheel_spins(user_id, week_start, result_fun_minutes, spun_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, week_start.isoformat(), result_fun_minutes, spun_at.isoformat()),
            )
        return cur.rowcount > 0


def _row_to_entry(row: sqlite3.Row) -> Entry:
    kind = row["kind"] if "kind" in row.keys() and row["kind"] else row["entry_type"]
    category = row["category"] or ("spend" if kind == "spend" else "build")
    xp_earned = int(row["xp_earned"] if "xp_earned" in row.keys() and row["xp_earned"] is not None else (row["minutes"] if kind == "productive" else 0))
    fun_earned = int(row["fun_earned"] if "fun_earned" in row.keys() and row["fun_earned"] is not None else 0)
    deep_mult = float(row["deep_work_multiplier"] if "deep_work_multiplier" in row.keys() and row["deep_work_multiplier"] is not None else 1.0)

    return Entry(
        id=row["id"],
        user_id=row["user_id"],
        kind=kind,
        category=category,
        minutes=row["minutes"],
        xp_earned=xp_earned,
        fun_earned=fun_earned,
        deep_work_multiplier=deep_mult,
        note=row["note"],
        created_at=datetime.fromisoformat(row["created_at"]),
        deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        source=row["source"],
    )


def _row_to_timer(row: sqlite3.Row) -> TimerSession:
    return TimerSession(
        user_id=row["user_id"],
        category=row["category"] or "build",
        note=row["note"],
        started_at=datetime.fromisoformat(row["started_at"]),
    )


def _row_to_plan(row: sqlite3.Row) -> PlanTarget:
    return PlanTarget(
        user_id=row["user_id"],
        week_start_date=date.fromisoformat(row["week_start_date"]),
        total_target_minutes=row["total_target_minutes"],
        study_target_minutes=row["study_target_minutes"],
        build_target_minutes=row["build_target_minutes"],
        training_target_minutes=row["training_target_minutes"],
        job_target_minutes=row["job_target_minutes"],
    )


def _row_to_level(row: sqlite3.Row) -> LevelUpEvent:
    return LevelUpEvent(
        id=row["id"],
        user_id=row["user_id"],
        level=row["level"],
        bonus_fun_minutes=row["bonus_fun_minutes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_streak(row: sqlite3.Row) -> Streak:
    return Streak(
        user_id=row["user_id"],
        current_streak=int(row["current_streak"]),
        longest_streak=int(row["longest_streak"]),
        last_productive_date=date.fromisoformat(row["last_productive_date"]) if row["last_productive_date"] else None,
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_quest(row: sqlite3.Row) -> Quest:
    return Quest(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        quest_type=row["quest_type"],
        difficulty=row["difficulty"],
        reward_fun_minutes=row["reward_fun_minutes"],
        condition_json=row["condition_json"],
        status=row["status"],
        expires_at=datetime.fromisoformat(row["expires_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_shop_item(row: sqlite3.Row) -> ShopItem:
    return ShopItem(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        emoji=row["emoji"] or "🎁",
        cost_fun_minutes=row["cost_fun_minutes"],
        nok_value=row["nok_value"],
        active=bool(row["active"]),
    )


def _row_to_savings(row: sqlite3.Row) -> SavingsGoal:
    return SavingsGoal(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        target_fun_minutes=row["target_fun_minutes"],
        saved_fun_minutes=row["saved_fun_minutes"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
    )


def _row_to_llm_usage(row: sqlite3.Row) -> LlmUsage:
    return LlmUsage(
        user_id=row["user_id"],
        day_key=row["day_key"],
        request_count=int(row["request_count"]),
        last_request_at=datetime.fromisoformat(row["last_request_at"]) if row["last_request_at"] else None,
    )


def _row_to_user_rule(row: sqlite3.Row) -> UserRule:
    return UserRule(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        rule_text=str(row["rule_text"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
