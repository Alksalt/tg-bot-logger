from __future__ import annotations

# ---------------------------------------------------------------------------
# Command descriptions (one-liner per command, used in /help overview)
# ---------------------------------------------------------------------------

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "log": "Log productive time or other activities",
    "spend": "Log fun/consumption time",
    "status": "Show level, XP, streak, economy summary",
    "week": "Weekly summary with plan progress",
    "undo": "Undo your last log entry",
    "plan": "Set or view weekly productive time target",
    "start": "Start a timer session",
    "stop": "Stop an active timer and log time",
    "quests": "View active quests or quest history",
    "shop": "Browse, add, or manage shop items",
    "redeem": "Redeem a shop item with fun minutes",
    "save": "Manage savings fund and goals",
    "rules": "Personal rulebook / notes",
    "llm": "Ask AI analytics questions about your data",
    "coach": "Personal AI productivity coach with memory",
    "search": "Run web search from Telegram",
    "lang": "Set preferred language (en/uk)",
    "reminders": "Toggle reminder notifications",
    "quiet_hours": "Set do-not-disturb window for reminders",
    "freeze": "Buy a streak freeze for tomorrow",
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
        "Other (no XP/fun, visible to coach/llm):\n"
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
        "Shows level, XP, streak, week totals, plan progress, economy, and active quest count."
    ),
    "week": (
        "/week\n"
        "Shows this week summary (productive, spent, plan progress, XP, deep sessions, fun remaining)."
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
        "/start [study|build|training|job|spend] [note]\n"
        "Starts a timer session.\n\n"
        "Example:\n"
        "- /start build backend cleanup\n"
        "- /start spend games"
    ),
    "stop": (
        "/stop\n"
        "Stops active timer and logs elapsed minutes.\n"
        "Productive timers give XP/fun; spend timers log fun spend."
    ),
    "quests": (
        "/quests\n"
        "/quests history\n"
        "Shows active quests or this-week quest history."
    ),
    "shop": (
        "/shop\n"
        "/shop add <emoji> \"name\" <cost_duration_or_minutes> [nok_value]\n"
        "/shop add <emoji> \"name\" <nok_value>nok\n"
        "/shop price <emoji> \"name\" <search_query>\n"
        "/shop price <emoji> \"name\" <search_query> --add\n"
        "/shop remove <item_id>\n"
        "/shop budget <minutes|off>\n\n"
        "Examples:\n"
        "- /shop add \u231a \"Apple Watch\" 15000m\n"
        "- /shop add \u231a \"Apple Watch\" 4990nok\n"
        "- /shop price \u231a \"Apple Watch\" apple watch price norway\n"
        "- /shop price \u231a \"Apple Watch\" apple watch price norway --add\n"
        "- /shop add \U0001f3a7 \"AirPods\" 4000 2490\n"
        "- /shop remove 12"
    ),
    "redeem": (
        "/redeem <item_id|item_name>\n"
        "/redeem history\n\n"
        "Redeem uses savings fund first, then remaining fun minutes."
    ),
    "save": (
        "/save\n"
        "/save goal <duration> [name]\n"
        "/save fund <duration>\n\n"
        "/save sunday on 50|60|70\n"
        "/save sunday off\n\n"
        "Simple flow:\n"
        "1) Add into fund directly: /save fund 200m\n"
        "2) Optional goal: /save goal 2000m Device fund\n"
        "Fund is locked for shop redemptions."
    ),
    "rules": (
        "/rules\n"
        "/rules add <text>\n"
        "/rules remove <id>\n"
        "/rules clear\n\n"
        "Personal rulebook/notes for yourself. It does not change system logic."
    ),
    "llm": (
        "/llm <question>\n"
        "/llm tier <free|open_source_cheap|top_tier> <question>\n"
        "/llm gpt|claude|gemini <question>\n"
        "/llm models\n"
        "Ask analytics/data questions based on your stats and logs.\n"
        "Uses V3 agent loop with tools and tiered model routing.\n\n"
        "Model shortcuts (use top_tier provider directly):\n"
        "- /llm gpt ... → GPT-5 Mini (OpenAI)\n"
        "- /llm claude ... → Claude Haiku 4.5 (Anthropic)\n"
        "- /llm gemini ... → Gemini 3 Flash (Google)\n\n"
        "Example:\n"
        "- /llm what should I focus on to hit level 10 faster?\n"
        "- /llm gpt how much did I spend on anime this week?\n"
        "- /llm tier free compare apple watch prices in norway"
    ),
    "coach": (
        "/coach <message>\n"
        "Personal productivity coach with conversation memory.\n\n"
        "Subcommands:\n"
        "/coach clear - clear conversation history\n"
        "/coach memory - view saved memories\n"
        "/coach forget <id> - remove a memory\n"
        "/coach tier - view/set persistent model tier\n\n"
        "Tier persists for all /coach and /llm requests:\n"
        "/coach tier top_tier - use GPT-5 Mini / Gemini / Haiku\n"
        "/coach tier free - switch back to free models\n"
        "/coach tier default - reset to system default\n\n"
        "Shares daily LLM limit with /llm.\n\n"
        "Example:\n"
        "- /coach what should I focus on this week?\n"
        "- /coach I prefer morning study sessions\n"
        "- /coach how am I doing compared to last week?"
    ),
    "search": (
        "/search <query>\n"
        "Runs web search tool (Brave -> Tavily -> Serper fallback) with cache + dedupe.\n\n"
        "Example:\n"
        "- /search apple watch ultra 2 price norway"
    ),
    "lang": (
        "/lang\n"
        "/lang <en|uk>\n"
        "Shows or sets your preferred bot language (English/Ukrainian)."
    ),
    "reminders": (
        "/reminders on\n"
        "/reminders off\n"
        "Turns reminder notifications on or off."
    ),
    "quiet_hours": (
        "/quiet_hours HH:MM-HH:MM\n"
        "Suppress reminders inside this window.\n"
        "Example: /quiet_hours 22:00-08:00"
    ),
    "freeze": (
        "/freeze\n"
        "Buys tomorrow streak freeze for 200 fun minutes."
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
    "coach": "coach",
    "llm": "llm",
    "ai": "llm",
    "quest": "quests",
    "quests": "quests",
    "shop": "shop",
    "economy": "shop",
    "redeem": "shop",
    "save": "shop",
    "savings": "shop",
    "log": "logging",
    "logging": "logging",
    "spend": "logging",
    "start": "logging",
    "stop": "logging",
    "timer": "logging",
    "plan": "logging",
    "week": "logging",
    "search": "search",
    "research": "search",
    "settings": "settings",
    "reminders": "settings",
    "quiet_hours": "settings",
    "lang": "settings",
    "language": "settings",
    "rules": "settings",
    "freeze": "settings",
    "todo": "todo",
    "todos": "todo",
    "tasks": "todo",
}


