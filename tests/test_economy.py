from tg_time_logger.gamification import (
    calculate_milestone_bonus,
    deep_work_multiplier,
    fun_from_minutes,
    level_from_xp,
    level_up_bonus_minutes,
    streak_multiplier,
)


def test_milestone_boundary_599() -> None:
    blocks, bonus = calculate_milestone_bonus(599)
    assert blocks == 0
    assert bonus == 0


def test_milestone_boundary_600() -> None:
    blocks, bonus = calculate_milestone_bonus(600)
    assert blocks == 1
    assert bonus == 180


def test_milestone_boundary_1200() -> None:
    blocks, bonus = calculate_milestone_bonus(1200)
    assert blocks == 2
    assert bonus == 360


def test_category_fun_rates() -> None:
    assert fun_from_minutes("study", 60) == 15
    assert fun_from_minutes("build", 60) == 20
    assert fun_from_minutes("training", 60) == 20
    assert fun_from_minutes("job", 60) == 4


def test_level_boundaries() -> None:
    assert level_from_xp(0) == 1
    assert level_from_xp(299) == 1
    assert level_from_xp(300) == 2
    assert level_from_xp(683) == 2
    assert level_from_xp(684) == 3


def test_level_bonus_scales_strongly() -> None:
    assert level_up_bonus_minutes(5) > level_up_bonus_minutes(2)
    assert level_up_bonus_minutes(25) > (level_up_bonus_minutes(5) * 5)


def test_level_milestone_bonus_jumps() -> None:
    assert level_up_bonus_minutes(10) - level_up_bonus_minutes(9) > 500
    assert level_up_bonus_minutes(25) - level_up_bonus_minutes(24) > 1500


def test_streak_multiplier_thresholds() -> None:
    assert streak_multiplier(1) == 1.0
    assert streak_multiplier(7) == 1.1
    assert streak_multiplier(14) == 1.2
    assert streak_multiplier(30) == 1.5


def test_deep_work_multiplier_thresholds() -> None:
    assert deep_work_multiplier(30) == 1.0
    assert deep_work_multiplier(45) == 1.1
    assert deep_work_multiplier(90) == 1.2
    assert deep_work_multiplier(120) == 1.5


def test_level_bonus_default_scale_is_40_percent() -> None:
    val_40 = level_up_bonus_minutes(5)
    val_100 = level_up_bonus_minutes(5, tuning={"level_bonus_scale_percent": 100})
    assert val_40 == (val_100 * 40) // 100


def test_milestone_excludes_job(tmp_path) -> None:
    from datetime import datetime, timezone

    from tg_time_logger.db import Database
    from tg_time_logger.service import add_productive_entry, compute_status

    db = Database(tmp_path / "app.db")
    now = datetime(2026, 2, 12, 12, 0, tzinfo=timezone.utc)
    add_productive_entry(db, 1, 600, "study", None, now, "manual")
    add_productive_entry(db, 1, 600, "job", None, now, "manual")
    view = compute_status(db, 1, now)
    # Only 600m study counts for milestones (1 block = 180 bonus)
    assert view.economy.milestone_bonus_minutes == 180
