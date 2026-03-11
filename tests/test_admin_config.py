from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


from tg_time_logger.db import Database
from tg_time_logger.db_constants import APP_CONFIG_DEFAULTS
from tg_time_logger.gamification import build_economy, fun_from_minutes


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_app_config_defaults_present(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    cfg = db.get_app_config()
    for key in APP_CONFIG_DEFAULTS:
        assert key in cfg


def test_feature_and_job_toggle(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_app_config(
        {
            "feature.economy_enabled": False,
            "job.reminders_enabled": False,
        },
        actor="test",
    )
    assert db.is_feature_enabled("economy") is False
    assert db.is_job_enabled("reminders") is False


def test_tuning_changes_fun_and_milestone(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_app_config(
        {
            "economy.fun_rate.build": 30,
            "economy.milestone_block_minutes": 300,
            "economy.milestone_bonus_minutes": 90,
        },
        actor="test",
    )
    tuning = db.get_economy_tuning()
    assert fun_from_minutes("build", 60, tuning=tuning) == 30
    eco = build_economy(
        base_fun_minutes=60,
        productive_minutes=600,
        level_bonus_minutes=0,
        spent_fun_minutes=0,
        tuning=tuning,
    )
    # 600 with 300 block = 2 blocks * 90 = 180
    assert eco.milestone_bonus_minutes == 180


def test_list_entries_with_deleted(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 10)
    db.add_entry(1, "productive", 60, now, category="build")
    db.add_entry(1, "productive", 30, now, category="study")
    assert len(db.list_entries(1)) == 2
    db.soft_delete_entry(1, deleted_at=now)
    assert len(db.list_entries(1)) == 1
    assert len(db.list_entries(1, include_deleted=True)) == 2


def test_fun_adjustment(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 10)
    entry = db.add_fun_adjustment(1, minutes=50, note="fix balance", created_at=now)
    assert entry.kind == "adjustment"
    assert entry.fun_earned == 50
    assert db.sum_fun_adjustments(1) == 50
    # Negative adjustment
    db.add_fun_adjustment(1, minutes=-20, note="correct", created_at=now)
    assert db.sum_fun_adjustments(1) == 30


def test_list_and_delete_level_up_events(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 10)
    db.add_level_up_event(1, 2, now)
    db.add_level_up_event(1, 3, now)
    events = db.list_level_up_events(1)
    assert len(events) == 2
    assert events[0].level == 2
    db.delete_level_up_event(events[0].id)
    assert len(db.list_level_up_events(1)) == 1


def test_reset_streak(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 3, 10)
    # Create a streak by logging enough productive time
    db.add_entry(1, "productive", 120, now, category="build")
    db.refresh_streak(1, now)
    streak = db.get_streak(1, now)
    assert streak.current_streak == 1
    # Reset
    db.reset_streak(1, now)
    streak = db.get_streak(1, now)
    assert streak.current_streak == 0
    assert streak.last_productive_date is None


def test_snapshot_restore(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_app_config({"feature.reminders_enabled": False}, actor="test")
    sid = db.create_config_snapshot(actor="test")
    db.set_app_config({"feature.reminders_enabled": True}, actor="test")
    assert db.is_feature_enabled("reminders") is True
    assert db.restore_config_snapshot(sid, actor="test") is True
    assert db.is_feature_enabled("reminders") is False


