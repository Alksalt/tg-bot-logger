from __future__ import annotations

import re
from dataclasses import dataclass, field

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
    (
        re.compile(
            r"\b(todo|to-do|task|plan my day|add task|checklist|to do list)\b",
            re.IGNORECASE,
        ),
        {"todo", "task", "productivity"},
    ),
]


# ---------------------------------------------------------------------------
# Skills: lazy-loaded directive fragments activated by intent matching
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillDef:
    """A skill enriches the agent prompt with a focused directive fragment."""

    name: str
    directive_file: str  # relative to directives dir (e.g. "skills/quest_builder.md")
    required_tool_tags: frozenset[str]  # auto-merged into tool_tags


@dataclass(frozen=True)
class IntentResult:
    """Combined output of intent resolution: tool tags + matched skills."""

    tool_tags: set[str] = field(default_factory=set)
    skills: list[str] = field(default_factory=list)


SKILL_DEFS: dict[str, SkillDef] = {
    "quest_builder": SkillDef(
        name="quest_builder",
        directive_file="skills/quest_builder.md",
        required_tool_tags=frozenset({"data", "stats", "history", "analytics", "insights"}),
    ),
    "research": SkillDef(
        name="research",
        directive_file="skills/research.md",
        required_tool_tags=frozenset({"search", "web"}),
    ),
    "coach": SkillDef(
        name="coach",
        directive_file="skills/coach.md",
        required_tool_tags=frozenset({"data", "stats", "history", "analytics", "insights"}),
    ),
    "db_analyst": SkillDef(
        name="db_analyst",
        directive_file="skills/db_analyst.md",
        # Tag "data" is enough to trigger DbQueryTool, but we want to be explicit.
        required_tool_tags=frozenset({"data", "stats", "history"}),
    ),
}


_SKILL_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(quest|challenge|generate quest|new quest|suggest quest|create quest)\b",
            re.IGNORECASE,
        ),
        "quest_builder",
    ),
    (
        re.compile(
            r"\b(research|deep search|investigate|find out about|compare options)\b",
            re.IGNORECASE,
        ),
        "research",
    ),
    (
        re.compile(
            r"\b(coach|strategy|advice|plan my|recommend|prioritize|what should I)\b",
            re.IGNORECASE,
        ),
        "coach",
    ),
    (
        re.compile(
            r"\b(sql|query database|analyze db|schema|table structure|raw data|count records)\b",
            re.IGNORECASE,
        ),
        "db_analyst",
    ),
]


def resolve_intent_tags(question: str) -> set[str]:
    """Return the union of all tool tags matching the user's question.

    If no rules match, returns an empty set — the agent will answer
    from context alone with no tools available.

    Kept for backward compatibility. Prefer :func:`resolve_intent`.
    """
    return resolve_intent(question).tool_tags


def resolve_intent(question: str) -> IntentResult:
    """Return tool tags *and* matched skill names for a user question."""
    tags: set[str] = set()
    skills: list[str] = []
    q = question.strip()
    if not q:
        return IntentResult(tool_tags=tags, skills=skills)
    for pattern, rule_tags in _RULES:
        if pattern.search(q):
            tags.update(rule_tags)
    seen_skills: set[str] = set()
    for pattern, skill_name in _SKILL_RULES:
        if pattern.search(q) and skill_name not in seen_skills:
            skills.append(skill_name)
            seen_skills.add(skill_name)
    return IntentResult(tool_tags=tags, skills=skills)
