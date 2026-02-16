from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tg_time_logger.db import Database
from tg_time_logger.quests import (
    _validate_llm_quest,
    quest_min_target_minutes,
    quest_reward_bounds,
    sync_quests_for_user,
)


def _dt(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=ZoneInfo("Europe/Oslo"))


def test_difficulty_bounds_scale_with_duration() -> None:
    assert quest_min_target_minutes("easy", 7) == 300
    assert quest_min_target_minutes("medium", 7) == 720
    assert quest_min_target_minutes("hard", 7) == 1200

    lo, hi = quest_reward_bounds("easy", 7)
    assert (lo, hi) == (30, 45)
    lo2, hi2 = quest_reward_bounds("hard", 14)
    assert lo2 >= 240
    assert hi2 >= 360


def test_validate_llm_quest_enforces_reward_penalty_and_min_target() -> None:
    payload = {
        "title": "Build Sprint",
        "description": "Push build output hard.",
        "difficulty": "easy",
        "duration_days": 7,
        "condition": {"type": "total_minutes", "target_minutes": 100, "category": "build"},
        "reward_fun_minutes": 999,  # out of bounds, should clamp
        "penalty_fun_minutes": 1,   # should be replaced by reward
    }
    stats = {"build_share": 0.7, "top_category": "build"}
    validated = _validate_llm_quest(payload, stats, random.Random(7))
    assert validated is not None
    assert validated["condition"]["target_minutes"] >= 300
    assert 30 <= validated["reward_fun_minutes"] <= 45
    assert validated["penalty_fun_minutes"] == validated["reward_fun_minutes"]


def test_sync_quests_applies_penalty_once(tmp_path) -> None:
    db = Database(tmp_path / "app.db")
    user_id = 1
    now = _dt(2026, 2, 16)

    db.insert_quest(
        user_id=user_id,
        title="Expired Hard Quest",
        description="Too hard",
        quest_type="challenge",
        difficulty="hard",
        reward_fun_minutes=120,
        penalty_fun_minutes=120,
        duration_days=7,
        condition={"type": "total_minutes", "target_minutes": 1200, "category": "build"},
        starts_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=2),
        created_at=now - timedelta(days=10),
        source="test",
    )

    first = sync_quests_for_user(db, user_id, now)
    assert len(first.failed) == 1
    assert first.penalty_minutes_applied == 120
    assert db.sum_minutes(user_id, "spend") == 120

    second = sync_quests_for_user(db, user_id, now + timedelta(minutes=1))
    assert len(second.failed) == 0
    assert second.penalty_minutes_applied == 0
    assert db.sum_minutes(user_id, "spend") == 120
