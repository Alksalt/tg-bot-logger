from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


DEFAULT_TZ = "Europe/Oslo"


def oslo_tz() -> ZoneInfo:
    return ZoneInfo(DEFAULT_TZ)


def now_local(tz_name: str = DEFAULT_TZ) -> datetime:
    return datetime.now(tz=ZoneInfo(tz_name))


@dataclass(frozen=True)
class WeekRange:
    start: datetime
    end: datetime


def week_range_for(dt: datetime) -> WeekRange:
    local_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    start = local_midnight - timedelta(days=local_midnight.weekday())
    end = start + timedelta(days=7)
    return WeekRange(start=start, end=end)


def start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_hhmm(value: str) -> time:
    hour_str, minute_str = value.split(":", maxsplit=1)
    hour = int(hour_str)
    minute = int(minute_str)
    return time(hour=hour, minute=minute)


def in_quiet_hours(now: datetime, quiet_range: str | None) -> bool:
    if not quiet_range:
        return False
    try:
        start_raw, end_raw = quiet_range.split("-", maxsplit=1)
        start = parse_hhmm(start_raw)
        end = parse_hhmm(end_raw)
    except Exception:
        return False

    current = now.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def week_start_date(dt: datetime) -> date:
    return week_range_for(dt).start.date()
