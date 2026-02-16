from __future__ import annotations

# ---------------------------------------------------------------------------
# Command descriptions (one-liner per command, used in /help overview)
# ---------------------------------------------------------------------------

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "log": "Log productive time or other activities",
    "spend": "Log fun/consumption time",
    "status": "Show level, XP, streak, economy, deep work summary",
    "undo": "Undo your last log entry",
    "plan": "Set or view weekly productive time target",
    "start": "Welcome / onboarding",
    "timer": "Start a timer session (/t shortcut)",
    "stop": "Stop an active timer and log time",
    "quests": "View active quests or quest history",
    "shop": "Shop, buy items, savings, streak freeze",
    "notes": "Personal notes / rulebook",
    "llm": "AI analytics, chat mode, and coaching",
    "settings": "Language, reminders, quiet hours, LLM tier",
    "todo": "Daily to-do list with auto-logging",
    "help": "Show help or detailed command docs",
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
        "Other (no XP/fun, visible to AI):\n"
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
        "Shows level, XP, streak, week totals, plan progress, deep work sessions, economy, and active quest count."
    ),
    "undo": (
        "/undo\n"
        "Soft-deletes your last entry (productive or spend)."
    ),
    "plan": (
        "/plan set <duration>\n"
        "/plan show\n"
        "Sets or shows this week target.\n\n"
        "Examples:\n"
        "- /plan set 20h\n"
        "- /plan show"
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
    "quests": (
        "/quests\n"
        "/quests history\n"
        "/quests reset\n"
        "Shows active quests/history or resets all quests."
    ),
    "shop": (
        "/shop — list items + balance\n"
        "/shop add <emoji> \"name\" <cost|nok>\n"
        "/shop remove <id>\n"
        "/shop price <emoji> \"name\" <query> [--add]\n"
        "/shop budget <minutes|off>\n"
        "/shop buy <id|name> — redeem an item\n"
        "/shop buy history — redemption history\n"
        "/shop buy freeze — streak freeze (200 fun min)\n"
        "/shop save — savings status\n"
        "/shop fund <dur> — deposit to savings\n"
        "/shop goal <dur> [name] — set savings goal\n"
        "/shop sunday on 50|60|70 | off\n"
        "/shop cancel <goal_id>"
    ),
    "notes": (
        "/notes\n"
        "/notes add <text>\n"
        "/notes remove <id>\n"
        "/notes clear\n\n"
        "Personal notes/rulebook for yourself. It does not change system logic.\n"
        "Alias: /rules also works."
    ),
    "llm": (
        "/llm <question> — one-shot analytics\n"
        "/llm quest <easy|medium|hard> [3|5|7|14|21]\n"
        "/llm quests [3|5|7|14|21] — random difficulty\n"
        "/llm health — active tier/model/keys/last status\n"
        "/llm chat <message> — conversational mode with memory\n"
        "/llm clear — clear conversation history\n"
        "/llm memory — list saved memories\n"
        "/llm forget <id> — delete a memory\n"
        "/llm models\n\n"
        "Example:\n"
        "- /llm how much did I study this week?\n"
        "- /llm quest hard 14\n"
        "- /llm chat what should I focus on?\n"
        "- /llm health"
    ),
    "settings": (
        "/settings — show all current settings\n"
        "/settings lang <en|uk> — set language\n"
        "/settings reminders <on|off> — toggle reminders\n"
        "/settings quiet <HH:MM-HH:MM> — set quiet hours\n"
        "/settings tier <name|default> — set LLM tier"
    ),
    "todo": (
        "/todo\n"
        "/todo tomorrow\n"
        "/todo add [duration] <title>\n"
        "/todo done <id>\n"
        "/todo rm <id>\n"
        "/todo clear\n\n"
        "Daily to-do list with inline tick buttons.\n"
        "Tasks with duration auto-suggest a log category when done.\n\n"
        "Also works via LLM:\n"
        "- /llm todo add training 1h for tomorrow\n"
        "- /llm todo plan my day: 2h coding, 1h gym\n\n"
        "Examples:\n"
        "- /todo add 2h improve tg bot\n"
        "- /todo add training\n"
        "- /todo tomorrow"
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
    "llm": "llm",
    "ai": "llm",
    "coach": "llm",
    "chat": "llm",
    "quest": "quests",
    "quests": "quests",
    "shop": "shop",
    "economy": "shop",
    "redeem": "shop",
    "buy": "shop",
    "save": "shop",
    "savings": "shop",
    "freeze": "shop",
    "log": "logging",
    "logging": "logging",
    "spend": "logging",
    "timer": "logging",
    "stop": "logging",
    "plan": "logging",
    "settings": "settings",
    "reminders": "settings",
    "quiet_hours": "settings",
    "lang": "settings",
    "language": "settings",
    "notes": "notes",
    "rules": "notes",
    "todo": "todo",
    "todos": "todo",
    "tasks": "todo",
}


# ---------------------------------------------------------------------------
# Guide display names
# ---------------------------------------------------------------------------

GUIDE_TITLES: dict[str, str] = {
    "llm": "AI & Chat Guide",
    "quests": "Quests Guide",
    "logging": "Time Logging Guide",
    "notes": "Notes Guide",
    "settings": "Settings Guide",
    "shop": "Shop & Economy Guide",
    "todo": "To-Do List Guide",
}


# ---------------------------------------------------------------------------
# Guide pages (each topic -> list of page strings)
# ---------------------------------------------------------------------------

_LLM_PAGES: list[str] = [
    # Page 1: What is /llm?
    (
        "What is /llm?\n"
        "\n"
        "/llm lets you ask AI-powered questions about your tracked data "
        "directly in Telegram. The AI agent can access your logs, stats, "
        "level, XP, quests, and economy to answer questions.\n"
        "\n"
        "Two modes:\n"
        "  /llm <question>       One-shot analytics (stateless)\n"
        "  /llm chat <message>   Conversational coaching (with memory)\n"
        "\n"
        "The agent runs a multi-step loop:\n"
        "1. Reads your question\n"
        "2. Decides which tools to use (database queries, analytics)\n"
        "3. Runs tools to gather data\n"
        "4. Composes a final answer\n"
        "\n"
        "Example:\n"
        "  /llm how much time did I spend on build this week?\n"
        "\n"
        "The agent will query your database, calculate totals, and "
        "return a human-readable answer."
    ),

    # Page 2: Chat mode (coaching)
    (
        "Chat Mode (Coaching)\n"
        "\n"
        "/llm chat gives you a conversational AI coach that remembers "
        "your conversation and saves long-term facts about you.\n"
        "\n"
        "Start a conversation:\n"
        "  /llm chat how did I do this week?\n"
        "  /llm chat I want to reach level 15, what should I change?\n"
        "  /llm chat I keep skipping study days, any suggestions?\n"
        "\n"
        "Chat mode features:\n"
        "- Sees your last 8 messages as conversation context\n"
        "- Saves important facts (goals, preferences) as memories\n"
        "- Knows your level, XP, streak, weekly totals\n"
        "- Can query your logs for deeper analysis\n"
        "\n"
        "Clear conversation history:\n"
        "  /llm clear\n"
        "\n"
        "This removes all saved messages. Long-term memories are kept."
    ),

    # Page 3: Long-term memory
    (
        "Long-Term Memory\n"
        "\n"
        "In chat mode, the AI saves important facts about you that "
        "persist across sessions. These survive /llm clear.\n"
        "\n"
        "The AI automatically saves memories when you share:\n"
        "- Preferences: \"I prefer studying in the morning\"\n"
        "- Goals: \"I want to reach level 20 by summer\"\n"
        "- Facts: \"I work a 9-5 job\" or \"I'm a student\"\n"
        "\n"
        "View saved memories:\n"
        "  /llm memory\n"
        "\n"
        "Remove a memory by its ID:\n"
        "  /llm forget 2\n"
        "\n"
        "You can also ask in conversation:\n"
        "  /llm chat forget that I prefer mornings\n"
        "\n"
        "Memory limit: up to 30 memories per user.\n"
        "Memories appear in every future chat conversation as context."
    ),

    # Page 4: Model tiers
    (
        "Model Tiers\n"
        "\n"
        "/llm uses model tiers configured in settings:\n"
        "\n"
        "free (default):\n"
        "  Free OpenRouter models with Arcee Trinity as primary.\n"
        "\n"
        "open_source:\n"
        "  Best low-cost open models (DeepSeek/Qwen/GLM/etc).\n"
        "\n"
        "Specialized tiers:\n"
        "  kimi, deepseek, qwen, gpt, gemini, claude, top\n"
        "\n"
        "Set persistent tier in settings:\n"
        "  /settings tier open_source\n"
        "  /settings tier gpt\n"
        "  /settings tier default\n"
        "\n"
        "Check current runtime health:\n"
        "  /llm health\n"
        "\n"
        "Show available models:\n"
        "  /llm models"
    ),

    # Page 5: Skills
    (
        "Agent Skills\n"
        "\n"
        "The agent has built-in skills that activate based on "
        "keywords in your question:\n"
        "\n"
        "Quest Builder:\n"
        "  Triggers: quest, challenge, create quest\n"
        "  Example: /llm suggest a quest for studying\n"
        "\n"
        "Research:\n"
        "  Triggers: research, investigate, compare options\n"
        "  Example: /llm research best study techniques\n"
        "\n"
        "Coach:\n"
        "  Triggers: coach, advice, recommend, what should I\n"
        "  Example: /llm what should I prioritize this week?\n"
        "\n"
        "Skills combine: asking \"create a quest based on my study "
        "patterns\" activates both quest builder and data analysis.\n"
        "\n"
        "For ongoing coaching with memory, use /llm chat instead."
    ),

    # Page 6: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "One-shot analytics:\n"
        "  /llm <question>\n"
        "\n"
        "Conversational coaching:\n"
        "  /llm chat <message>\n"
        "  /llm clear           Clear conversation\n"
        "  /llm memory          View saved memories\n"
        "  /llm forget <id>     Delete a memory\n"
        "  /llm health          Runtime status\n"
        "\n"
        "Model control:\n"
        "  /settings tier <n>   Set persistent tier\n"
        "  /settings tier default\n"
        "  /llm models          Show available models\n"
        "\n"
        "Limits:\n"
        "  Defaults: unlimited/day, 0s cooldown\n"
        "  6 agent steps, 4 tool calls max\n"
        "  Subcommands (clear, memory, forget) are free"
    ),
]


