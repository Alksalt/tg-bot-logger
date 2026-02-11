from tg_time_logger.agents.orchestration.intent_router import resolve_intent_tags


def test_search_keywords():
    assert "search" in resolve_intent_tags("search for Python tutorials")
    assert "web" in resolve_intent_tags("look up the weather")
    assert "search" in resolve_intent_tags("google best productivity apps")
    assert "web" in resolve_intent_tags("browse recent AI news")


def test_notion_keywords():
    assert "notion" in resolve_intent_tags("backup my data to Notion")
    assert "storage" in resolve_intent_tags("export my entries")
    assert "backup" in resolve_intent_tags("sync my data")


def test_no_match_returns_empty():
    assert resolve_intent_tags("what's my current level?") == set()
    assert resolve_intent_tags("recommend a study plan") == set()
    assert resolve_intent_tags("") == set()


def test_multiple_matches_union():
    tags = resolve_intent_tags("search Notion for my backup")
    assert "search" in tags
    assert "notion" in tags
    assert "backup" in tags


def test_mail_keywords():
    assert "communication" in resolve_intent_tags("send me an email summary")
    assert "mail" in resolve_intent_tags("check my inbox")


def test_maps_keywords():
    assert "maps" in resolve_intent_tags("find nearby coffee shops")
    assert "location" in resolve_intent_tags("get directions to the gym")


def test_api_keywords():
    assert "http" in resolve_intent_tags("fetch url for the endpoint")
    assert "api" in resolve_intent_tags("call the webhook")


def test_case_insensitive():
    assert "search" in resolve_intent_tags("SEARCH for something")
    assert "notion" in resolve_intent_tags("NOTION backup")


def test_data_keywords():
    tags = resolve_intent_tags("how many minutes did I log last week?")
    assert "data" in tags
    assert "stats" in tags
    assert "history" in tags
    tags2 = resolve_intent_tags("compare breakdown of my entries")
    assert "data" in tags2


def test_insights_keywords():
    tags = resolve_intent_tags("give me insights about consistency and bottleneck")
    assert "analytics" in tags
    assert "insights" in tags
    tags2 = resolve_intent_tags("what is my best day pattern?")
    assert "analytics" in tags2


def test_trend_matches_data_and_insights():
    tags = resolve_intent_tags("show trend for build this month")
    assert "data" in tags
    assert "analytics" in tags