# ---------------------------------------------------------------------------
# Guide display names
# ---------------------------------------------------------------------------

GUIDE_TITLES: dict[str, str] = {
    "coach": "Coach Guide",
    "llm": "LLM & Analytics Guide",
    "quests": "Quests Guide",
    "logging": "Time Logging Guide",
    "search": "Web Search Guide",
    "settings": "Settings Guide",
    "shop": "Shop & Economy Guide",
    "todo": "To-Do List Guide",
}


# ---------------------------------------------------------------------------
# Guide pages (each topic -> list of page strings)
# ---------------------------------------------------------------------------

_COACH_PAGES: list[str] = [
    # Page 1: What is Coach?
    (
        "What is Coach?\n"
        "\n"
        "Coach is your personal AI productivity companion built right into "
        "the bot. Unlike a simple chatbot, Coach:\n"
        "\n"
        "- Knows your tracked data (hours logged, level, streak, XP)\n"
        "- Remembers your conversation across messages\n"
        "- Saves long-term facts about you (goals, preferences)\n"
        "- Can look up your stats to give data-driven advice\n"
        "\n"
        "Think of it as a personal productivity partner that gets smarter "
        "the more you use it.\n"
        "\n"
        "You talk to Coach using the /coach command followed by your "
        "message. Coach uses the same AI models as /llm but with "
        "conversation memory on top.\n"
        "\n"
        "Example:\n"
        "  /coach Hi! I want to get better at consistent daily study\n"
        "\n"
        "Coach will respond with personalized advice based on your "
        "actual tracking data."
    ),

    # Page 2: Starting a conversation
    (
        "Starting a Conversation\n"
        "\n"
        "To talk to Coach, type:\n"
        "  /coach <your message>\n"
        "\n"
        "Coach works best with natural language. Just write what you'd "
        "say to a real coach. Here are some conversation starters:\n"
        "\n"
        "Ask for a weekly review:\n"
        "  /coach how did I do this week?\n"
        "\n"
        "Get advice on a goal:\n"
        "  /coach I want to reach level 15, what should I change?\n"
        "\n"
        "Reflect on habits:\n"
        "  /coach I keep skipping study days, any suggestions?\n"
        "\n"
        "Share context:\n"
        "  /coach I have exams next month, help me plan\n"
        "\n"
        "Ask about your data:\n"
        "  /coach which category am I spending the most time on?\n"
        "\n"
        "You can send multiple messages in a row. Coach remembers "
        "what was said earlier in the conversation."
    ),

    # Page 3: Conversation memory
    (
        "Conversation Memory\n"
        "\n"
        "Coach remembers your recent conversation. Each time you "
        "send a message, Coach sees the last 8 messages (yours and "
        "its replies) as context.\n"
        "\n"
        "This means you can have natural back-and-forth:\n"
        "\n"
        "  You: /coach how much did I study this week?\n"
        "  Coach: You studied 4h20m across 3 sessions...\n"
        "  You: /coach is that more or less than last week?\n"
        "  Coach: That's 30m less than last week when...\n"
        "\n"
        "Coach knows you're referring to study time because it "
        "saw the previous messages.\n"
        "\n"
        "How it works:\n"
        "- Messages are saved per user (private to you)\n"
        "- The bot keeps the last 20 messages in the database\n"
        "- Each Coach request includes the 8 most recent as context\n"
        "- Older messages are automatically pruned\n"
        "\n"
        "To start fresh, clear the conversation:\n"
        "  /coach clear\n"
        "\n"
        "This removes all saved messages. Coach will have no memory "
        "of previous conversations (long-term memories are kept)."
    ),

    # Page 4: Long-term memory
    (
        "Long-Term Memory\n"
        "\n"
        "Beyond conversation history, Coach can save important facts "
        "about you that persist across sessions. These are called "
        "\"memories\" and they survive even after /coach clear.\n"
        "\n"
        "Coach automatically saves memories when you share:\n"
        "- Preferences: \"I prefer studying in the morning\"\n"
        "- Goals: \"I want to reach level 20 by summer\"\n"
        "- Facts: \"I work a 9-5 job\" or \"I'm a student\"\n"
        "- Context: \"I have exams in March\"\n"
        "\n"
        "Examples of things Coach will remember:\n"
        "  /coach I'm most productive between 6am and 10am\n"
        "  /coach my goal is 25 hours of study per week\n"
        "  /coach I'm learning Python and machine learning\n"
        "\n"
        "Coach will NOT save trivial things like greetings or \"thanks\".\n"
        "\n"
        "Memories appear in every future Coach conversation as context, "
        "so Coach can reference them naturally:\n"
        "  \"Since you prefer mornings, try scheduling study before 10am.\""
    ),

    # Page 5: Managing memories
    (
        "Managing Memories\n"
        "\n"
        "View all saved memories:\n"
        "  /coach memory\n"
        "\n"
        "This shows a numbered list like:\n"
        "  Your memories:\n"
        "  1. (preference) Prefers morning study sessions\n"
        "  2. (goal [study]) Reach level 20 by summer\n"
        "  3. (fact) Works 9-5 office job\n"
        "\n"
        "Remove a specific memory by its ID:\n"
        "  /coach forget 2\n"
        "\n"
        "This removes the \"Reach level 20 by summer\" memory. "
        "Coach will no longer see it in future conversations.\n"
        "\n"
        "You can also ask Coach to forget something in conversation:\n"
        "  /coach forget that I prefer mornings, I changed my schedule\n"
        "\n"
        "Coach will use the memory_manage tool to delete the relevant "
        "memory and may save a new one based on your update.\n"
        "\n"
        "Memory limit: Coach stores up to 30 memories per user. "
        "If you hit the limit, remove old ones with /coach forget."
    ),

    # Page 6: Tips for best results
    (
        "Tips for Best Results\n"
        "\n"
        "What Coach is great at:\n"
        "- Weekly/daily reviews of your progress\n"
        "- Habit analysis (\"am I consistent?\")\n"
        "- Goal planning with your actual data\n"
        "- Motivational check-ins\n"
        "- Comparing time periods (\"this week vs last\")\n"
        "\n"
        "What Coach is NOT:\n"
        "- A general chatbot (keep it productivity-focused)\n"
        "- A replacement for /llm (use /llm for one-off data queries)\n"
        "\n"
        "Rate limits:\n"
        "- Coach shares the daily limit with /llm: 80 requests/day\n"
        "- 30-second cooldown between requests\n"
        "- Subcommands (clear, memory, forget) don't count\n"
        "\n"
        "Best practices:\n"
        "- Be specific: \"how was my study this week?\" > \"how am I doing?\"\n"
        "- Share your goals early so Coach can track them\n"
        "- Use /coach memory periodically to review what Coach knows\n"
        "- Clear old conversations if responses seem confused"
    ),

    # Page 7: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Talk to Coach:\n"
        "  /coach <message>\n"
        "\n"
        "Examples:\n"
        "  /coach how did I do this week?\n"
        "  /coach I want to study 3 hours every day\n"
        "  /coach compare my study vs build time\n"
        "  /coach what should I focus on tomorrow?\n"
        "\n"
        "Subcommands (no daily limit used):\n"
        "  /coach clear       - Clear conversation history\n"
        "  /coach memory      - View saved memories\n"
        "  /coach forget <id> - Remove a memory\n"
        "  /coach tier        - View current tier\n"
        "  /coach tier <name> - Set persistent tier\n"
        "\n"
        "Tier names: free, open_source_cheap, top_tier, default\n"
        "Applies to both /coach and /llm until changed.\n"
        "\n"
        "How Coach sees your data:\n"
        "  - Your level, XP, streak, weekly totals\n"
        "  - Last 8 conversation messages\n"
        "  - All saved long-term memories\n"
        "  - Can query your logs for deeper analysis\n"
        "\n"
        "Limits:\n"
        "  - 80 requests/day (shared with /llm)\n"
        "  - 30s cooldown between messages\n"
        "  - Max 30 saved memories"
    ),
]