_QUESTS_PAGES: list[str] = [
    # Page 1: What are quests?
    (
        "What Are Quests?\n"
        "\n"
        "Quests are manual challenges created via /llm quest. "
        "Each quest has both reward and penalty in fun minutes.\n"
        "\n"
        "How quests work:\n"
        "- Generate proposal with /llm quest or /llm quests\n"
        "- Review quest, then Accept or Decline\n"
        "- Progress is tracked automatically from your logs\n"
        "- Complete => reward is added\n"
        "- Fail/expire => equal penalty is applied\n"
        "- Duration options: 3, 5, 7, 14, 21 days\n"
        "\n"
        "Difficulty baseline (7 days):\n"
        "  easy   - min 300m, reward 30-45m\n"
        "  medium - min 720m, reward 60-90m\n"
        "  hard   - min 1200m, reward 120-180m\n"
        "\n"
        "Example quest:\n"
        "  Build 720 minutes in 7 days [medium]\n"
        "  Reward/Penalty: +75m / -75m\n"
        "  Progress: 240/720"
    ),

    # Page 2: Viewing quests
    (
        "Viewing Quests\n"
        "\n"
        "See your active quests:\n"
        "  /quests\n"
        "\n"
        "This shows all active quests with:\n"
        "- Quest title and difficulty\n"
        "- Duration in days\n"
        "- Current value vs target\n"
        "- Reward and penalty\n"
        "- Status (active, completed, or failed)\n"
        "\n"
        "Example output:\n"
        "  Active Quests:\n"
        "  - Builder Sprint (medium, 7d): 240/720 min | +75m / -75m\n"
        "  - Hard Forge (hard, 14d): 560/2400 min | +260m / -260m\n"
        "\n"
        "Quests update automatically as you log time."
    ),

    # Page 3: Quest types
    (
        "Quest Types\n"
        "\n"
        "Quests 2.0 primarily use measurable minute targets:\n"
        "\n"
        "- total_minutes in build|study|training|all\n"
        "- difficulty and duration define minimum target and reward range\n"
        "- hard quests may include extra benefit text\n"
        "\n"
        "Build-first policy:\n"
        "- Most quests should focus on build\n"
        "- Study and training are supportive additions\n"
        "\n"
        "Generate manually:\n"
        "  /llm quest easy 7\n"
        "  /llm quest hard 14\n"
        "  /llm quests"
    ),

    # Page 4: Quest history + quick ref
    (
        "Quest History & Quick Reference\n"
        "\n"
        "See completed and failed quests:\n"
        "  /quests history\n"
        "\n"
        "Completed quests add reward.\n"
        "Failed/expired quests apply matching penalty.\n"
        "\n"
        "Commands:\n"
        "  /quests         View active quests\n"
        "  /quests history View quest history\n"
        "  /quests reset   Delete all your quests/proposals\n"
        "\n"
        "Ask AI to create a quest:\n"
        "  /llm quest medium 7\n"
        "  /llm quests\n"
        "\n"
        "Difficulty: easy, medium, hard\n"
        "Duration: 3|5|7|14|21 days\n"
        "Reward and penalty are linked 1:1."
    ),
]


