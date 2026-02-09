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


def fun_from_minutes(category: str, minutes: int) -> int:
    if category not in FUN_RATE_PER_HOUR:
        return 0
    return max(0, math.floor(minutes * FUN_RATE_PER_HOUR[category] / 60))


def xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    if level == 2:
        return 300
    k = level - 2
    return 300 + (80 * k) + (4 * k * k)


def total_xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    total = 0
    for lvl in range(2, level + 1):
        total += xp_for_level(lvl)
    return total


def level_from_xp(total_xp: int) -> int:
    xp = max(0, total_xp)
    level = 1
    accumulated = 0
    while True:
        next_level = level + 1
        needed = xp_for_level(next_level)
        if accumulated + needed > xp:
            break
        accumulated += needed
        level = next_level
    return level


def get_title(level: int) -> str:
    if level >= 50:
        return TITLES[50]
    return TITLES.get(level, f"Level {level}")


def level_progress(total_xp: int) -> LevelProgress:
    xp = max(0, total_xp)
    level = level_from_xp(xp)
    current_floor = total_xp_for_level(level)
    next_total = total_xp_for_level(level + 1)
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


def calculate_milestone_bonus(productive_minutes: int) -> tuple[int, int]:
    blocks = max(0, productive_minutes) // 600
    return blocks, blocks * 180


def build_economy(
    base_fun_minutes: int,
    productive_minutes: int,
    level_bonus_minutes: int,
    quest_bonus_minutes: int,
    wheel_bonus_minutes: int,
    spent_fun_minutes: int,
    saved_fun_minutes: int,
) -> EconomyBreakdown:
    _, milestone_bonus = calculate_milestone_bonus(productive_minutes)
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


def level_up_bonus_minutes(level: int) -> int:
    lvl = max(1, level)
    base = 60 * lvl
    curve = 5 * lvl * lvl
    milestone = LEVEL_BONUS_MILESTONES.get(lvl, 0)
    return base + curve + milestone


def format_minutes_hm(minutes: int) -> str:
    sign = "-" if minutes < 0 else ""
    total = abs(minutes)
    h, m = divmod(total, 60)
    if m == 0:
        return f"{sign}{h}h"
    if h == 0:
        return f"{sign}{m}m"
    return f"{sign}{h}h {m}m"
