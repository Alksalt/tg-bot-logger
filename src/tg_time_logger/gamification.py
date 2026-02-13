from __future__ import annotations

import math
import random
from dataclasses import dataclass

PRODUCTIVE_CATEGORIES = ("study", "build", "training", "job")
ALL_CATEGORIES = PRODUCTIVE_CATEGORIES + ("spend",)

FUN_RATE_PER_HOUR = {
    "study": 15,
    "build": 20,
    "training": 20,
    "job": 4,
}

DEFAULT_ECONOMY_TUNING = {
    "fun_rate_study": 15,
    "fun_rate_build": 20,
    "fun_rate_training": 20,
    "fun_rate_job": 4,
    "milestone_block_minutes": 600,
    "milestone_bonus_minutes": 180,
    "xp_level2_base": 300,
    "xp_linear": 80,
    "xp_quadratic": 4,
    "level_bonus_scale_percent": 40,
}

TITLES = {
    1: "Novice",
    2: "Apprentice",
    3: "Initiate",
    4: "Adept",
    5: "Pathfinder",
    6: "Journeyman",
    7: "Artisan",
    8: "Specialist",
    9: "Veteran",
    10: "Expert",
    11: "Sentinel",
    12: "Vanguard",
    13: "Strategist",
    14: "Commander",
    15: "Master",
    16: "Grandmaster",
    17: "Sage",
    18: "Oracle",
    19: "Warden",
    20: "Champion",
    21: "Overlord",
    22: "Titan",
    23: "Mythic",
    24: "Legend",
    25: "Paragon",
    26: "Ascendant",
    27: "Immortal",
    28: "Transcendent",
    29: "Apex",
    30: "Sovereign",
    31: "Eternal",
    32: "Celestial",
    33: "Primordial",
    34: "Infinite",
    35: "Absolute",
    36: "Omega",
    37: "Omega II",
    38: "Omega III",
    39: "Omega IV",
    40: "Omega V",
    41: "Omega Transcendent",
    42: "Omega Ascendant",
    43: "Omega Immortal",
    44: "Omega Eternal",
    45: "Omega Absolute",
    46: "Beyond I",
    47: "Beyond II",
    48: "Beyond III",
    49: "Beyond IV",
    50: "Beyond — The Infinite",
}


@dataclass(frozen=True)
class LevelProgress:
    level: int
    title: str
    current_level_xp: int
    next_level_xp: int
    progress_ratio: float
    remaining_to_next: int


@dataclass(frozen=True)
class EconomyBreakdown:
    base_fun_minutes: int
    milestone_bonus_minutes: int
    level_bonus_minutes: int
    quest_bonus_minutes: int
    wheel_bonus_minutes: int
    earned_fun_minutes: int
    spent_fun_minutes: int
    saved_fun_minutes: int
    remaining_fun_minutes: int


def _effective_tuning(tuning: dict[str, int] | None = None) -> dict[str, int]:
    if not tuning:
        return dict(DEFAULT_ECONOMY_TUNING)
    merged = dict(DEFAULT_ECONOMY_TUNING)
    merged.update(tuning)
    return merged


def fun_from_minutes(category: str, minutes: int, tuning: dict[str, int] | None = None) -> int:
    rates = _effective_tuning(tuning)
    fun_rate = {
        "study": int(rates["fun_rate_study"]),
        "build": int(rates["fun_rate_build"]),
        "training": int(rates["fun_rate_training"]),
        "job": int(rates["fun_rate_job"]),
    }
    if category not in fun_rate:
        return 0
    return max(0, math.floor(minutes * fun_rate[category] / 60))


def xp_for_level(level: int, tuning: dict[str, int] | None = None) -> int:
    cfg = _effective_tuning(tuning)
    if level <= 1:
        return 0
    if level == 2:
        return max(1, int(cfg["xp_level2_base"]))
    k = level - 2
    return (
        int(cfg["xp_level2_base"])
        + (int(cfg["xp_linear"]) * k)
        + (int(cfg["xp_quadratic"]) * k * k)
    )


def total_xp_for_level(level: int, tuning: dict[str, int] | None = None) -> int:
    if level <= 1:
        return 0
    total = 0
    for lvl in range(2, level + 1):
        total += xp_for_level(lvl, tuning=tuning)
    return total


def level_from_xp(total_xp: int, tuning: dict[str, int] | None = None) -> int:
    xp = max(0, total_xp)
    level = 1
    accumulated = 0
    while True:
        next_level = level + 1
        needed = xp_for_level(next_level, tuning=tuning)
        if accumulated + needed > xp:
            break
        accumulated += needed
        level = next_level
    return level


