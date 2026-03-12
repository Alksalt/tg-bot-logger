from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from tg_time_logger.db import Database
from tg_time_logger.duration import parse_duration_to_minutes
from tg_time_logger.gamification import level_up_bonus_minutes


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_level_up_bonus_formula():
    assert level_up_bonus_minutes(2) == 50
    assert level_up_bonus_minutes(3) == 65
    assert level_up_bonus_minutes(5) == 95
    assert level_up_bonus_minutes(10) == 170
    assert level_up_bonus_minutes(15) == 245
    assert level_up_bonus_minutes(20) == 320


def test_level_up_bonus_minimum_level():
    """Levels below 2 should still return the level-2 bonus (50m)."""
    assert level_up_bonus_minutes(1) == 50
    assert level_up_bonus_minutes(0) == 50


def test_recalculate_level_bonuses(tmp_path):
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 12)

    with db._connect() as conn:
        conn.execute(
            "INSERT INTO level_up_events(user_id, level, bonus_fun_minutes, created_at) VALUES (?, ?, ?, ?)",
            (1, 2, 999, now.isoformat()),
        )
        conn.execute(
            "INSERT INTO level_up_events(user_id, level, bonus_fun_minutes, created_at) VALUES (?, ?, ?, ?)",
            (1, 3, 888, now.isoformat()),
        )

    count = db.recalculate_level_bonuses(1)
    assert count == 2

    events = db.list_level_up_events(1)
    assert events[0].bonus_fun_minutes == 50
    assert events[1].bonus_fun_minutes == 65


def test_set_user_level(tmp_path):
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 12)

    db.add_level_up_event(1, 2, now)
    db.add_level_up_event(1, 3, now)
    assert len(db.list_level_up_events(1)) == 2

    db.set_user_level(1, 5, now)
    events = db.list_level_up_events(1)
    assert len(events) == 4
    assert [e.level for e in events] == [2, 3, 4, 5]
    assert events[0].bonus_fun_minutes == 50
    assert events[3].bonus_fun_minutes == 95


def test_set_user_level_to_one_clears_all(tmp_path):
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 12)
    db.add_level_up_event(1, 2, now)
    db.add_level_up_event(1, 3, now)

    db.set_user_level(1, 1, now)
    assert len(db.list_level_up_events(1)) == 0


def test_update_daily_goal(tmp_path):
    db = Database(tmp_path / "app.db")
    db.get_settings(1)  # ensure row exists
    db.update_daily_goal(1, 120)
    settings = db.get_settings(1)
    assert settings.daily_goal_minutes == 120


def test_settings_goal_duration_parsing():
    """Verify parse_duration_to_minutes handles the formats we advertise."""
    assert parse_duration_to_minutes("2h") == 120
    assert parse_duration_to_minutes("90m") == 90
    assert parse_duration_to_minutes("1h30m") == 90


def test_settings_goal_persists(tmp_path):
    """Full flow: parse duration, update DB, read back."""
    db = Database(tmp_path / "app.db")
    db.get_settings(1)
    minutes = parse_duration_to_minutes("2h")
    db.update_daily_goal(1, minutes)
    assert db.get_settings(1).daily_goal_minutes == 120
