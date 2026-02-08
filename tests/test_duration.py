import pytest

from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("90m", 90),
        ("1.5h", 90),
        ("1h20m", 80),
        ("45", 45),
        ("2h", 120),
    ],
)
def test_parse_duration_valid(raw: str, expected: int) -> None:
    assert parse_duration_to_minutes(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "0", "-10", "1 h", "1m20h"])
def test_parse_duration_invalid(raw: str) -> None:
    with pytest.raises(DurationParseError):
        parse_duration_to_minutes(raw)