_LLM_PAGES: list[str] = [
    # Page 1: What is /llm?
    (
        "What is /llm?\n"
        "\n"
        "/llm lets you ask AI-powered questions about your tracked data "
        "directly in Telegram. The AI agent can access your logs, stats, "
        "level, XP, quests, and economy to answer questions.\n"
        "\n"
        "Unlike Coach, /llm is stateless: each question starts fresh "
        "with no memory of previous conversations. Use /llm for quick "
        "one-off data queries.\n"
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
        "return a human-readable answer.\n"
        "\n"
        "Requires an API key (OPENROUTER_API_KEY) set by admin."
    ),

    # Page 2: Basic questions
    (
        "Basic Questions\n"
        "\n"
        "Here are examples of what you can ask /llm:\n"
        "\n"
        "Time tracking:\n"
        "  /llm how much did I study this week?\n"
        "  /llm what was my most productive day?\n"
        "  /llm show my category breakdown for this week\n"
        "\n"
        "Progress:\n"
        "  /llm how close am I to the next level?\n"
        "  /llm what's my current streak?\n"
        "  /llm how does this week compare to last week?\n"
        "\n"
        "Economy:\n"
        "  /llm how many fun minutes do I have left?\n"
        "  /llm how much have I spent this week?\n"
        "\n"
        "Analysis:\n"
        "  /llm which category earns me the most XP?\n"
        "  /llm am I on track to hit my weekly plan?\n"
        "  /llm what time of day do I usually study?\n"
        "\n"
        "Tips:\n"
        "- Be specific about time periods (\"this week\", \"today\")\n"
        "- Ask about things the bot actually tracks\n"
        "- The agent can do math and comparisons"
    ),

    # Page 3: Model tiers
    (
        "Model Tiers\n"
        "\n"
        "/llm uses AI models with three tiers:\n"
        "\n"
        "free (default):\n"
        "  - Free models via OpenRouter, no cost\n"
        "  - Good for simple questions\n"
        "  - May be slower or less accurate\n"
        "\n"
        "open_source_cheap:\n"
        "  - Low-cost open source models via OpenRouter\n"
        "  - Better reasoning than free tier\n"
        "  - Good balance of cost and quality\n"
        "\n"
        "top_tier:\n"
        "  - Direct provider APIs: GPT-5 Mini, Gemini 3 Flash,\n"
        "    Claude Haiku 4.5\n"
        "  - Uses your free token allocations with each provider\n"
        "  - Falls back to OpenRouter if direct API fails\n"
        "\n"
        "To specify a tier:\n"
        "  /llm tier free what's my streak?\n"
        "  /llm tier top_tier analyze my weekly patterns\n"
        "\n"
        "Model shortcuts (top_tier, pick a specific model):\n"
        "  /llm gpt <question>     → GPT-5 Mini (OpenAI)\n"
        "  /llm claude <question>  → Claude Haiku 4.5 (Anthropic)\n"
        "  /llm gemini <question>  → Gemini 3 Flash (Google)\n"
        "\n"
        "To see available models:\n"
        "  /llm models\n"
        "\n"
        "If the default tier fails, the agent may automatically "
        "escalate to a higher tier."
    ),

    # Page 4: Skills
    (
        "Agent Skills\n"
        "\n"
        "The /llm agent has built-in skills that activate based on "
        "keywords in your question. Skills load extra instructions "
        "and specialized tools.\n"
        "\n"
        "Quest Builder:\n"
        "  Triggers: quest, challenge, create quest\n"
        "  What it does: Proposes and creates new quests\n"
        "  Example: /llm suggest a quest for studying\n"
        "\n"
        "Research:\n"
        "  Triggers: research, investigate, compare options\n"
        "  What it does: Multi-step web search with analysis\n"
        "  Example: /llm research best study techniques\n"
        "\n"
        "Coach:\n"
        "  Triggers: coach, advice, recommend, what should I\n"
        "  What it does: Data-backed coaching advice\n"
        "  Example: /llm what should I prioritize this week?\n"
        "\n"
        "Skills combine: asking \"create a quest based on my study "
        "patterns\" activates both quest builder and data analysis.\n"
        "\n"
        "Note: For ongoing coaching conversations with memory, "
        "use /coach instead of /llm."
    ),

    # Page 5: Limits and tips
    (
        "Limits and Tips\n"
        "\n"
        "Rate limits:\n"
        "  - 80 requests per day (shared with /coach)\n"
        "  - 30-second cooldown between requests\n"
        "  - Resets at midnight\n"
        "\n"
        "Agent loop:\n"
        "  - Max 6 thinking steps per request\n"
        "  - Max 4 tool calls per request\n"
        "  - If the agent can't answer, it will say so\n"
        "\n"
        "What works well:\n"
        "  - Specific questions with clear time periods\n"
        "  - Asking about data the bot tracks\n"
        "  - Comparisons (\"this week vs last\")\n"
        "  - Calculations (\"how many more hours to level 10?\")\n"
        "\n"
        "What doesn't work:\n"
        "  - General knowledge questions (use /search instead)\n"
        "  - Questions about other people's data\n"
        "  - Very long or multi-part questions\n"
        "\n"
        "If the response quality is poor, try:\n"
        "  - Rephrasing your question\n"
        "  - Using a higher tier: /llm tier top_tier ...\n"
        "  - Picking a specific model: /llm gpt ...\n"
        "  - Breaking complex questions into simpler parts"
    ),

    # Page 6: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Basic usage:\n"
        "  /llm <question>\n"
        "\n"
        "With specific tier:\n"
        "  /llm tier <free|open_source_cheap|top_tier> <question>\n"
        "\n"
        "Model shortcuts (top_tier, direct provider):\n"
        "  /llm gpt <question>     → GPT-5 Mini\n"
        "  /llm claude <question>  → Claude Haiku 4.5\n"
        "  /llm gemini <question>  → Gemini 3 Flash\n"
        "\n"
        "Show available models:\n"
        "  /llm models\n"
        "\n"
        "Example questions:\n"
        "  /llm how much did I study this week?\n"
        "  /llm am I on track for my weekly plan?\n"
        "  /llm gpt compare build vs study hours\n"
        "  /llm suggest a quest for daily logging\n"
        "  /llm claude deep analysis of my habits\n"
        "\n"
        "Skills (auto-detected):\n"
        "  quest builder - \"quest\", \"challenge\"\n"
        "  research      - \"research\", \"investigate\"\n"
        "  coach         - \"advice\", \"recommend\"\n"
        "\n"
        "Limits:\n"
        "  - 10/day (shared with /coach)\n"
        "  - 30s cooldown\n"
        "  - 6 agent steps, 4 tool calls max"
    ),
]