_SHOP_PAGES: list[str] = [
    # Page 1: How economy works
    (
        "How the Economy Works\n"
        "\n"
        "The bot has a built-in economy based on time:\n"
        "\n"
        "Earning:\n"
        "  - Log productive time (study, build, training, job)\n"
        "  - You earn \"fun minutes\" based on the category\n"
        "  - Quest rewards and level-up bonuses add more\n"
        "\n"
        "Spending:\n"
        "  - Log fun time with /spend\n"
        "  - Buy shop items with /shop buy\n"
        "  - Buy streak freezes with /shop buy freeze\n"
        "\n"
        "The idea: productive work earns guilt-free leisure time.\n"
        "\n"
        "Check your balance:\n"
        "  /status - shows current fun minutes remaining"
    ),

    # Page 2: Shop basics
    (
        "Shop Basics\n"
        "\n"
        "The shop is your personal reward catalog.\n"
        "\n"
        "View your shop:\n"
        "  /shop\n"
        "\n"
        "Add an item:\n"
        "  /shop add <emoji> \"<name>\" <duration>\n"
        "  /shop add <emoji> \"<name>\" <nok_price>nok\n"
        "\n"
        "Examples:\n"
        "  /shop add \U0001f3ae \"Gaming session\" 120m\n"
        "  /shop add \U0001f3a7 \"AirPods\" 2490nok\n"
        "\n"
        "Remove an item:\n"
        "  /shop remove <id>\n"
        "\n"
        "Price search (looks up web prices):\n"
        "  /shop price <emoji> \"<name>\" <query>\n"
        "  /shop price \u231a \"Apple Watch\" apple watch se price norway\n"
        "\n"
        "Set a monthly fun spend budget:\n"
        "  /shop budget 2000\n"
        "  /shop budget off"
    ),

    # Page 3: Buying items
    (
        "Buying Items\n"
        "\n"
        "When you've earned enough fun minutes, buy a shop item:\n"
        "\n"
        "Buy by ID or name:\n"
        "  /shop buy 3\n"
        "  /shop buy AirPods\n"
        "\n"
        "What happens:\n"
        "1. Bot checks if you have enough fun minutes\n"
        "2. Savings fund is used first (if available)\n"
        "3. Remaining cost comes from your fun balance\n"
        "4. Item is marked as redeemed\n"
        "\n"
        "View purchase history:\n"
        "  /shop buy history\n"
        "\n"
        "Streak freeze:\n"
        "  /shop buy freeze\n"
        "  Cost: 200 fun minutes\n"
        "  Prevents streak loss if you don't log tomorrow"
    ),

    # Page 4: Savings
    (
        "Savings Fund\n"
        "\n"
        "Set aside fun minutes for expensive items.\n"
        "Saved minutes are locked and won't be spent by /spend.\n"
        "\n"
        "View savings:\n"
        "  /shop save\n"
        "\n"
        "Deposit into savings:\n"
        "  /shop fund 200m\n"
        "  /shop fund 2h\n"
        "\n"
        "Set a savings goal:\n"
        "  /shop goal 5000m Apple Watch fund\n"
        "\n"
        "Cancel a goal (keeps the fund):\n"
        "  /shop cancel <goal_id>\n"
        "\n"
        "Auto-save on Sundays:\n"
        "  /shop sunday on 50   (transfer 50% of balance)\n"
        "  /shop sunday off\n"
        "\n"
        "When you buy an item, savings are used first,\n"
        "then your regular balance."
    ),

    # Page 5: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Shop:\n"
        "  /shop              View items + balance\n"
        "  /shop add ...      Add item\n"
        "  /shop remove <id>  Remove item\n"
        "  /shop price ...    Search web price\n"
        "  /shop budget <min> Set monthly budget\n"
        "\n"
        "Buying:\n"
        "  /shop buy <id|name>  Buy an item\n"
        "  /shop buy history    Past purchases\n"
        "  /shop buy freeze     Streak freeze (200 fun)\n"
        "\n"
        "Savings:\n"
        "  /shop save           View savings\n"
        "  /shop fund <dur>     Deposit to fund\n"
        "  /shop goal <dur> [n] Set savings goal\n"
        "  /shop cancel <id>    Cancel goal\n"
        "  /shop sunday on <%%> Auto weekly save\n"
        "  /shop sunday off     Disable auto save\n"
        "\n"
        "Economy: Productive time -> fun minutes -> shop/spend"
    ),
]


