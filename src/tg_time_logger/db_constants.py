from __future__ import annotations

from typing import Any

DEFAULT_SHOP_ITEMS: list[tuple[str, str, int, float]] = [
    ("\u2615", "Nice coffee / tea", 60, 80.0),
    ("\U0001f354", "Burger meal", 200, 180.0),
    ("\U0001f363", "Sushi dinner", 400, 350.0),
    ("\U0001f3ac", "Movie / streaming night", 150, 130.0),
    ("\U0001f3ae", "New game (Steam/PS)", 800, 500.0),
    ("\U0001f4f1", "Device fund +500 NOK", 2000, 500.0),
    ("\U0001f355", "Pizza night", 180, 160.0),
    ("\U0001f9c1", "Cheat meal / dessert", 120, 100.0),
]

STREAK_MINUTES_REQUIRED = 120

APP_CONFIG_DEFAULTS: dict[str, Any] = {
    "feature.llm_enabled": True,
    "feature.quests_enabled": True,
    "feature.reminders_enabled": True,
    "feature.shop_enabled": True,
    "feature.savings_enabled": True,
    "feature.economy_enabled": True,
    "feature.agent_enabled": True,
    "feature.search_enabled": True,
    "feature.notion_backup_enabled": True,
    "job.sunday_summary_enabled": True,
    "job.reminders_enabled": True,
    "job.midweek_enabled": True,
    "job.notion_backup_enabled": True,
    "economy.fun_rate.study": 15,
    "economy.fun_rate.build": 20,
    "economy.fun_rate.training": 20,
    "economy.fun_rate.job": 4,
    "economy.nok_to_fun_minutes": 3,
    "economy.milestone_block_minutes": 600,
    "economy.milestone_bonus_minutes": 180,
    "economy.xp_level2_base": 300,
    "economy.xp_linear": 80,
    "economy.xp_quadratic": 4,
    "economy.level_bonus_scale_percent": 100,
    "agent.max_steps": 6,
    "agent.max_tool_calls": 4,
    "agent.max_step_input_tokens": 1800,
    "agent.max_step_output_tokens": 420,
    "agent.max_total_tokens": 6000,
    "agent.reasoning_enabled": True,
    "agent.default_tier": "free",
    # Single-user friendly defaults:
    # 0 daily limit = unlimited, 0 cooldown = no enforced delay.
    "llm.daily_limit": 0,
    "llm.cooldown_seconds": 0,
    "search.cache_ttl_seconds": 21600,
    "search.provider_order": "brave,tavily,serper",
    "search.brave_enabled": True,
    "search.tavily_enabled": True,
    "search.serper_enabled": True,
    "i18n.default_language": "en",
}

JOB_CONFIG_KEYS = {
    "sunday_summary": "job.sunday_summary_enabled",
    "reminders": "job.reminders_enabled",
    "midweek": "job.midweek_enabled",
    "notion_backup": "job.notion_backup_enabled",
}
