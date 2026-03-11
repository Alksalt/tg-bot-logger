from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from tg_time_logger.commands_core import (
    _category_picker,
    _duration_picker,
    handle_callback,
    handle_menu_text,
)
from tg_time_logger.config import Settings
from tg_time_logger.db import Database


TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 3, 10, 10, 0, tzinfo=TZ)


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="test",
        database_path=Path("/tmp/test.db"),
        tz="Europe/Oslo",
        admin_panel_token=None,
        admin_host="127.0.0.1",
        admin_port=8080,
    )


def _make_context(db: Database) -> MagicMock:
    ctx = MagicMock()
    ctx.application.bot_data = {"db": db, "settings": _settings()}
    ctx.user_data = {}
    ctx.args = []
    return ctx


def _make_update(user_id: int = 1, text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = "testuser"
    update.effective_chat.id = user_id

    msg = AsyncMock()
    update.effective_message = msg
    update.effective_message.text = text

    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query_msg = AsyncMock()
        query.message = query_msg
        update.callback_query = query
    else:
        update.callback_query = None

    return update


# ---------------------------------------------------------------------------
# Unit tests for keyboard builders
# ---------------------------------------------------------------------------

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
    assert len(rows) == 3
    assert rows[0][0].text == "10m"
    assert rows[0][0].callback_data == "menu:log:dur:build:10"
    assert rows[0][3].text == "45m"
    assert rows[0][3].callback_data == "menu:log:dur:build:45"
    assert rows[1][0].text == "1h"
    assert rows[1][0].callback_data == "menu:log:dur:build:60"
    assert rows[1][3].text == "3h"
    assert rows[1][3].callback_data == "menu:log:dur:build:180"
    assert rows[2][0].text == "Custom..."
    assert rows[2][0].callback_data == "menu:log:dur:build:custom"


def test_spend_duration_picker():
    kb = _duration_picker("menu:spend:dur")
    rows = kb.inline_keyboard
    assert rows[0][2].callback_data == "menu:spend:dur:30"
    assert rows[1][1].callback_data == "menu:spend:dur:90"


def test_callback_data_parsing_log():
    data = "menu:log:dur:study:30"
    parts = data.split(":")
    assert parts[0] == "menu"
    assert parts[1] == "log"
    assert parts[3] == "study"
    assert int(parts[4]) == 30


def test_callback_data_parsing_spend():
    data = "menu:spend:dur:60"
    assert int(data.split(":")[-1]) == 60


def test_callback_data_parsing_timer():
    data = "menu:timer:cat:build"
    assert data.split(":")[-1] == "build"


# ---------------------------------------------------------------------------
# Integration tests — full menu flows with real DB
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "app.db")


def _patch_now(dt):
    return patch("tg_time_logger.time_utils.now_local", return_value=dt)


@pytest.mark.asyncio
async def test_log_flow_category_then_duration(db):
    """Log button -> category -> duration -> entry in DB."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        # Tap "Log"
        u1 = _make_update(text="Log")
        await handle_menu_text(u1, ctx)
        assert "What did you work on?" in u1.effective_message.reply_text.call_args[0][0]

        # Select "study"
        u2 = _make_update(callback_data="menu:log:cat:study")
        await handle_callback(u2, ctx)
        assert "study" in u2.callback_query.message.edit_text.call_args[0][0].lower()

        # Select "30m"
        u3 = _make_update(callback_data="menu:log:dur:study:30")
        await handle_callback(u3, ctx)

    entries = db.list_recent_entries(1)
    assert len(entries) == 1
    assert entries[0].category == "study"
    assert entries[0].minutes == 30
    assert entries[0].kind == "productive"


@pytest.mark.asyncio
async def test_spend_flow(db):
    """Spend button -> duration -> spend entry in DB."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        u1 = _make_update(text="Spend")
        await handle_menu_text(u1, ctx)

        u2 = _make_update(callback_data="menu:spend:dur:60")
        await handle_callback(u2, ctx)

    entries = db.list_recent_entries(1)
    assert len(entries) == 1
    assert entries[0].kind == "spend"
    assert entries[0].minutes == 60


@pytest.mark.asyncio
async def test_timer_start_and_stop(db):
    """Timer -> category -> stop -> entry in DB, timer cleared."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        u1 = _make_update(text="Timer")
        await handle_menu_text(u1, ctx)

        u2 = _make_update(callback_data="menu:timer:cat:build")
        await handle_callback(u2, ctx)

    assert db.get_active_timer(1) is not None

    stop_time = datetime(2026, 3, 10, 10, 45, tzinfo=TZ)
    with _patch_now(stop_time):
        u3 = _make_update(text="\u23f9 Stop \u00b7 Build \u00b7 45m")
        await handle_menu_text(u3, ctx)

    assert db.get_active_timer(1) is None
    entries = db.list_recent_entries(1)
    assert len(entries) == 1
    assert entries[0].category == "build"
    assert entries[0].minutes == 45


@pytest.mark.asyncio
async def test_custom_duration_flow(db):
    """Log -> category -> custom -> type '2h30m' -> verify 150m entry."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        u1 = _make_update(callback_data="menu:log:cat:training")
        await handle_callback(u1, ctx)

        u2 = _make_update(callback_data="menu:log:dur:training:custom")
        await handle_callback(u2, ctx)
        assert ctx.user_data.get("pending_custom") == {"action": "log", "category": "training"}

        u3 = _make_update(text="2h30m")
        await handle_menu_text(u3, ctx)

    entries = db.list_recent_entries(1)
    assert len(entries) == 1
    assert entries[0].category == "training"
    assert entries[0].minutes == 150
    assert ctx.user_data.get("pending_custom") is None


@pytest.mark.asyncio
async def test_timer_discard(db):
    """Start timer -> discard -> no entry, timer cleared."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        u1 = _make_update(callback_data="menu:timer:cat:study")
        await handle_callback(u1, ctx)
    assert db.get_active_timer(1) is not None

    discard_time = datetime(2026, 3, 10, 10, 30, tzinfo=TZ)
    with _patch_now(discard_time):
        u2 = _make_update(text="\U0001f5d1 Discard")
        await handle_menu_text(u2, ctx)

    assert db.get_active_timer(1) is None
    assert len(db.list_recent_entries(1)) == 0
    reply = u2.effective_message.reply_text.call_args[0][0]
    assert "Discarded" in reply
    assert "study" in reply


@pytest.mark.asyncio
async def test_undo_removes_entry(db):
    """Log an entry -> undo -> entry soft-deleted."""
    ctx = _make_context(db)

    with _patch_now(NOW):
        u1 = _make_update(callback_data="menu:log:dur:build:30")
        await handle_callback(u1, ctx)
    assert len(db.list_recent_entries(1)) == 1

    with _patch_now(NOW):
        u2 = _make_update(text="Undo")
        await handle_menu_text(u2, ctx)

    assert len(db.list_recent_entries(1)) == 0
