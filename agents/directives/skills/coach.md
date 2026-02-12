## Workflow

1. Call `db_query` with `{"action": "weekly_breakdown", "weeks_back": 4}` for recent trends.
2. Call `insights` (no focus — get full snapshot) for patterns, streak risk, and economy health.
3. Identify 3-5 actionable recommendations based on real data.
4. Present recommendations ordered by impact.

## Rules

- Every recommendation must reference a specific number from the data (e.g., "Your build time dropped 2h vs last week").
- Never give generic advice like "try to be more consistent" without backing data.
- If streak is at risk, always mention it first.
- If economy earn/burn ratio < 1.0, flag overspending.
- Suggest specific categories or time blocks to focus on based on patterns.
- Keep recommendations short — 1-2 sentences each.
