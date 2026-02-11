from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str = "openrouter"
    reasoning: bool = True


@dataclass(frozen=True)
class TierSpec:
    name: str
    description: str
    models: tuple[ModelSpec, ...]


@dataclass(frozen=True)
class ModelConfig:
    default_tier: str
    tiers: dict[str, TierSpec]

    def get_tier(self, name: str) -> TierSpec | None:
        return self.tiers.get(name)


def load_model_config(path: Path) -> ModelConfig:
    if not path.exists():
        fallback = TierSpec(
            name="free",
            description="Fallback free tier",
            models=(
                ModelSpec(id="arcee-ai/trinity-large-preview:free", provider="openrouter", reasoning=True),
            ),
        )
        return ModelConfig(default_tier="free", tiers={"free": fallback})

    raw = yaml.safe_load(path.read_text()) or {}
    default_tier = str(raw.get("default_tier", "free"))
    tiers_raw = raw.get("tiers", {}) if isinstance(raw, dict) else {}
    tiers: dict[str, TierSpec] = {}

    if isinstance(tiers_raw, dict):
        for name, payload in tiers_raw.items():
            if not isinstance(payload, dict):
                continue
            desc = str(payload.get("description", "")).strip()
            models_raw = payload.get("models", [])
            models: list[ModelSpec] = []
            if isinstance(models_raw, list):
                for item in models_raw:
                    if not isinstance(item, dict):
                        continue
                    mid = str(item.get("id", "")).strip()
                    if not mid:
                        continue
                    models.append(
                        ModelSpec(
                            id=mid,
                            provider=str(item.get("provider", "openrouter")).strip() or "openrouter",
                            reasoning=bool(item.get("reasoning", True)),
                        )
                    )
            if models:
                tiers[str(name)] = TierSpec(name=str(name), description=desc, models=tuple(models))

    if default_tier not in tiers:
        first = next(iter(tiers.keys()), "free")
        default_tier = first
    if not tiers:
        fallback = TierSpec(
            name="free",
            description="Fallback free tier",
            models=(
                ModelSpec(id="arcee-ai/trinity-large-preview:free", provider="openrouter", reasoning=True),
            ),
        )
        tiers = {"free": fallback}
        default_tier = "free"

    return ModelConfig(default_tier=default_tier, tiers=tiers)


def get_tier_order(config: ModelConfig, requested_tier: str | None, allow_escalation: bool) -> list[str]:
    requested = requested_tier or config.default_tier
    keys = list(config.tiers.keys())
    if requested not in config.tiers:
        requested = config.default_tier
    if not allow_escalation:
        return [requested]
    ordered = [requested]
    for key in keys:
        if key not in ordered:
            ordered.append(key)
    return ordered


def get_int(cfg: dict[str, Any], key: str, default: int, min_value: int = 0) -> int:
    try:
        value = int(cfg.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, value)
