from __future__ import annotations

import re

DURATION_PATTERN = re.compile(r"^(?:(?P<hours>\d+(?:\.\d+)?)h)?(?:(?P<minutes>\d+)m)?$")


class DurationParseError(ValueError):
    pass


def parse_duration_to_minutes(raw: str) -> int:
    value = raw.strip().lower()
    if not value:
        raise DurationParseError("Duration is required")

    if value.isdigit():
        minutes = int(value)
        if minutes <= 0:
            raise DurationParseError("Duration must be positive")
        return minutes

    if " " in value:
        raise DurationParseError("Use compact duration format like 1h20m")

    if value.endswith("m") and value[:-1].isdigit():
        minutes = int(value[:-1])
        if minutes <= 0:
            raise DurationParseError("Duration must be positive")
        return minutes

    match = DURATION_PATTERN.fullmatch(value)
    if not match:
        raise DurationParseError("Invalid duration format. Examples: 90m, 1.5h, 1h20m, 45")

    hours = float(match.group("hours")) if match.group("hours") else 0.0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    total = int(round(hours * 60)) + minutes

    if total <= 0:
        raise DurationParseError("Duration must be positive")
    return total
