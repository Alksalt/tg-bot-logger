from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderConfig:
    env_key: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class RouterConfig:
    default_provider: str
    default_model: str
    providers: dict[str, ProviderConfig]


@dataclass(frozen=True)
class LlmRoute:
    provider: str
    model: str
    api_key: str | None


def load_router_config(path: Path) -> RouterConfig:
    if not path.exists():
        return RouterConfig(
            default_provider="openai",
            default_model="gpt-5-mini",
            providers={
                "openai": ProviderConfig(env_key="OPENAI_API_KEY", models=("gpt-5-mini", "gpt-5-nano")),
            },
        )

    lines = path.read_text().splitlines()
    default_provider = "openai"
    default_model = "gpt-5-mini"
    providers: dict[str, ProviderConfig] = {}

    mode = "root"
    current_provider: str | None = None
    current_env_key = ""
    current_models: list[str] = []

    def flush_provider() -> None:
        nonlocal current_provider, current_env_key, current_models
        if not current_provider:
            return
        providers[current_provider] = ProviderConfig(
            env_key=current_env_key or "OPENAI_API_KEY",
            models=tuple(current_models),
        )
        current_provider = None
        current_env_key = ""
        current_models = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if line.startswith("default_provider:"):
            default_provider = line.split(":", 1)[1].strip()
            continue
        if line.startswith("default_model:"):
            default_model = line.split(":", 1)[1].strip()
            continue
        if stripped == "providers:":
            mode = "providers"
            continue

        if mode == "providers" and line.startswith("  ") and line.strip().endswith(":") and not line.strip().startswith("-"):
            flush_provider()
            current_provider = line.strip()[:-1]
            mode = "provider"
            continue

        if mode == "provider" and line.startswith("    env_key:"):
            current_env_key = line.split(":", 1)[1].strip()
            continue

        if mode == "provider" and line.startswith("    models:"):
            mode = "models"
            continue

        if mode == "models" and line.startswith("      - "):
            current_models.append(line.split("-", 1)[1].strip())
            continue

        if mode == "models" and line.startswith("  ") and line.strip().endswith(":") and not line.strip().startswith("-"):
            flush_provider()
            current_provider = line.strip()[:-1]
            mode = "provider"
            continue

    flush_provider()

    if default_provider not in providers:
        providers.setdefault(
            "openai",
            ProviderConfig(env_key="OPENAI_API_KEY", models=("gpt-5-mini", "gpt-5-nano")),
        )
        default_provider = "openai"
        if default_model not in providers[default_provider].models:
            default_model = providers[default_provider].models[0]

    provider_cfg = providers[default_provider]
    if default_model not in provider_cfg.models and provider_cfg.models:
        default_model = provider_cfg.models[0]

    return RouterConfig(
        default_provider=default_provider,
        default_model=default_model,
        providers=providers,
    )


def resolve_route(
    config: RouterConfig,
    provider_override: str | None,
    model_override: str | None,
    env_getter,
) -> LlmRoute:
    provider = (provider_override or config.default_provider).strip().lower()
    if provider not in config.providers:
        provider = config.default_provider

    p_cfg = config.providers[provider]
    model = (model_override or config.default_model).strip()
    if model not in p_cfg.models and p_cfg.models:
        model = p_cfg.models[0]

    api_key = env_getter(p_cfg.env_key)
    return LlmRoute(provider=provider, model=model, api_key=api_key)


def call_text(route: LlmRoute, prompt: str, max_tokens: int) -> str | None:
    if not route.api_key:
        return None

    if route.provider == "openai":
        try:
            from openai import OpenAI

            client = OpenAI(api_key=route.api_key)
            resp = client.responses.create(
                model=route.model,
                input=prompt,
                max_output_tokens=max_tokens,
            )
            text = (resp.output_text or "").strip()
            return text or None
        except Exception:
            return None

    # Provider not wired yet; graceful fallback keeps bot operational.
    return None


def call_messages(route: LlmRoute, messages: list[dict[str, str]], max_tokens: int) -> str | None:
    if not route.api_key:
        return None

    if route.provider == "openai":
        try:
            from openai import OpenAI

            client = OpenAI(api_key=route.api_key)
            resp = client.responses.create(
                model=route.model,
                input=messages,
                max_output_tokens=max_tokens,
            )
            text = (resp.output_text or "").strip()
            return text or None
        except Exception:
            return None

    return None
