from __future__ import annotations

from typing import Final

SUPPORTED_LANGUAGES: Final[set[str]] = {"en", "uk"}

MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "unknown_command": "Nothing happened. Unknown command. Use /help to see all commands.",
        "llm_working": "Working on your question...",
        "llm_usage": "Usage: /llm <question about your stats>",
        "llm_disabled_key": "LLM agent is disabled. Set at least one key: OPENROUTER_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, or ANTHROPIC_API_KEY.",
        "lang_show": "Current language: {code}. Supported: en, uk.\nUse /lang en or /lang uk.",
        "lang_set": "Language set to {code}.",
        "lang_usage": "Usage: /lang <en|uk>",
    },
    "uk": {
        "unknown_command": "Нічого не сталося. Невідома команда. Використай /help для списку команд.",
        "llm_working": "Працюю над твоїм запитом...",
        "llm_usage": "Використання: /llm <запит про твою статистику>",
        "llm_disabled_key": "LLM-агент вимкнений. Додай хоча б один ключ: OPENROUTER_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY або ANTHROPIC_API_KEY.",
        "lang_show": "Поточна мова: {code}. Підтримуються: en, uk.\nВикористай /lang en або /lang uk.",
        "lang_set": "Мову змінено на {code}.",
        "lang_usage": "Використання: /lang <en|uk>",
    },
}


def normalize_language_code(raw: str | None, default: str = "en") -> str:
    value = (raw or "").strip().lower()
    if value.startswith("uk"):
        return "uk"
    if value.startswith("en"):
        return "en"
    return default if default in SUPPORTED_LANGUAGES else "en"


def t(key: str, lang: str = "en", **kwargs: object) -> str:
    code = normalize_language_code(lang, default="en")
    template = MESSAGES.get(code, {}).get(key) or MESSAGES["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def localize(lang: str, en: str, uk: str | None = None, **kwargs: object) -> str:
    code = normalize_language_code(lang, default="en")
    template = uk if code == "uk" and uk is not None else en
    try:
        return template.format(**kwargs)
    except Exception:
        return template
