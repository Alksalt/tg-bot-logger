from datetime import datetime
from zoneinfo import ZoneInfo

from tg_time_logger.time_utils import in_quiet_hours, week_range_for


def test_week_range_monday_start_oslo() -> None:
    dt = datetime(2026, 2, 4, 10, 30, tzinfo=ZoneInfo("Europe/Oslo"))  # Wednesday
    week = week_range_for(dt)
    assert week.start.strftime("%Y-%m-%d %H:%M") == "2026-02-02 00:00"
    assert week.end.strftime("%Y-%m-%d %H:%M") == "2026-02-09 00:00"


def test_quiet_hours_across_midnight() -> None:
    dt_inside = datetime(2026, 2, 4, 23, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    dt_inside2 = datetime(2026, 2, 5, 7, 30, tzinfo=ZoneInfo("Europe/Oslo"))
    dt_outside = datetime(2026, 2, 5, 12, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    assert in_quiet_hours(dt_inside, "22:00-08:00") is True
    assert in_quiet_hours(dt_inside2, "22:00-08:00") is True
    assert in_quiet_hours(dt_outside, "22:00-08:00") is False
