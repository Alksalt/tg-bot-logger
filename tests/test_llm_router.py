from pathlib import Path

from tg_time_logger.llm_router import load_router_config, resolve_route


def test_router_defaults_to_gpt5_mini(tmp_path: Path) -> None:
    cfg_file = tmp_path / "router.yaml"
    cfg_file.write_text(
        """
default_provider: openai
default_model: gpt-5-mini
providers:
  openai:
    env_key: OPENAI_API_KEY
    models:
      - gpt-5-mini
      - gpt-5-nano
""".strip()
    )

    cfg = load_router_config(cfg_file)
    route = resolve_route(cfg, provider_override=None, model_override=None, env_getter=lambda k: "x")

    assert route.provider == "openai"
    assert route.model == "gpt-5-mini"


def test_router_falls_back_to_provider_default_model(tmp_path: Path) -> None:
    cfg_file = tmp_path / "router.yaml"
    cfg_file.write_text(
        """
default_provider: anthropic
default_model: claude-haiku-4-5
providers:
  openai:
    env_key: OPENAI_API_KEY
    models:
      - gpt-5-mini
  anthropic:
    env_key: ANTHROPIC_API_KEY
    models:
      - claude-haiku-4-5
""".strip()
    )

    cfg = load_router_config(cfg_file)
    route = resolve_route(cfg, provider_override="anthropic", model_override="not-real", env_getter=lambda k: "k")

    assert route.provider == "anthropic"
    assert route.model == "claude-haiku-4-5"