_QUESTS_PAGES: list[str] = [
    # Page 1: What are quests?
    (
        "What Are Quests?\n"
        "\n"
        "Quests are weekly challenges that reward you with bonus fun "
        "minutes when completed. They add a game-like layer to your "
        "time tracking.\n"
        "\n"
        "How quests work:\n"
        "- Quests are generated weekly (or proposed by the AI)\n"
        "- Each quest has a condition (e.g., study 5 hours)\n"
        "- Progress is tracked automatically from your logs\n"
        "- Completing a quest awards fun minutes as a reward\n"
        "- Quests expire at the end of the week\n"
        "\n"
        "Quest difficulty levels:\n"
        "  easy   - Small challenges, modest rewards\n"
        "  medium - Moderate effort, good rewards\n"
        "  hard   - Significant commitment, best rewards\n"
        "\n"
        "Example quest:\n"
        "  Study 300 minutes this week [medium]\n"
        "  Reward: 45 fun minutes\n"
        "  Progress: 180/300 (60%)"
    ),

    # Page 2: Viewing quests
    (
        "Viewing Quests\n"
        "\n"
        "See your active quests:\n"
        "  /quests\n"
        "\n"
        "This shows all quests for the current week with:\n"
        "- Quest title and difficulty\n"
        "- A progress bar showing completion percentage\n"
        "- Current value vs target\n"
        "- Reward amount\n"
        "- Status (active, completed, or failed)\n"
        "\n"
        "Example output:\n"
        "  Active Quests:\n"
        "  1. Study 300 minutes [medium]\n"
        "     [========>         ] 180/300 (60%)\n"
        "     Reward: 45m fun\n"
        "\n"
        "  2. Log every day this week [hard]\n"
        "     [=============>    ] 5/7 days\n"
        "     Reward: 60m fun\n"
        "\n"
        "Quests update automatically as you log time. You don't need "
        "to manually mark them as complete."
    ),

    # Page 3: Quest types
    (
        "Quest Types\n"
        "\n"
        "Quests use different condition types to track progress:\n"
        "\n"
        "Time-based:\n"
        "  \"Study 300 minutes\" - total time in a category\n"
        "  \"Build 5 hours\" - same, different unit\n"
        "  \"Log 10 hours total\" - across all categories\n"
        "\n"
        "Frequency-based:\n"
        "  \"Log every day this week\" - daily consistency\n"
        "  \"Study at least 5 days\" - minimum active days\n"
        "\n"
        "Session-based:\n"
        "  \"Complete 3 deep work sessions\" - sessions 60+ min\n"
        "  \"Do 5 study sessions\" - any length study entries\n"
        "\n"
        "Category-specific:\n"
        "  \"Spend 2 hours on training\" - specific category\n"
        "  \"Build for 4 hours\" - another specific category\n"
        "\n"
        "Categories available:\n"
        "  study, build, training, job\n"
        "\n"
        "You can ask the AI to create custom quests:\n"
        "  /llm suggest a quest for daily study practice"
    ),

    # Page 4: Quest history
    (
        "Quest History\n"
        "\n"
        "See completed and failed quests from this week:\n"
        "  /quests history\n"
        "\n"
        "History shows:\n"
        "- Quest title and difficulty\n"
        "- Whether it was completed or failed\n"
        "- Final progress at completion/expiry\n"
        "- Reward earned (for completed quests)\n"
        "\n"
        "Completed quests automatically add the reward to your fun "
        "minutes balance. Failed quests give no reward.\n"
        "\n"
        "Quest lifecycle:\n"
        "  1. Quest is created (manually or auto-generated)\n"
        "  2. You log time throughout the week\n"
        "  3. Progress updates automatically\n"
        "  4. At week end: completed = reward, incomplete = failed\n"
        "\n"
        "Strategy tips:\n"
        "- Check /quests daily to see what's close to finishing\n"
        "- Focus on nearly-complete quests for easy wins\n"
        "- Hard quests give the best rewards but need consistency"
    ),

    # Page 5: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "View active quests:\n"
        "  /quests\n"
        "\n"
        "View quest history:\n"
        "  /quests history\n"
        "\n"
        "Ask AI to create a quest:\n"
        "  /llm suggest a quest for studying 2 hours daily\n"
        "  /llm create an easy quest for this week\n"
        "\n"
        "Difficulty levels:\n"
        "  easy   - Low effort, small rewards\n"
        "  medium - Moderate effort, good rewards\n"
        "  hard   - High effort, best rewards\n"
        "\n"
        "Condition types:\n"
        "  - Total time in a category\n"
        "  - Number of active days\n"
        "  - Deep work sessions (60+ min)\n"
        "  - Session count\n"
        "\n"
        "Categories: study, build, training, job\n"
        "\n"
        "Quests are weekly. They reset each week.\n"
        "Rewards are fun minutes added to your balance."
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
        "  - Different categories have different earn rates\n"
        "  - Quest rewards also add fun minutes\n"
        "  - Level-up bonuses add fun minutes\n"
        "\n"
        "Spending:\n"
        "  - Log fun/consumption time with /spend\n"
        "  - This deducts from your fun minutes balance\n"
        "  - Redeem shop items (costs fun minutes)\n"
        "  - Buy streak freezes (200 fun minutes)\n"
        "\n"
        "The idea: productive work earns you guilt-free leisure time. "
        "The more you study/build, the more fun time you can spend.\n"
        "\n"
        "Check your balance:\n"
        "  /status - shows current fun minutes remaining\n"
        "  /week   - shows this week's earn/spend breakdown"
    ),

    # Page 2: Shop basics
    (
        "Shop Basics\n"
        "\n"
        "The shop is your personal reward catalog. Add items you "
        "want to earn through productive time.\n"
        "\n"
        "View your shop:\n"
        "  /shop\n"
        "\n"
        "Add an item with a time-based cost:\n"
        "  /shop add <emoji> \"<name>\" <duration>\n"
        "\n"
        "Examples:\n"
        "  /shop add \U0001f3ae \"Gaming session\" 120m\n"
        "  /shop add \U0001f355 \"Pizza night\" 3h\n"
        "  /shop add \u231a \"Apple Watch\" 250h\n"
        "\n"
        "Add an item with a NOK price (auto-converts to minutes):\n"
        "  /shop add \U0001f3a7 \"AirPods\" 2490nok\n"
        "\n"
        "Add with both duration and NOK (for reference):\n"
        "  /shop add \U0001f3a7 \"AirPods\" 4000 2490\n"
        "\n"
        "Remove an item:\n"
        "  /shop remove <item_id>\n"
        "  /shop remove 3\n"
        "\n"
        "Each item shows its cost in fun minutes and optional NOK value."
    ),

    # Page 3: Price scouting
    (
        "Price Scouting\n"
        "\n"
        "Don't know the price? Let the bot search the web for you.\n"
        "\n"
        "Search for a price:\n"
        "  /shop price <emoji> \"<name>\" <search query>\n"
        "\n"
        "Example:\n"
        "  /shop price \u231a \"Apple Watch\" apple watch se price norway\n"
        "\n"
        "The bot will:\n"
        "1. Search the web using your query\n"
        "2. Extract the best price in NOK\n"
        "3. Show the price and ask if you want to add it\n"
        "4. Display an \"Add to shop\" button for confirmation\n"
        "\n"
        "To search AND auto-add in one step:\n"
        "  /shop price \u231a \"Apple Watch\" apple watch price --add\n"
        "\n"
        "The --add flag skips the confirmation step.\n"
        "\n"
        "Tips for good results:\n"
        "  - Include the country (e.g., \"norway\")\n"
        "  - Be specific about the model/variant\n"
        "  - Try \"<product> price <store>\" for specific retailers\n"
        "\n"
        "The price confirmation button expires after 20 minutes."
    ),

    # Page 4: Redeeming rewards
    (
        "Redeeming Rewards\n"
        "\n"
        "When you've earned enough fun minutes, redeem a shop item.\n"
        "\n"
        "Redeem by ID:\n"
        "  /redeem 3\n"
        "\n"
        "Redeem by name:\n"
        "  /redeem AirPods\n"
        "\n"
        "What happens when you redeem:\n"
        "1. Bot checks if you have enough fun minutes\n"
        "2. Savings fund is used first (if available)\n"
        "3. Remaining cost comes from your fun balance\n"
        "4. Item is marked as redeemed with timestamp\n"
        "\n"
        "Example:\n"
        "  Item costs 4000 fun minutes\n"
        "  Your savings: 1500\n"
        "  Your balance: 3000\n"
        "  Result: 1500 from savings + 2500 from balance = redeemed!\n"
        "\n"
        "View redemption history:\n"
        "  /redeem history\n"
        "\n"
        "This shows all past redemptions with dates and costs."
    ),

    # Page 5: Savings fund
    (
        "Savings Fund\n"
        "\n"
        "The savings fund lets you set aside fun minutes for "
        "expensive items. Saved minutes are locked and won't be "
        "spent by /spend.\n"
        "\n"
        "View your savings:\n"
        "  /save\n"
        "\n"
        "Deposit into savings:\n"
        "  /save fund 200m\n"
        "  /save fund 2h\n"
        "\n"
        "Set a savings goal:\n"
        "  /save goal 5000m Apple Watch fund\n"
        "  /save goal 100h Big purchase\n"
        "\n"
        "Goals help you track progress toward expensive items. "
        "Your fund balance counts toward the goal.\n"
        "\n"
        "Cancel a goal (keeps the fund):\n"
        "  /save cancel <goal_id>\n"
        "\n"
        "How it works with /redeem:\n"
        "  When you redeem an item, savings fund is used first "
        "  before touching your regular balance. This means you "
        "  can save specifically for big purchases."
    ),

    # Page 6: Budget and auto-save
    (
        "Budget and Auto-Save\n"
        "\n"
        "Set a monthly fun spend budget:\n"
        "  /shop budget 2000\n"
        "  /shop budget off\n"
        "\n"
        "The budget tracks how much fun time you spend per month. "
        "It doesn't block spending but shows you warnings when "
        "you're close to your limit.\n"
        "\n"
        "Auto-save on Sundays:\n"
        "  /save sunday on 50\n"
        "  /save sunday on 60\n"
        "  /save sunday on 70\n"
        "  /save sunday off\n"
        "\n"
        "This automatically transfers a percentage of your remaining "
        "fun minutes to savings every Sunday. For example:\n"
        "  - Balance: 500 fun minutes\n"
        "  - /save sunday on 50\n"
        "  - Every Sunday: 250 minutes moved to savings\n"
        "\n"
        "Daily auto-save:\n"
        "  /save auto 30m\n"
        "\n"
        "This saves a fixed amount each day automatically. Great "
        "for steady savings toward a goal."
    ),

    # Page 7: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Shop:\n"
        "  /shop              - View items\n"
        "  /shop add <e> \"n\" <cost> - Add item\n"
        "  /shop price <e> \"n\" <q>  - Search price\n"
        "  /shop remove <id>  - Remove item\n"
        "  /shop budget <min> - Set monthly budget\n"
        "\n"
        "Redeem:\n"
        "  /redeem <id|name>  - Redeem item\n"
        "  /redeem history    - Past redemptions\n"
        "\n"
        "Savings:\n"
        "  /save              - View savings\n"
        "  /save fund <dur>   - Deposit to fund\n"
        "  /save goal <dur> [name] - Set goal\n"
        "  /save cancel <id>  - Cancel goal\n"
        "  /save sunday on <50|60|70> - Auto weekly save\n"
        "  /save sunday off   - Disable weekly save\n"
        "  /save auto <dur>   - Daily auto-save\n"
        "\n"
        "Economy flow:\n"
        "  Productive time -> fun minutes -> shop/spend\n"
        "  Savings lock fun minutes for expensive items\n"
        "  Redeem uses savings first, then balance"
    ),
]


