# v4.2 — Economy Rebalance + Admin/Settings Power

## Problem

Level-up bonuses are wildly overinflated. At level 10 with 215h productive, the user accumulated 6,860m in level bonuses — more than base fun earned (1,856m) and milestone bonuses (1,080m) combined. The economy feels meaningless when fun minutes pile up faster than they can be spent.

Secondary issues: admin panel lacks level management, and /settings is too limited.

## Design

### 1. Rebalance Level-Up Bonus Formula

**Current formula** in `gamification.py`:
```python
base = 60 * level
curve = 5 * level * level
milestone = LEVEL_BONUS_MILESTONES.get(level, 0)  # 500 at lvl5, 1200 at lvl10, etc.
raw = base + curve + milestone
bonus = (raw * scale_percent) // 100  # scale = 40%
```

Level 10 current: `(600 + 500 + 1200) * 40% = 920m` for a single level-up.

**New formula:**
```python
bonus = 20 + 15 * level
```

No quadratic scaling. No milestone dict. No scale_percent.

| Level | New Bonus | Old Bonus | New Cumulative | Old Cumulative |
|-------|-----------|-----------|----------------|----------------|
| 2     | 50m       | 56m       | 50m            | 56m            |
| 3     | 65m       | 90m       | 115m           | 146m           |
| 5     | 95m       | 370m      | 365m           | 644m           |
| 10    | 170m      | 920m      | 1,225m         | 3,744m         |
| 15    | 245m      | 2,640m    | 2,600m         | ~16,000m       |
| 20    | 320m      | ~4,800m   | 4,500m         | ~40,000m       |

**Files changed:**
- `gamification.py`: Replace `level_up_bonus_minutes()` with `return 20 + 15 * max(2, level)`. Delete `LEVEL_BONUS_MILESTONES` dict. Remove `level_bonus_scale_percent` from `DEFAULT_ECONOMY_TUNING`.
- `db_constants.py`: Remove `economy.level_bonus_scale_percent` from `APP_CONFIG_DEFAULTS`.
- `admin_app.py`: Remove `level_bonus_scale_percent` from economy tuning JS keys.

### 2. Retroactive Recalculation

Existing `level_up_events` rows have `bonus_fun_minutes` baked in from the old formula. Need to update them.

**New admin endpoint:**
```
POST /api/recalculate-level-bonuses
```

Logic:
1. For each user, fetch all `level_up_events`
2. Recalculate `bonus_fun_minutes` using the new formula
3. Update each row
4. Return summary of changes

**Admin UI:** "Recalculate Level Bonuses" button in the admin panel.

**Also add to `db_repo/gamification.py`:**
```python
def recalculate_level_bonuses(self, user_id: int) -> int:
    """Recalculate all level_up_events bonus_fun_minutes. Returns count updated."""
```

### 3. Admin Panel: Set Level

**New admin endpoint:**
```
POST /api/user/{user_id}/set-level  {level: int}
```

Logic:
1. Delete all `level_up_events` for the user
2. Recreate events for levels 2 through `target_level` using new formula
3. Audit log the change

**Admin UI:** Input field + "Set Level" button in User Data section.

Note: This doesn't change XP — it only manages the level_up_events table. The displayed level in /status is derived from XP, not from level_up_events. To truly set level, we'd also need an XP adjustment. Two options:

- **Option A (simple):** Set level only adjusts level_up_events (fun bonuses). Displayed level still comes from XP. If user wants level 8, admin sets level_up_events to 8, and optionally adjusts XP with a fun adjustment entry.
- **Option B (complete):** Add an XP override field to the admin. Create an "xp_adjustment" entry type (like fun_adjustment) that modifies total XP.

**Recommendation:** Option A for now. Level-up events control fun bonuses; XP is derived from entries. If the XP is wrong, delete the bad entries via admin. Simpler, no new entry types.

### 4. More /settings Options

Add to the bot's `/settings` command:

**Daily goal:**
```
/settings goal 2h        → sets daily goal to 120 minutes
/settings goal 90m       → sets daily goal to 90 minutes
```

Currently `daily_goal_minutes` exists in `UserSettings` but there's no way to set it from the bot. The reminder system already uses it.

**Files changed:**
- `commands_settings.py`: Add `goal` action handler. Parse duration with `parse_duration_to_minutes`.
- `db_repo/users.py`: Add `update_daily_goal(user_id, minutes)` method.

### 5. Fix Fun Balance After Rebalance

After recalculating level bonuses, the fun balance changes automatically because `sum_level_bonus()` re-derives from the updated `level_up_events` rows. No separate adjustment needed — the admin "Recalculate" button does it all.

The existing -2,358m adjustment entry stays as-is. After recalculation, if the balance needs further tweaking, use the existing fun adjustment UI.

## Migration Strategy

1. Deploy code changes (new formula, new endpoints)
2. Hit "Recalculate Level Bonuses" in admin panel
3. Check new balance in admin panel
4. Adjust with fun adjustment if needed

No DB schema migration required — just updating `bonus_fun_minutes` values in existing rows.

## Test Plan

- Unit test: `level_up_bonus_minutes(2) == 50`, `level_up_bonus_minutes(10) == 170`
- Unit test: `recalculate_level_bonuses` updates existing rows correctly
- Unit test: set-level endpoint creates correct level_up_events
- Unit test: `/settings goal 2h` sets daily_goal_minutes to 120
- Existing economy tests still pass
- Integration: recalculate via admin API, verify balance changes

## Files Summary

| File | Change |
|------|--------|
| `gamification.py` | New formula, delete LEVEL_BONUS_MILESTONES, remove scale_percent |
| `db_constants.py` | Remove level_bonus_scale_percent default |
| `db_repo/gamification.py` | Add recalculate_level_bonuses(), set_user_level() |
| `db_repo/users.py` | Add update_daily_goal() |
| `admin_app.py` | New endpoints + UI: recalculate, set-level. Remove scale_percent from JS |
| `commands_settings.py` | Add /settings goal handler |
| `tests/test_admin_config.py` | New formula tests, recalculate tests |
| `tests/test_v2_logic.py` | Update level bonus assertions |
