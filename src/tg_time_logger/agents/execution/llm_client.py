from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from tg_time_logger.agents.execution.config import ModelSpec


@dataclass(frozen=True)
class LlmResponse:
    text: str
    model_id: str


def _extract_text(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(str(item["text"]))
        joined = "\n".join(chunks).strip()
        return joined or None
    return None


def call_openrouter(
    model: ModelSpec,
    messages: list[dict[str, str]],
    api_key: str,
    max_tokens: int,
    reasoning_enabled: bool,
    timeout_seconds: int = 45,
) -> LlmResponse | None:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if reasoning_enabled and model.reasoning:
        payload["reasoning"] = {"enabled": True}

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return None
            data = resp.json()
    except Exception:
        return None

    text = _extract_text(data)
    if not text:
        return None
    return LlmResponse(text=text, model_id=model.id)


def call_openai(
    model: ModelSpec,
    messages: list[dict[str, str]],
    api_key: str,
    max_tokens: int,
    timeout_seconds: int = 45,
) -> LlmResponse | None:
    """Call OpenAI API directly (also works for OpenAI-compatible endpoints)."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return None
            data = resp.json()
    except Exception:
        return None
    text = _extract_text(data)
    if not text:
        return None
    return LlmResponse(text=text, model_id=model.id)


def call_google(
    model: ModelSpec,
    messages: list[dict[str, str]],
    api_key: str,
    max_tokens: int,
    timeout_seconds: int = 45,
) -> LlmResponse | None:
    """Call Google Gemini API via OpenAI-compatible endpoint."""
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return None
            data = resp.json()
    except Exception:
        return None
    text = _extract_text(data)
    if not text:
        return None
    return LlmResponse(text=text, model_id=model.id)


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    chunks: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                chunks.append(text)
    joined = "\n".join(chunks).strip()
    return joined or None


def call_anthropic(
    model: ModelSpec,
    messages: list[dict[str, str]],
    api_key: str,
    max_tokens: int,
    timeout_seconds: int = 45,
) -> LlmResponse | None:
    """Call Anthropic Messages API directly."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    # Anthropic requires system as a separate field, not in messages
    system_text = ""
    user_messages: list[dict[str, str]] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text += msg.get("content", "") + "\n"
        else:
            user_messages.append(msg)
    payload: dict[str, Any] = {
        "model": model.id,
        "messages": user_messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if system_text.strip():
        payload["system"] = system_text.strip()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return None
            data = resp.json()
    except Exception:
        return None
    text = _extract_anthropic_text(data)
    if not text:
        return None
    return LlmResponse(text=text, model_id=model.id)


def parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = cleaned[start : end + 1]
    try:
        obj = json.loads(snippet)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None
