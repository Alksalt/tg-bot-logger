from __future__ import annotations

import json
from dataclasses import dataclass

from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.gamification import PRODUCTIVE_CATEGORIES
from tg_time_logger.llm_router import LlmRoute, call_messages


@dataclass(frozen=True)
class ParsedAction:
    action: str
    category: str | None
    minutes: int
    note: str | None


def parse_free_form_with_llm(
    text: str,
    route: LlmRoute,
) -> ParsedAction | None:
    messages = [
        {
            "role": "system",
            "content": (
                "Extract a single action from the message as JSON with keys: "
                "action ('log' or 'spend'), category ('study'|'build'|'training'|'job' or null), "
                "duration (string), note (string or null). Return JSON only."
            ),
        },
        {"role": "user", "content": text},
    ]

    content = call_messages(route, messages, max_tokens=150)
    if not content:
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    action = payload.get("action")
    category = payload.get("category")
    duration = payload.get("duration")
    note = payload.get("note")

    if action not in {"log", "spend"}:
        return None

    if action == "log":
        if category not in PRODUCTIVE_CATEGORIES:
            category = "build"
    else:
        category = None

    if not isinstance(duration, str):
        return None

    try:
        minutes = parse_duration_to_minutes(duration)
    except DurationParseError:
        return None

    if note is not None and not isinstance(note, str):
        note = None

    return ParsedAction(action=action, category=category, minutes=minutes, note=note)
