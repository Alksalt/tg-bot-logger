from __future__ import annotations

from types import SimpleNamespace

from tg_time_logger.commands_core import _build_quest_json_repair_prompt, _quest_candidate_tiers


def test_quest_candidate_tiers_with_all_keys() -> None:
    settings = SimpleNamespace(
        openai_api_key="x",
        anthropic_api_key="x",
        google_api_key="x",
        openrouter_api_key="x",
    )
    tiers = ["free", "open_source", "gpt", "gemini", "claude", "top"]
    out = _quest_candidate_tiers(settings, "free", tiers)
    assert out == ["free", "gpt", "claude", "gemini", "open_source", "top"]


def test_quest_candidate_tiers_without_extra_keys() -> None:
    settings = SimpleNamespace(
        openai_api_key=None,
        anthropic_api_key=None,
        google_api_key=None,
        openrouter_api_key=None,
    )
    tiers = ["free", "open_source", "gpt", "gemini", "claude", "top"]
    out = _quest_candidate_tiers(settings, "free", tiers)
    assert out == ["free"]


def test_quest_json_repair_prompt_contains_constraints() -> None:
    prompt = _build_quest_json_repair_prompt(
        raw_answer="Build hard this week",
        difficulty="easy",
        duration_days=3,
        min_target=129,
        reward_lo=13,
        reward_hi=19,
    )
    assert "difficulty must be easy" in prompt
    assert "duration_days must be 3" in prompt
    assert "reward_fun_minutes must be integer in [13, 19]" in prompt
    assert "Source text:" in prompt
