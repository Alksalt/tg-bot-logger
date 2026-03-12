from __future__ import annotations

# ---------------------------------------------------------------------------
# Command descriptions (one-liner per command, used in /help overview)
# ---------------------------------------------------------------------------

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "start": "Welcome / onboarding",
    "log": "Log productive time or other activities",
    "spend": "Log fun/consumption time",
    "timer": "Start a timer session (/t shortcut)",
    "stop": "Stop an active timer and log time",
    "status": "Show level, XP, streak, economy summary",
    "undo": "Undo your last log entry",
    "help": "Show help or detailed command docs",
    "settings": "Reminders, quiet hours, daily goal, unspend",
}


# ---------------------------------------------------------------------------
# Per-command help text (shown by /help <command>)
# ---------------------------------------------------------------------------

HELP_TOPICS: dict[str, str] = {
    "log": (
        "/log <duration> [study|build|training|job] [note]\n"
        "/log <duration> other <description>\n"
        "Logs productive time or other activities.\n\n"
        "Productive examples:\n"
        "- /log 90m\n"
        "- /log 1.5h build API refactor\n"
        "- /log 1h20m study chapter 3\n\n"
        "Other (no XP/fun, visible in logs):\n"
        "- /log 30m other morning walk\n"
        "- /log 20m other breakfast\n"
        "- /log 8h other sleep"
    ),
    "spend": (
        "/spend <duration> [note]\n"
        "Logs fun consumption time.\n\n"
        "Examples:\n"
        "- /spend 40m YouTube\n"
        "- /spend 2h movie night"
    ),
    "status": (
        "/status\n"
        "Shows level, XP, streak, week totals, deep work sessions, and economy."
    ),
    "undo": (
        "/undo\n"
        "Soft-deletes your last entry (productive or spend)."
    ),
    "start": (
        "/start\n"
        "Welcome / onboarding message with quick-start tips."
    ),
    "timer": (
        "/timer [study|build|training|job|spend] [note]\n"
        "/t [study|build|training|job|spend] [note]\n"
        "Starts a timer session. Use the STOP button or /stop to finish.\n\n"
        "Example:\n"
        "- /timer build backend cleanup\n"
        "- /t study\n"
        "- /timer spend games"
    ),
    "stop": (
        "/stop\n"
        "Stops active timer and logs elapsed minutes.\n"
        "Productive timers give XP/fun; spend timers log fun spend."
    ),
    "settings": (
        "/settings -- show all current settings\n"
        "/settings reminders <on|off> -- toggle reminders\n"
        "/settings quiet <HH:MM-HH:MM> -- set quiet hours\n"
        "/settings goal <duration> -- set daily goal (2h, 90m)\n"
        "/settings unspend <amount> -- deduct fun minutes"
    ),
    "help": (
        "/help\n"
        "/help <command>\n"
        "Shows global help or detailed docs for one command."
    ),
}


# ---------------------------------------------------------------------------
# Topic aliases (keyword -> guide key)
# ---------------------------------------------------------------------------

TOPIC_ALIASES: dict[str, str] = {
    "log": "time_tracking",
    "logging": "time_tracking",
    "spend": "time_tracking",
    "timer": "time_tracking",
    "stop": "time_tracking",
    "time": "time_tracking",
    "start": "getting_started",
    "getting_started": "getting_started",
    "onboarding": "getting_started",
    "economy": "economy",
    "fun": "economy",
    "balance": "economy",
    "level": "leveling",
    "leveling": "leveling",
    "xp": "leveling",
    "streak": "leveling",
    "settings": "settings",
    "reminders": "settings",
    "quiet_hours": "settings",
    "unspend": "settings",
    "goal": "settings",
}


# ---------------------------------------------------------------------------
# Guide display names
# ---------------------------------------------------------------------------

GUIDE_TITLES: dict[str, str] = {
    "getting_started": "Getting Started",
    "time_tracking": "Time Tracking Guide",
    "economy": "Economy Guide",
    "leveling": "Leveling & XP Guide",
    "settings": "Settings Guide",
}


