from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tg_time_logger.db import Database
from tg_time_logger.quests import (
    _validate_llm_quest,
    extract_quest_payload,
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


def test_extract_quest_payload_unwraps_answer_wrapper() -> None:
    wrapped = (
        '{"action":"answer","answer":"{\\"title\\":\\"Build Marathon\\",'
        '\\"description\\":\\"Ship one production feature\\",'
        '\\"quest_type\\":\\"challenge\\",'
        '\\"difficulty\\":\\"medium\\",'
        '\\"duration_days\\":7,'
        '\\"condition\\":{\\"type\\":\\"total_minutes\\",\\"target_minutes\\":720,\\"category\\":\\"build\\"},'
        '\\"reward_fun_minutes\\":75,'
        '\\"penalty_fun_minutes\\":75}"}'
    )
    payload = extract_quest_payload(wrapped)
    assert payload is not None
    assert payload["title"] == "Build Marathon"
    assert payload["condition"]["target_minutes"] == 720


def test_extract_quest_payload_handles_json_like_output() -> None:
    raw = """
Here is your quest:
```json
{
  'title': '7-Day Builder Push',
  'description': 'Ship meaningful build output daily.',
  'quest_type': 'challenge',
  'difficulty': 'medium',
  'duration_days': 7,
  'condition': {'type': 'total_minutes', 'target_minutes': 780, 'category': 'build'},
  'reward_fun_minutes': 90,
  'penalty_fun_minutes': 90,
}
```
"""
    payload = extract_quest_payload(raw)
    assert payload is not None
    assert payload["difficulty"] == "medium"
    assert payload["condition"]["category"] == "build"


def test_extract_quest_payload_picks_valid_object_from_multi_object_text() -> None:
    raw = """
Template:
{"title":"template only"}
Final:
{"title":"Execution Ramp","description":"Push build minutes every day.","quest_type":"challenge","difficulty":"easy","duration_days":7,"condition":{"type":"total_minutes","target_minutes":320,"category":"build"},"reward_fun_minutes":35,"penalty_fun_minutes":35}
"""
    payload = extract_quest_payload(raw)
    assert payload is not None
    assert payload["title"] == "Execution Ramp"
