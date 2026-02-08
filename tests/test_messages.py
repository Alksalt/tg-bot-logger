from tg_time_logger.economy import calculate_fun_economy
from tg_time_logger.messages import NEGATIVE_WARNING, status_message, week_message
from tg_time_logger.service import PeriodTotals, StatusView


def _view(productive_all: int, spent_all: int) -> StatusView:
    economy = calculate_fun_economy(productive_all, spent_all)
    return StatusView(
        today=PeriodTotals(0, 0),
        week=PeriodTotals(0, 0),
        all_time=PeriodTotals(productive_all, spent_all),
        economy=economy,
    )


def test_status_negative_fun_is_clamped_and_warned() -> None:
    text = status_message(_view(productive_all=0, spent_all=10))
    assert "Fun remaining (all-time): -1m" in text
    assert NEGATIVE_WARNING in text


def test_week_negative_fun_is_clamped_and_warned() -> None:
    text = week_message(_view(productive_all=0, spent_all=10))
    assert "Fun remaining (all-time): -1m" in text
    assert NEGATIVE_WARNING in text