# ---------------------------------------------------------------------------
# Guide pages (each topic -> list of page strings)
# ---------------------------------------------------------------------------

_GETTING_STARTED_PAGES: list[str] = [
    (
        "Getting Started\n"
        "\n"
        "This bot tracks how you spend your time and rewards "
        "productive work with fun time.\n"
        "\n"
        "The core loop:\n"
        "  1. Log productive time (study, build, training, job)\n"
        "  2. Earn fun minutes as a reward\n"
        "  3. Spend fun minutes on leisure activities\n"
        "  4. Level up and earn XP as you go\n"
        "\n"
        "Quick start:\n"
        "  /log 30m study -- log 30 min of study\n"
        "  /timer study   -- start a live timer\n"
        "  /spend 1h      -- log 1h of fun time\n"
        "  /status        -- see your progress\n"
        "\n"
        "You can also use the reply keyboard buttons:\n"
        "  [Log] [Spend] [Timer] -- tap to pick category/duration\n"
        "  [Status] [Undo]       -- quick access"
    ),
]


_TIME_TRACKING_PAGES: list[str] = [
    # Page 1: Logging productive time
    (
        "Logging Productive Time\n"
        "\n"
        "Command:\n"
        "  /log <duration> [category] [note]\n"
        "\n"
        "Duration formats (all equivalent for 90 minutes):\n"
        "  /log 90m\n"
        "  /log 1.5h\n"
        "  /log 1h30m\n"
        "  /log 90\n"
        "\n"
        "Categories:\n"
        "  study    - Learning, reading, courses\n"
        "  build    - Creating, coding, projects (default)\n"
        "  training - Exercise, practice, drills\n"
        "  job      - Work, employment tasks\n"
        "\n"
        "With notes:\n"
        "  /log 2h study chapter 5 of ML book\n"
        "  /log 45m build fixed login bug\n"
        "  /log 1h training gym workout\n"
        "\n"
        "Other activities (no XP, no fun -- just context):\n"
        "  /log 30m other morning walk\n"
        "  /log 8h other sleep"
    ),

    # Page 2: Fun time + timer
    (
        "Fun Time & Timer Mode\n"
        "\n"
        "Log fun time:\n"
        "  /spend <duration> [note]\n"
        "  /spend 40m YouTube\n"
        "  /spend 2h movie night\n"
        "\n"
        "Timer mode:\n"
        "  /timer [category] [note]   Start timer\n"
        "  /t study                   Shortcut\n"
        "  /stop                      Stop and log\n"
        "\n"
        "Use the STOP button on the keyboard or /stop.\n"
        "\n"
        "Deep work bonus:\n"
        "  Timer sessions of 60+ minutes earn extra XP.\n"
        "\n"
        "Undo a mistake:\n"
        "  /undo\n"
        "  Removes your last log entry (productive or spend)."
    ),

    # Page 3: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Log productive time:\n"
        "  /log <duration> [study|build|training|job] [note]\n"
        "\n"
        "Log other activities (no XP/fun):\n"
        "  /log <duration> other <description>\n"
        "\n"
        "Log fun time:\n"
        "  /spend <duration> [note]\n"
        "\n"
        "Timer:\n"
        "  /timer [category] [note]\n"
        "  /t [category] [note]\n"
        "  /stop\n"
        "\n"
        "Undo: /undo\n"
        "View progress: /status\n"
        "\n"
        "Duration formats: 90m, 1.5h, 1h30m, 90\n"
        "Categories: study, build (default), training, job"
    ),
]


