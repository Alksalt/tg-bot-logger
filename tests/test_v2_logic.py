from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from tg_time_logger.db import Database
from tg_time_logger.service import add_productive_entry


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_level_up_event_created_on_boundary(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    outcome = add_productive_entry(
        db=db,
        user_id=1,
        minutes=300,
        category="build",
        note=None,
        created_at=_dt(2026, 2, 9),
        source="manual",
    )
    assert any(e.level == 2 for e in outcome.level_ups)


def test_streak_consecutive_days(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    add_productive_entry(db, 1, 120, "build", None, _dt(2026, 2, 9), "manual")
    out2 = add_productive_entry(db, 1, 120, "build", None, _dt(2026, 2, 10), "manual")
    assert out2.streak.current_streak == 2


def test_streak_freeze_preserves_gap(tmp_path) -> None:
    from datetime import date

    db = Database(tmp_path / "app.db")
    add_productive_entry(db, 1, 120, "build", None, _dt(2026, 2, 9), "manual")
    db.create_freeze(1, date(2026, 2, 10), _dt(2026, 2, 9, 20))
    out = add_productive_entry(db, 1, 120, "build", None, _dt(2026, 2, 11), "manual")
    assert out.streak.current_streak == 2


def test_streak_requires_two_hours_minimum(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    out1 = add_productive_entry(db, 1, 90, "build", None, _dt(2026, 2, 9), "manual")
    out2 = add_productive_entry(db, 1, 90, "build", None, _dt(2026, 2, 10), "manual")
    assert out1.streak.current_streak == 0
    assert out2.streak.current_streak == 0


def test_job_logs_grant_no_xp(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    out = add_productive_entry(db, 1, 180, "job", None, _dt(2026, 2, 9), "manual")
    assert out.entry.xp_earned == 0
    assert out.xp_earned == 0


def test_undo_cleans_up_level_up_events(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    # Log enough XP to reach level 2 (300 XP needed)
    outcome = add_productive_entry(db, 1, 300, "build", None, _dt(2026, 2, 9), "manual")
    assert any(e.level == 2 for e in outcome.level_ups)
    assert db.max_level_event_level(1) == 2

    # Undo the entry
    removed = db.undo_last_entry(1, _dt(2026, 2, 9, 10, 1))
    assert removed is not None

    # Level-up event should be cleaned up (max_level_event_level returns 1 when no events)
    assert db.max_level_event_level(1) == 1  # no level 2 event remains
    assert db.sum_level_bonus(1) == 0  # no bonus fun from level-ups


def test_deep_work_xp_multiplier_applies(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    out = add_productive_entry(
        db=db,
        user_id=1,
        minutes=120,
        category="build",
        note=None,
        created_at=_dt(2026, 2, 9),
        source="timer",
        timer_mode=True,
    )
    assert out.deep_mult == 1.5
    assert out.xp_earned == 180


def test_migration_productive_to_build_category(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            category TEXT,
            minutes INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            deleted_at TEXT,
            source TEXT NOT NULL,
            kind TEXT
        );

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
        """
    )
    conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2026-01-01T00:00:00')")
    conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (2, '2026-01-01T00:01:00')")
    conn.execute(
        """
        INSERT INTO entries(user_id, entry_type, category, minutes, note, created_at, deleted_at, source, kind)
        VALUES (1, 'productive', NULL, 90, 'legacy', '2026-02-01T10:00:00+01:00', NULL, 'manual', 'productive')
        """
    )
    conn.commit()
    conn.close()

    db = Database(db_path)
    # Migration should have defaulted legacy productive to build.
    with db._connect() as check_conn:
        row = check_conn.execute("SELECT category, kind FROM entries LIMIT 1").fetchone()
    assert row["kind"] == "productive"
    assert row["category"] == "build"