def get_title(level: int) -> str:
    if level >= 50:
        return TITLES[50]
    return TITLES.get(level, f"Level {level}")


def level_progress(total_xp: int, tuning: dict[str, int] | None = None) -> LevelProgress:
    xp = max(0, total_xp)
    level = level_from_xp(xp, tuning=tuning)
    current_floor = total_xp_for_level(level, tuning=tuning)
    next_total = total_xp_for_level(level + 1, tuning=tuning)
    span = max(next_total - current_floor, 1)
    current_level_xp = xp - current_floor
    remaining = max(next_total - xp, 0)
    ratio = current_level_xp / span
    return LevelProgress(
        level=level,
        title=get_title(level),
        current_level_xp=current_level_xp,
        next_level_xp=span,
        progress_ratio=ratio,
        remaining_to_next=remaining,
    )


def streak_multiplier(streak_days: int) -> float:
    if streak_days >= 30:
        return 1.5
    if streak_days >= 14:
        return 1.2
    if streak_days >= 7:
        return 1.1
    return 1.0


def deep_work_multiplier(minutes: int) -> float:
    if minutes >= 120:
        return 1.5
    if minutes >= 90:
        return 1.2
    if minutes >= 45:
        return 1.1
    return 1.0


def calculate_milestone_bonus(productive_minutes: int, tuning: dict[str, int] | None = None) -> tuple[int, int]:
    cfg = _effective_tuning(tuning)
    block_minutes = max(1, int(cfg["milestone_block_minutes"]))
    block_bonus = max(0, int(cfg["milestone_bonus_minutes"]))
    blocks = max(0, productive_minutes) // block_minutes
    return blocks, blocks * block_bonus


def build_economy(
    base_fun_minutes: int,
    productive_minutes: int,
    level_bonus_minutes: int,
    quest_bonus_minutes: int,
    wheel_bonus_minutes: int,
    spent_fun_minutes: int,
    saved_fun_minutes: int,
    tuning: dict[str, int] | None = None,
) -> EconomyBreakdown:
    _, milestone_bonus = calculate_milestone_bonus(productive_minutes, tuning=tuning)
    earned = max(0, base_fun_minutes) + milestone_bonus + max(0, level_bonus_minutes) + max(0, quest_bonus_minutes) + max(0, wheel_bonus_minutes)
    remaining = earned - max(0, spent_fun_minutes) - max(0, saved_fun_minutes)
    return EconomyBreakdown(
        base_fun_minutes=max(0, base_fun_minutes),
        milestone_bonus_minutes=milestone_bonus,
        level_bonus_minutes=max(0, level_bonus_minutes),
        quest_bonus_minutes=max(0, quest_bonus_minutes),
        wheel_bonus_minutes=max(0, wheel_bonus_minutes),
        earned_fun_minutes=earned,
        spent_fun_minutes=max(0, spent_fun_minutes),
        saved_fun_minutes=max(0, saved_fun_minutes),
        remaining_fun_minutes=remaining,
    )


def spin_wheel() -> tuple[str, int]:
    roll = random.random()
    if roll < 0.50:
        return "🎰 Small win!", 30
    if roll < 0.80:
        return "🎰 Medium win!", 60
    if roll < 0.95:
        return "🎰 Big win!", 120
    return "🎰🎰🎰 JACKPOT!", 300


LEVEL_BONUS_MILESTONES = {
    5: 500,
    10: 1200,
    15: 2200,
    20: 3500,
    25: 5200,
    30: 7600,
    35: 10800,
    40: 15000,
    45: 20500,
    50: 28000,
}


def level_up_bonus_minutes(level: int, tuning: dict[str, int] | None = None) -> int:
    cfg = _effective_tuning(tuning)
    lvl = max(1, level)
    base = 60 * lvl
    curve = 5 * lvl * lvl
    milestone = LEVEL_BONUS_MILESTONES.get(lvl, 0)
    raw = base + curve + milestone
    scale = max(0, int(cfg["level_bonus_scale_percent"]))
    return (raw * scale) // 100


def format_minutes_hm(minutes: int) -> str:
    sign = "-" if minutes < 0 else ""
    total = abs(minutes)
    h, m = divmod(total, 60)
    if m == 0:
        return f"{sign}{h}h"
    if h == 0:
        return f"{sign}{m}m"
    return f"{sign}{h}h {m}m"
