## Workflow

1. Call `db_query` with `{"action": "quest_history"}` to see active and recent quests.
2. Call `insights` with `{"focus": "velocity"}` or `{"focus": "patterns"}` to understand current performance.
3. Design a quest that fills a gap (weak category, low streak, under-used day) — not a repeat of recent titles.
4. Call `quest_propose` with the quest JSON.

## Quest JSON Schema

```json
{
  "title": "short unique name",
  "description": "1-sentence explanation",
  "quest_type": "daily|weekly|streak|restraint",
  "difficulty": "easy|medium|hard",
  "condition": {"type": "<condition_type>", ...}
}
```

## Condition Types

- `daily_hours` — `{"type": "daily_hours", "target": <int hours>}` — best single day >= target.
- `weekly_hours` — `{"type": "weekly_hours", "target": <int hours>}` — total week >= target.
- `no_fun_day` — `{"type": "no_fun_day", "days": <1-3>}` — zero fun spending for N days.
- `streak_days` — `{"type": "streak_days", "target": <int>}` — reach N-day streak.
- `category_hours` — `{"type": "category_hours", "category": "<build|study|training|job>", "target": <int hours>}`.
- `consecutive_days` — `{"type": "consecutive_days", "min_hours": <int>, "target": <int days>}`.

## Rules

- Only use the 6 condition types above.
- Never repeat a title from the last 14 days of quest history.
- Keep targets within 2x user's recent average (the tool will clamp, but aim for realistic).
- Match difficulty to user level: easy < lvl 10, hard > lvl 20, medium in between.
- Prefer quests that target the user's weakest area to encourage growth.