_LOGGING_PAGES: list[str] = [
    # Page 1: Overview
    (
        "Time Tracking Overview\n"
        "\n"
        "This bot helps you track how you spend your time and "
        "rewards productive work with fun time.\n"
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
        "  Timer:  /start study then /stop when done\n"
        "\n"
        "Everything you log contributes to:\n"
        "  - Your weekly totals and plan progress\n"
        "  - Your level and XP progression\n"
        "  - Your streak (log every day to maintain it)\n"
        "  - Your fun minutes economy"
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
        "If you skip the category, it defaults to \"build\".\n"
        "\n"
        "Each log entry earns:\n"
        "  - Fun minutes (varies by category)\n"
        "  - XP toward leveling up\n"
        "  - Progress toward weekly plan\n"
        "  - Progress toward active quests\n"
        "\n"
        "Other activities (no XP, no fun — just context):\n"
        "  /log 30m other morning walk\n"
        "  /log 20m other breakfast\n"
        "  /log 8h other sleep\n"
        "Coach and /llm can see these for full-day context."
    ),

    # Page 3: Logging fun time
    (
        "Logging Fun Time\n"
        "\n"
        "Command:\n"
        "  /spend <duration> [note]\n"
        "\n"
        "Examples:\n"
        "  /spend 40m YouTube\n"
        "  /spend 2h movie night\n"
        "  /spend 30m social media\n"
        "  /spend 1h gaming\n"
        "\n"
        "When you /spend:\n"
        "  - Fun minutes are deducted from your balance\n"
        "  - The time is recorded in your logs\n"
        "  - It appears in your weekly summary\n"
        "\n"
        "You can go negative on fun minutes, but it means you've "
        "spent more leisure time than you've earned.\n"
        "\n"
        "Why track fun time?\n"
        "  - See how much leisure you actually consume\n"
        "  - Balance productive and fun activities\n"
        "  - Stay accountable to your goals\n"
        "  - The economy motivates more productive time\n"
        "\n"
        "Undo a mistake:\n"
        "  /undo\n"
        "Removes your last log entry (productive or spend)."
    ),

    # Page 4: Timer mode
    (
        "Timer Mode\n"
        "\n"
        "Instead of estimating time, you can use a live timer.\n"
        "\n"
        "Start a timer:\n"
        "  /start                    - Default (build)\n"
        "  /start study              - Study timer\n"
        "  /start build backend work - Build with note\n"
        "  /start spend gaming       - Fun timer\n"
        "\n"
        "Stop the timer:\n"
        "  /stop\n"
        "\n"
        "When you stop:\n"
        "  - Elapsed time is calculated automatically\n"
        "  - Time is rounded to the nearest minute\n"
        "  - Entry is logged as if you used /log or /spend\n"
        "\n"
        "Deep work bonus:\n"
        "  Sessions of 60+ minutes earn a deep work bonus. "
        "  This gives extra XP. These sessions also count "
        "  toward \"deep work\" quest conditions.\n"
        "\n"
        "You can only have one active timer at a time. Starting a "
        "new timer while one is running will show an error.\n"
        "\n"
        "Check if a timer is running:\n"
        "  /status - shows active timer if any"
    ),

    # Page 5: Weekly planning
    (
        "Weekly Planning\n"
        "\n"
        "Set a weekly goal for productive time:\n"
        "  /plan set 20h\n"
        "  /plan set 1500m\n"
        "\n"
        "View current plan:\n"
        "  /plan show\n"
        "  /plan\n"
        "\n"
        "The plan tracks total productive time across all categories "
        "for the current week (Monday to Sunday).\n"
        "\n"
        "See your weekly summary:\n"
        "  /week\n"
        "\n"
        "This shows:\n"
        "  - Total productive time this week\n"
        "  - Plan progress (e.g., 12h / 20h = 60%)\n"
        "  - Total fun time spent\n"
        "  - XP earned this week\n"
        "  - Deep work sessions count\n"
        "  - Fun minutes remaining\n"
        "\n"
        "Quick status check:\n"
        "  /status\n"
        "\n"
        "Shows level, XP, streak, week totals, plan progress, "
        "economy balance, and active quest count."
    ),

    # Page 6: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Log productive time:\n"
        "  /log <duration> [study|build|training|job] [note]\n"
        "  /log 90m study math homework\n"
        "\n"
        "Log other activities (no XP/fun):\n"
        "  /log <duration> other <description>\n"
        "  /log 30m other lunch break\n"
        "\n"
        "Log fun time:\n"
        "  /spend <duration> [note]\n"
        "  /spend 1h Netflix\n"
        "\n"
        "Timer:\n"
        "  /start [category] [note]\n"
        "  /stop\n"
        "\n"
        "Undo last entry:\n"
        "  /undo\n"
        "\n"
        "Weekly plan:\n"
        "  /plan set <duration>\n"
        "  /plan show\n"
        "\n"
        "View progress:\n"
        "  /status - Quick overview\n"
        "  /week   - Weekly breakdown\n"
        "\n"
        "Duration formats:\n"
        "  90m, 1.5h, 1h30m, 90 (minutes)\n"
        "\n"
        "Categories:\n"
        "  study, build (default), training, job"
    ),
]