_LOGGING_PAGES: list[str] = [
    # Page 1: Overview
    (
        "Time Tracking Overview\n"
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
        "Two types of logging:\n"
        "  /log  - Productive time (earns fun minutes + XP)\n"
        "  /spend - Fun/consumption time (costs fun minutes)\n"
        "\n"
        "Two ways to log:\n"
        "  Manual: /log 90m study or /spend 1h movie\n"
        "  Timer:  /timer study then /stop when done\n"
        "\n"
        "You can also send free-form text and the AI will parse it\n"
        "into a log entry for you to confirm."
    ),

    # Page 2: Logging productive time
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

    # Page 3: Fun time + timer
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
        "Use the STOP button on the timer message or /stop.\n"
        "\n"
        "Deep work bonus:\n"
        "  Timer sessions of 60+ minutes earn extra XP.\n"
        "  These also count toward deep work quest conditions.\n"
        "\n"
        "Undo a mistake:\n"
        "  /undo\n"
        "  Removes your last log entry (productive or spend)."
    ),

    # Page 4: Quick reference
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
        "\n"
        "Weekly plan:\n"
        "  /plan set <duration>\n"
        "  /plan show\n"
        "\n"
        "View progress: /status\n"
        "\n"
        "Duration formats: 90m, 1.5h, 1h30m, 90\n"
        "Categories: study, build (default), training, job"
    ),
]


