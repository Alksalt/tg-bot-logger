from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

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
            "feature.quests_enabled": False,
            "job.reminders_enabled": False,
        },
        actor="test",
    )
    assert db.is_feature_enabled("quests") is False
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
        quest_bonus_minutes=0,
        wheel_bonus_minutes=0,
        spent_fun_minutes=0,
        saved_fun_minutes=0,
        tuning=tuning,
    )
    # 600 with 300 block = 2 blocks * 90 = 180
    assert eco.milestone_bonus_minutes == 180


def test_snapshot_restore(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    db.set_app_config({"feature.llm_enabled": False}, actor="test")
    sid = db.create_config_snapshot(actor="test")
    db.set_app_config({"feature.llm_enabled": True}, actor="test")
    assert db.is_feature_enabled("llm") is True
    assert db.restore_config_snapshot(sid, actor="test") is True
    assert db.is_feature_enabled("llm") is False


def test_search_provider_stats_counter(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    now = _dt(2026, 2, 11)
    db.record_search_provider_event(
        provider="brave",
        now=now,
        success=True,
        cached=False,
        rate_limited=False,
    )
    db.record_search_provider_event(
        provider="brave",
        now=now,
        success=False,
        cached=False,
        rate_limited=True,
        status_code=429,
        error="HTTP 429",
    )
    rows = db.list_search_provider_stats()
    assert rows
    row = rows[0]
    assert row["provider"] == "brave"
    assert int(row["request_count"]) == 2
    assert int(row["success_count"]) == 1
    assert int(row["fail_count"]) == 1
    assert int(row["rate_limit_count"]) == 1
