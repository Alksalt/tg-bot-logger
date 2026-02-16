from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from tg_time_logger.gamification import level_from_xp, level_up_bonus_minutes


class BaseDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_readonly_query(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """
        Execute a read-only SQL query and return rows as dicts.
        Restricts usage to SELECT statements only.
        """
        normalized = sql.strip().lower()
        if not normalized.startswith("select") and not normalized.startswith("with"):
             # "WITH" Common Table Expressions (CTEs) also start read-only queries usually,
             # but to be safe we might restrict to SELECT/WITH.
             # Simple heuristic: must start with SELECT or WITH.
             # Also check for strictly no usage of INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA/VACUUM?
             # SQLite permissions are per file, so we can't easily restrict the connection itself without
             # using a separate read-only connection string (file:...&mode=ro).
             # For now, simplistic check.
             raise ValueError("Only SELECT queries are allowed.")

        # Ensure we are not tricking the check (e.g. "SELECT 1; DROP TABLE entries;")
        # simplest way is to fetchall.
        with self._connect() as conn:
            # Enforce read-only mode processing if possible, but python sqlite3 doesn't easily support mode=ro uri unless enabled
            # We can use os.path uri.
            # Let's rely on simple string check + catch errors.
            try:
                cursor = conn.execute(sql, params or ())
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                # If it was a multi-statement that failed or something
                raise e


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
                13: """
                    ALTER TABLE user_settings
                    ADD COLUMN sunday_fund_percent INTEGER NOT NULL DEFAULT 0;
                """,
                14: """
                    CREATE TABLE IF NOT EXISTS app_config (
                        key TEXT PRIMARY KEY,
                        value_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        updated_by TEXT
                    );

                    CREATE TABLE IF NOT EXISTS config_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        created_by TEXT,
                        note TEXT
                    );

                    CREATE TABLE IF NOT EXISTS admin_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actor TEXT,
                        action TEXT NOT NULL,
                        target TEXT NOT NULL,
                        payload_json TEXT,
                        created_at TEXT NOT NULL
                    );
                """,
                15: """
                    CREATE TABLE IF NOT EXISTS tool_cache (
                        tool_name TEXT NOT NULL,
                        cache_key TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        fetched_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        PRIMARY KEY(tool_name, cache_key)
                    );
                """,
                16: """
                    ALTER TABLE user_settings
                    ADD COLUMN language_code TEXT NOT NULL DEFAULT 'en';
                """,
                17: """
                    CREATE TABLE IF NOT EXISTS search_provider_stats (
                        provider TEXT PRIMARY KEY,
                        request_count INTEGER NOT NULL DEFAULT 0,
                        success_count INTEGER NOT NULL DEFAULT 0,
                        fail_count INTEGER NOT NULL DEFAULT 0,
                        cache_hit_count INTEGER NOT NULL DEFAULT 0,
                        rate_limit_count INTEGER NOT NULL DEFAULT 0,
                        last_status_code INTEGER,
                        last_error TEXT,
                        last_request_at TEXT,
                        updated_at TEXT NOT NULL
                    );
                """,
                18: """
                    CREATE TABLE IF NOT EXISTS coach_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_coach_messages_user_created
                    ON coach_messages(user_id, created_at DESC);

                    CREATE TABLE IF NOT EXISTS coach_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        category TEXT NOT NULL CHECK(category IN ('preference', 'goal', 'fact', 'context')),
                        content TEXT NOT NULL,
                        tags TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_coach_memory_user_category
                    ON coach_memory(user_id, category);
                """,
                19: """
                    ALTER TABLE user_settings
                    ADD COLUMN preferred_tier TEXT;
                """,
                20: """
                    CREATE TABLE IF NOT EXISTS todo_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        plan_date TEXT NOT NULL,
                        title TEXT NOT NULL,
                        duration_minutes INTEGER,
                        status TEXT NOT NULL DEFAULT 'pending',
                        position INTEGER NOT NULL DEFAULT 0,
                        completed_at TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_todo_items_user_date
                    ON todo_items(user_id, plan_date);
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
