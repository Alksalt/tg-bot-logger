from __future__ import annotations

from tg_time_logger.help_guides import (
    COMMAND_DESCRIPTIONS,
    GUIDE_PAGES,
    GUIDE_TITLES,
    HELP_TOPICS,
    TOPIC_ALIASES,
    get_guide_page,
    list_guide_topics,
    resolve_guide_topic,
)

ALL_COMMANDS = [
    "log", "spend", "status", "undo", "plan", "start", "timer", "stop",
    "quests", "shop", "notes", "llm", "settings", "todo", "help",
]


# ---------------------------------------------------------------------------
# Guide data integrity
# ---------------------------------------------------------------------------


def test_all_guide_topics_have_titles() -> None:
    for topic in GUIDE_PAGES:
        assert topic in GUIDE_TITLES, f"Missing GUIDE_TITLES entry for '{topic}'"


def test_all_guide_topics_have_at_least_one_page() -> None:
    for topic, pages in GUIDE_PAGES.items():
        assert len(pages) >= 1, f"Guide '{topic}' has no pages"


def test_all_pages_under_telegram_limit() -> None:
    header_budget = 300
    max_len = 4096 - header_budget
    for topic, pages in GUIDE_PAGES.items():
        for i, page in enumerate(pages, 1):
            assert len(page) <= max_len, (
                f"Guide '{topic}' page {i} is {len(page)} chars (max {max_len})"
            )


def test_no_empty_pages() -> None:
    for topic, pages in GUIDE_PAGES.items():
        for i, page in enumerate(pages, 1):
            assert page.strip(), f"Guide '{topic}' page {i} is empty"


def test_guide_topic_count() -> None:
    assert len(GUIDE_PAGES) == 7


# ---------------------------------------------------------------------------
# Accessor functions
# ---------------------------------------------------------------------------


def test_get_guide_page_valid() -> None:
    text, total = get_guide_page("llm", 1)
    assert text is not None
    assert total >= 3


def test_get_guide_page_last() -> None:
    pages = GUIDE_PAGES["llm"]
    text, total = get_guide_page("llm", len(pages))
    assert text is not None
    assert total == len(pages)


def test_get_guide_page_out_of_range() -> None:
    text, total = get_guide_page("llm", 999)
    assert text is None
    assert total > 0


def test_get_guide_page_zero() -> None:
    text, total = get_guide_page("llm", 0)
    assert text is None


def test_get_guide_page_invalid_topic() -> None:
    text, total = get_guide_page("nonexistent", 1)
    assert text is None
    assert total == 0


def test_list_guide_topics_sorted() -> None:
    topics = list_guide_topics()
    assert topics == sorted(topics)
    assert len(topics) == 7


def test_resolve_guide_topic_direct() -> None:
    assert resolve_guide_topic("llm") == "llm"
    assert resolve_guide_topic("quests") == "quests"
    assert resolve_guide_topic("shop") == "shop"
    assert resolve_guide_topic("notes") == "notes"


def test_resolve_guide_topic_aliases() -> None:
    assert resolve_guide_topic("economy") == "shop"
    assert resolve_guide_topic("timer") == "logging"
    assert resolve_guide_topic("coach") == "llm"
    assert resolve_guide_topic("ai") == "llm"
    assert resolve_guide_topic("savings") == "shop"
    assert resolve_guide_topic("language") == "settings"
    assert resolve_guide_topic("rules") == "notes"
    assert resolve_guide_topic("freeze") == "shop"


def test_resolve_guide_topic_strips_slash() -> None:
    assert resolve_guide_topic("/llm") == "llm"
    assert resolve_guide_topic("/log") == "logging"


def test_resolve_guide_topic_unknown() -> None:
    assert resolve_guide_topic("zzznotreal") is None


# ---------------------------------------------------------------------------
# Command descriptions
# ---------------------------------------------------------------------------


def test_all_commands_have_descriptions() -> None:
    for cmd in ALL_COMMANDS:
        assert cmd in COMMAND_DESCRIPTIONS, f"Missing COMMAND_DESCRIPTIONS for '/{cmd}'"


def test_all_commands_have_help_topics() -> None:
    """Every command except 'overview' key should have a HELP_TOPICS entry."""
    for cmd in ALL_COMMANDS:
        assert cmd in HELP_TOPICS, f"Missing HELP_TOPICS entry for '/{cmd}'"


# ---------------------------------------------------------------------------
# Callback data fits Telegram limit
# ---------------------------------------------------------------------------


def test_callback_data_fits_64_bytes() -> None:
    for topic in GUIDE_PAGES:
        for page_num in range(1, len(GUIDE_PAGES[topic]) + 1):
            data = f"guide:{topic}:{page_num}"
            assert len(data.encode("utf-8")) <= 64, (
                f"Callback data '{data}' is {len(data.encode('utf-8'))} bytes"
            )
    assert len("guide:back".encode("utf-8")) <= 64
    assert len("guide:noop".encode("utf-8")) <= 64


# ---------------------------------------------------------------------------
# Alias coverage
# ---------------------------------------------------------------------------


def test_all_alias_values_are_valid_guide_topics() -> None:
    for alias, topic in TOPIC_ALIASES.items():
        assert topic in GUIDE_PAGES, (
            f"Alias '{alias}' maps to '{topic}' which is not in GUIDE_PAGES"
        )
