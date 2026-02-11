from __future__ import annotations

from tg_time_logger.i18n import normalize_language_code, t


def test_normalize_language_code() -> None:
    assert normalize_language_code("en-US") == "en"
    assert normalize_language_code("uk-UA") == "uk"
    assert normalize_language_code("de") == "en"


def test_translation_fallback() -> None:
    assert "Unknown command" in t("unknown_command", "en")
    assert "Невідома команда" in t("unknown_command", "uk")
    assert t("missing.key", "uk") == "missing.key"

