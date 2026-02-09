from tg_time_logger.gamification import (
    calculate_milestone_bonus,
    deep_work_multiplier,
    fun_from_minutes,
    level_from_xp,
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
    assert level_from_xp(700) == 3


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
