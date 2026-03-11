from __future__ import annotations

from typing import Any

STREAK_MINUTES_REQUIRED = 120

APP_CONFIG_DEFAULTS: dict[str, Any] = {
    "feature.reminders_enabled": True,
    "feature.economy_enabled": True,
    "job.sunday_summary_enabled": True,
    "job.reminders_enabled": True,
    "job.daily_digest_enabled": True,
    "economy.fun_rate.study": 15,
    "economy.fun_rate.build": 20,
    "economy.fun_rate.training": 20,
    "economy.fun_rate.job": 4,
    "economy.milestone_block_minutes": 600,
    "economy.milestone_bonus_minutes": 180,
    "economy.xp_level2_base": 300,
    "economy.xp_linear": 80,
    "economy.xp_quadratic": 4,
    "economy.level_bonus_scale_percent": 100,
}

JOB_CONFIG_KEYS = {
    "sunday_summary": "job.sunday_summary_enabled",
    "reminders": "job.reminders_enabled",
    "daily_digest": "job.daily_digest_enabled",
}
