from tg_time_logger.gamification import build_economy
from tg_time_logger.messages import NEGATIVE_WARNING, status_message
from tg_time_logger.service import PeriodTotals, StatusView


def _view(productive_all: int, spent_all: int, deep_sessions: int = 0) -> StatusView:
    economy = build_economy(
        base_fun_minutes=0,
        productive_minutes=productive_all,
        level_bonus_minutes=0,
        quest_bonus_minutes=0,
        wheel_bonus_minutes=0,
        spent_fun_minutes=spent_all,
        saved_fun_minutes=0,
    )
    return StatusView(
        today=PeriodTotals(0, 0),
        week=PeriodTotals(0, 0),
        all_time=PeriodTotals(productive_all, spent_all),
        week_categories={"study": 0, "build": 0, "training": 0, "job": 0},
        all_time_categories={"study": 0, "build": 0, "training": 0, "job": 0},
        xp_total=0,
        xp_week=0,
        level=1,
        title="Novice",
        xp_current_level=0,
        xp_next_level=300,
        xp_progress_ratio=0.0,
        xp_remaining_to_next=300,
        streak_current=0,
        streak_longest=0,
        streak_multiplier=1.0,
        deep_sessions_week=deep_sessions,
        active_quests=0,
        week_plan_done_minutes=0,
        week_plan_target_minutes=0,
        week_plan_remaining_minutes=0,
        economy=economy,
    )


def test_status_negative_fun_is_clamped_and_warned() -> None:
    text = status_message(_view(productive_all=0, spent_all=10))
    assert "Remaining: -1m" in text
    assert NEGATIVE_WARNING in text


def test_status_shows_deep_work_sessions() -> None:
    text = status_message(_view(productive_all=0, spent_all=0, deep_sessions=3))
    assert "Deep work" in text
    assert "3" in text