_ECONOMY_PAGES: list[str] = [
    (
        "How the Economy Works\n"
        "\n"
        "The bot has a built-in economy based on time:\n"
        "\n"
        "Earning:\n"
        "  - Log productive time (study, build, training, job)\n"
        "  - You earn \"fun minutes\" based on the category\n"
        "  - Level-up bonuses add more\n"
        "\n"
        "Fun rates per hour:\n"
        "  build    - 20m fun/hour\n"
        "  study    - 15m fun/hour\n"
        "  training - 20m fun/hour\n"
        "  job      - 4m fun/hour (no XP, no streak)\n"
        "\n"
        "Spending:\n"
        "  - Log fun time with /spend\n"
        "  - Use /settings unspend to manually deduct\n"
        "\n"
        "The idea: productive work earns guilt-free leisure time.\n"
        "\n"
        "Check your balance:\n"
        "  /status -- shows current fun minutes remaining"
    ),
]


_LEVELING_PAGES: list[str] = [
    # Page 1: XP and levels
    (
        "XP & Levels\n"
        "\n"
        "You earn XP for every productive minute logged.\n"
        "XP requirements scale quadratically with level.\n"
        "\n"
        "Multipliers that boost XP:\n"
        "  Streak multiplier -- consecutive active days\n"
        "  Deep work bonus   -- timer sessions 60+ minutes\n"
        "\n"
        "Level-up rewards:\n"
        "  Each level grants a fun minute bonus (20 + 15 per level).\n"
        "  Higher levels unlock new titles.\n"
        "\n"
        "Note: job category earns fun minutes but no XP."
    ),

    # Page 2: Streaks
    (
        "Streaks\n"
        "\n"
        "Log at least one productive session per day to keep\n"
        "your streak alive.\n"
        "\n"
        "Streak multiplier grows with consecutive days:\n"
        "  1-2 days  -- 1.0x\n"
        "  3-6 days  -- 1.1x\n"
        "  7-13 days -- 1.2x\n"
        "  14+ days  -- 1.3x\n"
        "  30+ days  -- 1.5x\n"
        "\n"
        "If you miss a day, the streak resets to 0.\n"
        "\n"
        "Your longest streak is tracked in /status."
    ),
]


_SETTINGS_PAGES: list[str] = [
    (
        "Settings Overview\n"
        "\n"
        "View all settings:\n"
        "  /settings\n"
        "\n"
        "Reminders:\n"
        "  /settings reminders on    Enable reminders\n"
        "  /settings reminders off   Disable reminders\n"
        "\n"
        "Quiet hours (no reminders during this window):\n"
        "  /settings quiet 22:00-08:00\n"
        "  /settings quiet 23:00-07:00\n"
        "\n"
        "Daily goal:\n"
        "  /settings goal 2h         Set daily goal to 2 hours\n"
        "  /settings goal 90m        Set daily goal to 90 minutes\n"
        "\n"
        "Unspend (manual fun-minute deduction):\n"
        "  /settings unspend 30\n"
        "  Prompts for confirmation before deducting.\n"
        "\n"
        "All settings are per-user and persist across sessions."
    ),
]


GUIDE_PAGES: dict[str, list[str]] = {
    "getting_started": _GETTING_STARTED_PAGES,
    "time_tracking": _TIME_TRACKING_PAGES,
    "economy": _ECONOMY_PAGES,
    "leveling": _LEVELING_PAGES,
    "settings": _SETTINGS_PAGES,
}


# ---------------------------------------------------------------------------
# Accessor functions
# ---------------------------------------------------------------------------


def get_guide_page(topic: str, page: int) -> tuple[str | None, int]:
    """Return (page_text, total_pages) or (None, 0) if topic invalid.

    Pages are 1-indexed.
    """
    pages = GUIDE_PAGES.get(topic)
    if not pages:
        return None, 0
    if page < 1 or page > len(pages):
        return None, len(pages)
    return pages[page - 1], len(pages)


def list_guide_topics() -> list[str]:
    """Return sorted list of available guide topic keys."""
    return sorted(GUIDE_PAGES.keys())


def resolve_guide_topic(keyword: str) -> str | None:
    """Resolve a user keyword to a guide topic key, or None."""
    normalized = keyword.strip().lower().lstrip("/")
    return TOPIC_ALIASES.get(normalized)