_NOTES_PAGES: list[str] = [
    # Page 1: What are notes?
    (
        "Personal Notes\n"
        "\n"
        "/notes lets you maintain a personal rulebook or notes. "
        "These are text entries you save for yourself.\n"
        "\n"
        "View your notes:\n"
        "  /notes\n"
        "\n"
        "Add a note:\n"
        "  /notes add No social media before noon\n"
        "  /notes add Study at least 1 hour every morning\n"
        "\n"
        "Remove a note by ID:\n"
        "  /notes remove 2\n"
        "\n"
        "Clear all notes:\n"
        "  /notes clear\n"
        "\n"
        "Alias: /rules also works.\n"
        "\n"
        "Notes are for yourself. They don't change how the bot works. "
        "However, the AI can see your notes and may reference them "
        "when giving advice."
    ),
]


_SETTINGS_PAGES: list[str] = [
    # Page 1: Overview
    (
        "Settings Overview\n"
        "\n"
        "View all settings:\n"
        "  /settings\n"
        "\n"
        "Language:\n"
        "  /settings lang en    Set to English\n"
        "  /settings lang uk    Set to Ukrainian\n"
        "\n"
        "Reminders:\n"
        "  /settings reminders on    Enable reminders\n"
        "  /settings reminders off   Disable reminders\n"
        "\n"
        "Quiet hours (no reminders during this window):\n"
        "  /settings quiet 22:00-08:00\n"
        "  /settings quiet 23:00-07:00\n"
        "\n"
        "LLM tier:\n"
        "  /settings tier free\n"
        "  /settings tier open_source\n"
        "  /settings tier gpt\n"
        "  /settings tier default\n"
        "\n"
        "What changes with language:\n"
        "  Status messages, error messages, system messages.\n"
        "  Commands and help content stay in English.\n"
        "\n"
        "All settings are per-user and persist across sessions."
    ),
]


