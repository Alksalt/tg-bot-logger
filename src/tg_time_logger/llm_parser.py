from __future__ import annotations

import json
from dataclasses import dataclass

from tg_time_logger.duration import DurationParseError, parse_duration_to_minutes
from tg_time_logger.service import VALID_CATEGORIES


@dataclass(frozen=True)
class ParsedAction:
    action: str
    category: str | None
    minutes: int
    note: str | None


def parse_free_form_with_llm(
    text: str,
    api_key: str,
) -> ParsedAction | None:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = (
        "Extract a single action from the message as JSON with keys: "
        "action ('log' or 'spend'), category ('work'|'study'|'learn' or null for spend), "
        "duration (string), note (string or null). Return JSON only."
    )

    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    )

    content = (response.output_text or "").strip()
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
    if action == "log" and category not in VALID_CATEGORIES:
        return None
    if action == "spend":
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
