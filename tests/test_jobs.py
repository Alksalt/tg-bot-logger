from datetime import datetime
from zoneinfo import ZoneInfo

from tg_time_logger.jobs_runner import evaluate_reminders


def test_inactivity_due_after_20_when_no_productive() -> None:
    now = datetime(2026, 2, 8, 20, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    decision = evaluate_reminders(now, productive_today_minutes=0, daily_goal_minutes=60, has_productive_log_today=False)
    assert decision.inactivity is True


def test_daily_goal_due_after_2130_when_below_goal() -> None:
    now = datetime(2026, 2, 8, 21, 30, tzinfo=ZoneInfo("Europe/Oslo"))
    decision = evaluate_reminders(now, productive_today_minutes=30, daily_goal_minutes=60, has_productive_log_today=True)
    assert decision.daily_goal is True


def test_no_goal_ping_when_goal_met() -> None:
    now = datetime(2026, 2, 8, 22, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    decision = evaluate_reminders(now, productive_today_minutes=60, daily_goal_minutes=60, has_productive_log_today=True)
    assert decision.daily_goal is False
