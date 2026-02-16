from __future__ import annotations

from tg_time_logger.llm_tiers import normalize_tier_input, resolve_available_tier


def test_normalize_tier_input_aliases() -> None:
    assert normalize_tier_input("open_source_cheap") == "open_source"
    assert normalize_tier_input("top_tier") == "top"
    assert normalize_tier_input("open-source") == "open_source"
    assert normalize_tier_input("default") is None


def test_resolve_available_tier() -> None:
    tiers = {"free", "open_source", "gpt", "top"}
    assert resolve_available_tier("free", tiers) == "free"
    assert resolve_available_tier("open_source_cheap", tiers) == "open_source"
    assert resolve_available_tier("top_tier", tiers) == "top"
    assert resolve_available_tier("kimi", tiers) is None

