from __future__ import annotations

from tg_time_logger.commands_core import _category_picker, _duration_picker


def test_category_picker_without_spend():
    kb = _category_picker("menu:log:cat")
    rows = kb.inline_keyboard
    assert len(rows) == 1
    labels = [btn.text for btn in rows[0]]
    assert labels == ["Study", "Build", "Training", "Job"]
    assert rows[0][0].callback_data == "menu:log:cat:study"
    assert rows[0][1].callback_data == "menu:log:cat:build"


def test_category_picker_with_spend():
    kb = _category_picker("menu:timer:cat", include_spend=True)
    rows = kb.inline_keyboard
    assert len(rows) == 2
    assert rows[1][0].text == "Spend"
    assert rows[1][0].callback_data == "menu:timer:cat:spend"


def test_duration_picker():
    kb = _duration_picker("menu:log:dur:build")
    rows = kb.inline_keyboard
    assert len(rows) == 2
    # First row: 10m, 20m, 30m, 45m
    assert rows[0][0].text == "10m"
    assert rows[0][0].callback_data == "menu:log:dur:build:10"
    assert rows[0][3].text == "45m"
    assert rows[0][3].callback_data == "menu:log:dur:build:45"
    # Second row: 1h, 1.5h, 2h, 3h
    assert rows[1][0].text == "1h"
    assert rows[1][0].callback_data == "menu:log:dur:build:60"
    assert rows[1][3].text == "3h"
    assert rows[1][3].callback_data == "menu:log:dur:build:180"


def test_spend_duration_picker():
    kb = _duration_picker("menu:spend:dur")
    rows = kb.inline_keyboard
    assert rows[0][2].callback_data == "menu:spend:dur:30"
    assert rows[1][1].callback_data == "menu:spend:dur:90"


def test_callback_data_parsing_log():
    """Verify the callback data format can be parsed correctly."""
    data = "menu:log:dur:study:30"
    parts = data.split(":")
    assert parts[0] == "menu"
    assert parts[1] == "log"
    assert parts[2] == "dur"
    assert parts[3] == "study"
    assert int(parts[4]) == 30


def test_callback_data_parsing_spend():
    data = "menu:spend:dur:60"
    minutes = int(data.split(":")[-1])
    assert minutes == 60


def test_callback_data_parsing_timer():
    data = "menu:timer:cat:build"
    cat = data.split(":")[-1]
    assert cat == "build"