_SEARCH_PAGES: list[str] = [
    # Page 1: What is /search?
    (
        "What is /search?\n"
        "\n"
        "/search lets you run web searches directly from Telegram "
        "without opening a browser.\n"
        "\n"
        "Usage:\n"
        "  /search <your query>\n"
        "\n"
        "Example:\n"
        "  /search best noise cancelling headphones 2025\n"
        "\n"
        "The bot will:\n"
        "1. Send your query to a search provider\n"
        "2. Collect the top results\n"
        "3. Return titles, snippets, and links\n"
        "\n"
        "Results are formatted for easy reading right in your "
        "Telegram chat. You get the most relevant results without "
        "leaving the app.\n"
        "\n"
        "This is also used internally by other features:\n"
        "  - /shop price uses search to find product prices\n"
        "  - /llm research skill uses search for web research\n"
        "\n"
        "Requires at least one search API key configured by admin "
        "(Brave, Tavily, or Serper)."
    ),

    # Page 2: Usage examples
    (
        "Usage Examples\n"
        "\n"
        "Product research:\n"
        "  /search apple watch se price norway\n"
        "  /search best budget laptop 2025\n"
        "\n"
        "Learning resources:\n"
        "  /search python machine learning tutorial\n"
        "  /search best books on productivity\n"
        "\n"
        "Current events:\n"
        "  /search latest tech news today\n"
        "  /search weather oslo tomorrow\n"
        "\n"
        "Technical questions:\n"
        "  /search how to set up docker on mac\n"
        "  /search python asyncio best practices\n"
        "\n"
        "Comparison shopping:\n"
        "  /search airpods pro vs sony wf-1000xm5\n"
        "  /search cheapest flights oslo london march\n"
        "\n"
        "Tips for better results:\n"
        "  - Be specific with your query\n"
        "  - Include relevant context (year, location)\n"
        "  - Use natural language, like you would in Google"
    ),

    # Page 3: Providers
    (
        "Search Providers\n"
        "\n"
        "The bot tries multiple search engines in order, falling "
        "back if one fails:\n"
        "\n"
        "1. Brave Search (primary)\n"
        "   - Privacy-focused search engine\n"
        "   - Good general results\n"
        "\n"
        "2. Tavily (fallback 1)\n"
        "   - AI-optimized search API\n"
        "   - Good for factual queries\n"
        "\n"
        "3. Serper (fallback 2)\n"
        "   - Google-based search API\n"
        "   - Most comprehensive results\n"
        "\n"
        "The bot automatically uses whichever provider is available. "
        "You don't need to configure anything as a user.\n"
        "\n"
        "Result caching:\n"
        "  - Results are cached for a period of time\n"
        "  - Duplicate results across providers are removed\n"
        "  - Searching the same query again is faster"
    ),

    # Page 4: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Search the web:\n"
        "  /search <query>\n"
        "\n"
        "Examples:\n"
        "  /search best study techniques\n"
        "  /search apple watch price norway\n"
        "  /search python async tutorial\n"
        "\n"
        "Results include:\n"
        "  - Page titles\n"
        "  - Brief descriptions/snippets\n"
        "  - Direct links\n"
        "\n"
        "Related features:\n"
        "  /shop price - uses search for product prices\n"
        "  /llm research ... - deep search with AI analysis\n"
        "\n"
        "No configuration needed on your end.\n"
        "The admin configures which search providers are active."
    ),
]


