from tg_time_logger.agents.orchestration.intent_router import (
    SKILL_DEFS,
    IntentResult,
    resolve_intent,
    resolve_intent_tags,
)


# ---------------------------------------------------------------------------
# Skill matching via resolve_intent
# ---------------------------------------------------------------------------


def test_quest_builder_skill():
    result = resolve_intent("suggest a quest for me")
    assert "quest_builder" in result.skills


def test_quest_builder_keywords():
    for kw in ("quest", "challenge", "new quest", "create quest"):
        result = resolve_intent(f"please {kw}")
        assert "quest_builder" in result.skills, f"Expected quest_builder for '{kw}'"


def test_research_skill():
    result = resolve_intent("research best pomodoro techniques")
    assert "research" in result.skills


def test_research_keywords():
    for kw in ("research", "deep search", "investigate", "find out about", "compare options"):
        result = resolve_intent(f"can you {kw}")
        assert "research" in result.skills, f"Expected research for '{kw}'"


def test_coach_skill():
    result = resolve_intent("give me strategy advice")
    assert "coach" in result.skills


def test_coach_keywords():
    for kw in ("coach", "strategy", "advice", "recommend", "prioritize", "what should I"):
        result = resolve_intent(f"{kw} do next")
        assert "coach" in result.skills, f"Expected coach for '{kw}'"


def test_no_skill_match():
    result = resolve_intent("what's my current level?")
    assert result.skills == []


def test_empty_question():
    result = resolve_intent("")
    assert result.skills == []
    assert result.tool_tags == set()


def test_skill_case_insensitive():
    result = resolve_intent("SUGGEST A QUEST")
    assert "quest_builder" in result.skills


def test_multiple_skills():
    result = resolve_intent("research and suggest a quest")
    assert "research" in result.skills
    assert "quest_builder" in result.skills


def test_no_duplicate_skills():
    result = resolve_intent("quest quest quest quest")
    assert result.skills.count("quest_builder") == 1


# ---------------------------------------------------------------------------
# IntentResult structure
# ---------------------------------------------------------------------------


def test_intent_result_has_tags_and_skills():
    result = resolve_intent("suggest a quest and show me breakdown")
    assert isinstance(result, IntentResult)
    assert isinstance(result.tool_tags, set)
    assert isinstance(result.skills, list)
    assert "quest_builder" in result.skills
    assert "data" in result.tool_tags


# ---------------------------------------------------------------------------
# Backward compat: resolve_intent_tags still returns set[str]
# ---------------------------------------------------------------------------


def test_backward_compat_resolve_intent_tags():
    tags = resolve_intent_tags("show me my entries breakdown")
    assert isinstance(tags, set)
    assert "data" in tags


def test_backward_compat_empty():
    assert resolve_intent_tags("hello") == set()


# ---------------------------------------------------------------------------
# Skill definitions
# ---------------------------------------------------------------------------


def test_skill_defs_have_required_fields():
    for name, skill_def in SKILL_DEFS.items():
        assert skill_def.name == name
        assert skill_def.directive_file.endswith(".md")
        assert isinstance(skill_def.required_tool_tags, frozenset)
        assert len(skill_def.required_tool_tags) > 0


def test_quest_builder_requires_quest_tags():
    qb = SKILL_DEFS["quest_builder"]
    assert "quest" in qb.required_tool_tags
    assert "gamification" in qb.required_tool_tags


def test_research_requires_search_tags():
    r = SKILL_DEFS["research"]
    assert "search" in r.required_tool_tags
    assert "web" in r.required_tool_tags


def test_coach_requires_analytics_tags():
    c = SKILL_DEFS["coach"]
    assert "analytics" in c.required_tool_tags
    assert "insights" in c.required_tool_tags