_TODO_PAGES: list[str] = [
    # Page 1: What is /todo?
    (
        "What is /todo?\n"
        "\n"
        "The to-do list is a daily task planner built into the bot. "
        "You can plan your day, set tasks with optional durations, and "
        "tick them off when done.\n"
        "\n"
        "Key features:\n"
        "- Plan tasks for today or tomorrow\n"
        "- Add optional durations (2h, 30m, etc.)\n"
        "- Tick off tasks with inline buttons\n"
        "- Auto-suggest logging when a task with duration is completed\n"
        "- Also works through /llm for natural language input\n"
        "\n"
        "Quick start:\n"
        "  /todo add 2h improve tg bot\n"
        "  /todo add 1h training\n"
        "  /todo add meeting with boss\n"
        "  /todo\n"
        "\n"
        "The last command shows your list with tick buttons."
    ),
    # Page 2: Adding tasks
    (
        "Adding tasks\n"
        "\n"
        "Basic format:\n"
        "  /todo add [duration] <title>\n"
        "\n"
        "Duration goes first (optional). If recognized as a time "
        "value, it is stored separately. Everything after is the title.\n"
        "\n"
        "Examples:\n"
        "  /todo add 2h improve tg bot\n"
        "     -> title: 'improve tg bot', duration: 2h\n"
        "\n"
        "  /todo add training\n"
        "     -> title: 'training', no duration\n"
        "\n"
        "  /todo add 30m morning walk\n"
        "     -> title: 'morning walk', duration: 30m\n"
        "\n"
        "Tasks are added to today by default.\n"
        "\n"
        "Via LLM (natural language):\n"
        "  /llm todo add training 1h for tomorrow\n"
        "  /llm todo plan my day: 2h coding, 1h gym, meeting\n"
        "\n"
        "The LLM agent can add multiple items in one message."
    ),
    # Page 3: Completing tasks
    (
        "Completing tasks\n"
        "\n"
        "When you type /todo, you see your list with tick buttons:\n"
        "\n"
        "  Plan for 13.02 (0/3):\n"
        "  1. \u2b1c improve tg bot (2h)\n"
        "  2. \u2b1c training (1h)\n"
        "  3. \u2b1c meeting with boss\n"
        "  [\u27051] [\u27052] [\u27053]\n"
        "\n"
        "Tap a button to mark it done.\n"
        "\n"
        "Auto-categorize:\n"
        "If the task has a duration, the bot calls the AI to suggest "
        "a log category and sends:\n"
        "\n"
        "  \u2705 training (1h) -- done!\n"
        "  Log as 60m training?\n"
        "  [Accept] [Decline]\n"
        "\n"
        "Accept logs the time entry automatically.\n"
        "You can also use: /todo done <id>"
    ),
    # Page 4: Quick reference
    (
        "Quick reference\n"
        "\n"
        "Commands:\n"
        "  /todo              Show today's list\n"
        "  /todo tomorrow     Show tomorrow's list\n"
        "  /todo add <title>  Add task (today)\n"
        "  /todo add 2h <t>   Add with duration\n"
        "  /todo done <id>    Mark done by ID\n"
        "  /todo rm <id>      Delete a task\n"
        "  /todo clear        Clear pending tasks\n"
        "\n"
        "Via LLM:\n"
        "  /llm todo add ...     Add via natural language\n"
        "  /llm todo show tomorrow  List tasks\n"
        "\n"
        "Auto-log flow:\n"
        "  Tick task -> AI suggests category -> Accept/Decline\n"
        "  Categories: study, build, training, other\n"
        "\n"
        "Notes:\n"
        "- Duration is optional but needed for auto-logging\n"
        "- Tasks are per-date (today/tomorrow)\n"
        "- /todo clear only removes pending tasks, not done"
    ),
]


GUIDE_PAGES: dict[str, list[str]] = {
    "llm": _LLM_PAGES,
    "logging": _LOGGING_PAGES,
    "notes": _NOTES_PAGES,
    "quests": _QUESTS_PAGES,
    "settings": _SETTINGS_PAGES,
    "shop": _SHOP_PAGES,
    "todo": _TODO_PAGES,
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