_SETTINGS_PAGES: list[str] = [
    # Page 1: Language
    (
        "Language Settings\n"
        "\n"
        "The bot supports two languages:\n"
        "  en - English (default)\n"
        "  uk - Ukrainian\n"
        "\n"
        "Check your current language:\n"
        "  /lang\n"
        "\n"
        "Set language to English:\n"
        "  /lang en\n"
        "\n"
        "Set language to Ukrainian:\n"
        "  /lang uk\n"
        "\n"
        "What changes with language:\n"
        "  - Status and week messages\n"
        "  - Error messages and prompts\n"
        "  - System messages from the bot\n"
        "  - Coach responds in your language\n"
        "\n"
        "What stays in English:\n"
        "  - Command names (/log, /spend, etc.)\n"
        "  - Help and guide content\n"
        "  - Category names (study, build, etc.)\n"
        "\n"
        "Your language preference is saved and persists across sessions."
    ),

    # Page 2: Reminders
    (
        "Reminders and Quiet Hours\n"
        "\n"
        "The bot can send periodic reminders to log your time.\n"
        "\n"
        "Toggle reminders:\n"
        "  /reminders on\n"
        "  /reminders off\n"
        "\n"
        "When reminders are on, the bot will periodically nudge you "
        "to log time if you haven't logged recently.\n"
        "\n"
        "Set quiet hours (no reminders during this window):\n"
        "  /quiet_hours 22:00-08:00\n"
        "\n"
        "This suppresses all reminders between 10 PM and 8 AM. "
        "Use 24-hour format (HH:MM-HH:MM).\n"
        "\n"
        "Examples:\n"
        "  /quiet_hours 23:00-07:00  - Sleep hours\n"
        "  /quiet_hours 09:00-17:00  - Work hours\n"
        "  /quiet_hours 00:00-06:00  - Late night only\n"
        "\n"
        "Reminders are per-user. Each person can have their own "
        "schedule and quiet hours."
    ),

    # Page 3: Rules
    (
        "Personal Rules\n"
        "\n"
        "/rules lets you maintain a personal rulebook or notes. "
        "These are text entries you save for yourself.\n"
        "\n"
        "View your rules:\n"
        "  /rules\n"
        "\n"
        "Add a rule:\n"
        "  /rules add No social media before noon\n"
        "  /rules add Study at least 1 hour every morning\n"
        "  /rules add Always log time right after a session\n"
        "\n"
        "Remove a rule by ID:\n"
        "  /rules remove 2\n"
        "\n"
        "Clear all rules:\n"
        "  /rules clear\n"
        "\n"
        "Important: Rules are notes for yourself. They don't change "
        "how the bot works. The bot won't enforce them.\n"
        "\n"
        "However, the AI Coach can see your rules and may reference "
        "them when giving advice. For example, if you have a rule "
        "\"Study 2 hours before lunch\", Coach may ask how you're "
        "doing on that commitment."
    ),

    # Page 4: Quick reference
    (
        "Quick Reference\n"
        "\n"
        "Language:\n"
        "  /lang         - Show current language\n"
        "  /lang en      - Set to English\n"
        "  /lang uk      - Set to Ukrainian\n"
        "\n"
        "Reminders:\n"
        "  /reminders on  - Enable reminders\n"
        "  /reminders off - Disable reminders\n"
        "  /quiet_hours HH:MM-HH:MM - Set quiet window\n"
        "\n"
        "Personal rules:\n"
        "  /rules           - View rules\n"
        "  /rules add <text> - Add a rule\n"
        "  /rules remove <id> - Remove a rule\n"
        "  /rules clear     - Clear all rules\n"
        "\n"
        "Streak freeze:\n"
        "  /freeze - Buy tomorrow's streak freeze\n"
        "  Cost: 200 fun minutes\n"
        "  Prevents streak loss if you don't log tomorrow\n"
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
        "The LLM agent can add multiple items in one message and "
        "understands 'today', 'tomorrow', or specific dates."
    ),
    # Page 3: Completing tasks
    (
        "Completing tasks\n"
        "\n"
        "When you type /todo, you see your list with tick buttons:\n"
        "\n"
        "  Plan for 13.02 (0/3):\n"
        "  1. ⬜ improve tg bot (2h)\n"
        "  2. ⬜ training (1h)\n"
        "  3. ⬜ meeting with boss\n"
        "  [✅1] [✅2] [✅3]\n"
        "\n"
        "Tap a button to mark it done. The list updates in-place.\n"
        "\n"
        "Auto-categorize:\n"
        "If the task has a duration, the bot calls the AI to suggest "
        "a log category (study/build/training/other) and sends:\n"
        "\n"
        "  ✅ training (1h) — done!\n"
        "  Log as 60m training?\n"
        "  [Accept] [Decline]\n"
        "\n"
        "- Accept: logs the time entry automatically\n"
        "- Decline: nothing logged, task stays marked done\n"
        "\n"
        "Tasks without duration are simply marked done with "
        "no logging suggestion.\n"
        "\n"
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
        "- Job category is not auto-suggested (log manually)\n"
        "- /todo clear only removes pending tasks, not done"
    ),
]


GUIDE_PAGES: dict[str, list[str]] = {
    "coach": _COACH_PAGES,
    "llm": _LLM_PAGES,
    "logging": _LOGGING_PAGES,
    "quests": _QUESTS_PAGES,
    "search": _SEARCH_PAGES,
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
