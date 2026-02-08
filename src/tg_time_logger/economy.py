from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunEconomySnapshot:
    productive_minutes: int
    spent_minutes: int
    base_fun_minutes: int
    bonus_blocks: int
    bonus_fun_minutes: int
    earned_fun_minutes: int
    fun_left_minutes: int


def calculate_fun_economy(productive_minutes: int, spent_minutes: int) -> FunEconomySnapshot:
    productive = max(0, productive_minutes)
    spent = max(0, spent_minutes)

    base_fun = productive // 3
    bonus_blocks = productive // 600
    bonus_fun = bonus_blocks * 180
    earned = base_fun + bonus_fun
    left = earned - spent

    return FunEconomySnapshot(
        productive_minutes=productive,
        spent_minutes=spent,
        base_fun_minutes=base_fun,
        bonus_blocks=bonus_blocks,
        bonus_fun_minutes=bonus_fun,
        earned_fun_minutes=earned,
        fun_left_minutes=left,
    )


def format_minutes_hm(minutes: int) -> str:
    sign = "-" if minutes < 0 else ""
    total = abs(minutes)
    h, m = divmod(total, 60)
    if m == 0:
        return f"{sign}{h}h"
    if h == 0:
        return f"{sign}{m}m"
    return f"{sign}{h}h {m}m"
