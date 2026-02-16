from __future__ import annotations

from collections.abc import Iterable

# Empty string means "reset to default tier".
_ALIASES: dict[str, str] = {
    "default": "",
    "auto": "",
    "reset": "",
    "none": "",
    "free": "free",
    "open_source": "open_source",
    "open-source": "open_source",
    "opensource": "open_source",
    "kimi": "kimi",
    "deepseek": "deepseek",
    "qwen": "qwen",
    "gpt": "gpt",
    "gpt5": "gpt",
    "gemini": "gemini",
    "claude": "claude",
    "top": "top",
    # Legacy aliases kept for compatibility.
    "open_source_cheap": "open_source",
    "top_tier": "top",
}


def normalize_tier_input(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    key = key.replace(" ", "_")
    mapped = _ALIASES.get(key, key)
    if mapped == "":
        return None
    return mapped


def resolve_available_tier(raw: str | None, available_tiers: Iterable[str]) -> str | None:
    normalized = normalize_tier_input(raw)
    if normalized is None:
        return None
    available = set(available_tiers)
    if normalized in available:
        return normalized
    return None

