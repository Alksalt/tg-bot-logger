from __future__ import annotations

import re

# Each rule maps a regex pattern to a set of tool tags.
# All matching rules are unioned so a question like
# "search for my notion backup" activates both search and notion tools.

_RULES: list[tuple[re.Pattern[str], set[str]]] = [
    (
        re.compile(
            r"\b(search|google|find online|look up|web|browse|internet|who is|what is .+ currently)\b",
            re.IGNORECASE,
        ),
        {"search", "web"},
    ),
    (
        re.compile(
            r"\b(notion|backup|export|sync|database backup)\b",
            re.IGNORECASE,
        ),
        {"storage", "notion", "backup"},
    ),
    (
        re.compile(
            r"\b(email|mail|send message|inbox)\b",
            re.IGNORECASE,
        ),
        {"communication", "mail"},
    ),
    (
        re.compile(
            r"\b(map|location|directions|geocode|nearby|address)\b",
            re.IGNORECASE,
        ),
        {"maps", "location"},
    ),
    (
        re.compile(
            r"\b(api|http|fetch url|endpoint|webhook)\b",
            re.IGNORECASE,
        ),
        {"http", "api"},
    ),
    (
        re.compile(
            r"\b(history|last week|trend|logged|entries|how much|how many|compare|breakdown)\b",
            re.IGNORECASE,
        ),
        {"data", "stats", "history"},
    ),
    (
        re.compile(
            r"\b(insights|pattern|trend|consistency|best day|worst|improve|bottleneck)\b",
            re.IGNORECASE,
        ),
        {"analytics", "insights"},
    ),
]


def resolve_intent_tags(question: str) -> set[str]:
    """Return the union of all tool tags matching the user's question.

    If no rules match, returns an empty set — the agent will answer
    from context alone with no tools available.
    """
    tags: set[str] = set()
    q = question.strip()
    if not q:
        return tags
    for pattern, rule_tags in _RULES:
        if pattern.search(q):
            tags.update(rule_tags)
    return tags
