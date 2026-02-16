from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tg_time_logger.db import Database
from tg_time_logger.service import add_productive_entry, compute_status
from tg_time_logger.time_utils import week_start_date

def test_job_economy_isolation(tmp_path):
    db = Database(tmp_path / "app.db")
    user_id = 1
    # Ensure settings exist (defaults)
    db.get_settings(user_id)
    
    now = datetime(2025, 2, 24, 12, 0, tzinfo=ZoneInfo("Europe/Oslo")) # Monday
    
    # 0. Set plan target 120m
    db.set_plan_target(user_id, week_start_date(now), 120)

    # 1. Log 1h Job
    outcome = add_productive_entry(
        db=db, user_id=user_id, minutes=60, category="job", 
        note="Work", created_at=now, source="manual"
    )
    
    # Verify Fun = 4m (1h * 4)
    assert outcome.entry.fun_earned == 4
    # Verify XP = 0
    assert outcome.xp_earned == 0
    # Verify Streak not touched (should be 0 since it wasn't refreshed/started)
    assert outcome.streak.current_streak == 0 
    
    # 2. Log 1h Build (should trigger streak/xp)
    outcome2 = add_productive_entry(
        db=db, user_id=user_id, minutes=60, category="build", 
        note="Code", created_at=now + timedelta(minutes=1), source="manual"
    )
    assert outcome2.entry.fun_earned == 20 # 1h * 20
    assert outcome2.xp_earned == 60 # 1h = 60xp + 0 streak bonus (streak becomes 1 AFTER?)
    # refresh_streak updates streak.
    # 60m < 120m required? STREAK_MINUTES_REQUIRED = 120 in constants.
    # So streak might still be 0 if 60m is not enough?
    # Actually checking constants: `STREAK_MINUTES_REQUIRED = 120`.
    # So 60m build is NOT enough for streak increment.
    # But streak object should be returned.
    
    # 3. Check status view
    view = compute_status(db, user_id, now)
    
    # Total productive min = 60(job) + 60(build) = 120
    assert view.week.productive_minutes == 120
    
    # Plan done should EXCLUDE job. So only 60m (build).
    assert view.week_plan_done_minutes == 60
    
    # Fun earned this week
    # 4 (job) + 20 (build) = 24
    assert view.fun_earned_this_week == 24
