from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from tg_time_logger.agents.tools.base import Tool, ToolContext, ToolResult
from tg_time_logger.agents.tools.utils import normalize_query


@dataclass(frozen=True)
class SearchItem:
    title: str
    url: str
    snippet: str
    provider: str


def _short(items: list[SearchItem], limit: int = 5) -> str:
    lines: list[str] = []
    for item in items[:limit]:
        lines.append(f"- {item.title}\n  {item.url}\n  {item.snippet}")
    return "\n".join(lines)


def _brave_search(query: str, key: str, max_results: int) -> list[SearchItem]:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    with httpx.Client(timeout=20) as client:
        resp = client.get(url, headers=headers, params={"q": query, "count": max_results})
        resp.raise_for_status()
        data = resp.json()
    rows = data.get("web", {}).get("results", [])
    results: list[SearchItem] = []
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        url_val = str(row.get("url", "")).strip()
        snippet = str(row.get("description", "")).strip()
        if title and url_val:
            results.append(SearchItem(title=title, url=url_val, snippet=snippet, provider="brave"))
    return results


def _tavily_search(query: str, key: str, max_results: int) -> list[SearchItem]:
    url = "https://api.tavily.com/search"
    payload = {"api_key": key, "query": query, "max_results": max_results}
    with httpx.Client(timeout=20) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    rows = data.get("results", [])
    results: list[SearchItem] = []
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        url_val = str(row.get("url", "")).strip()
        snippet = str(row.get("content", "")).strip()
        if title and url_val:
            results.append(SearchItem(title=title, url=url_val, snippet=snippet, provider="tavily"))
    return results


def _serper_search(query: str, key: str, max_results: int) -> list[SearchItem]:
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    with httpx.Client(timeout=20) as client:
        resp = client.post(url, headers=headers, json={"q": query, "num": max_results})
        resp.raise_for_status()
        data = resp.json()
    rows = data.get("organic", [])
    results: list[SearchItem] = []
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        url_val = str(row.get("link", "")).strip()
        snippet = str(row.get("snippet", "")).strip()
        if title and url_val:
            results.append(SearchItem(title=title, url=url_val, snippet=snippet, provider="serper"))
    return results


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web for current information. "
        "Args: {\"query\": str, \"max_results\": int (optional)}"
    )
    tags = ("search", "web")

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query_raw = str(args.get("query", "")).strip()
        if not query_raw:
            return ToolResult(ok=False, content="Missing query", metadata={"provider": None, "cached": False})
        max_results = int(args.get("max_results", 5) or 5)
        max_results = min(max(1, max_results), 8)

        normalized = normalize_query(query_raw)
        cache_key = hashlib.sha256(f"{normalized}:{max_results}".encode("utf-8")).hexdigest()
        ttl = int(ctx.config.get("search.cache_ttl_seconds", 21600) or 21600)
        cached = ctx.db.get_tool_cache(self.name, cache_key, ctx.now)
        if cached:
            content = str(cached.get("content", "")).strip()
            provider = str(cached.get("provider") or "cache")
            ctx.db.record_search_provider_event(
                provider=provider,
                now=ctx.now,
                success=True,
                cached=True,
                rate_limited=False,
            )
            return ToolResult(ok=True, content=content, metadata={"cached": True, "provider": provider})

        provider_order_raw = str(ctx.config.get("search.provider_order", "brave,tavily,serper"))
        provider_order = [p.strip().lower() for p in provider_order_raw.split(",") if p.strip()]
        results: list[SearchItem] = []
        selected_provider: str | None = None
        errors: dict[str, str] = {}

        for provider in provider_order:
            enabled_key = f"search.{provider}_enabled"
            if not bool(ctx.config.get(enabled_key, True)):
                continue
            try:
                if provider == "brave":
                    if not ctx.settings.brave_search_api_key:
                        continue
                    results = _brave_search(query_raw, ctx.settings.brave_search_api_key, max_results)
                elif provider == "tavily":
                    if not ctx.settings.tavily_api_key:
                        continue
                    results = _tavily_search(query_raw, ctx.settings.tavily_api_key, max_results)
                elif provider == "serper":
                    if not ctx.settings.serper_api_key:
                        continue
                    results = _serper_search(query_raw, ctx.settings.serper_api_key, max_results)
                else:
                    continue
                if results:
                    selected_provider = provider
                    ctx.db.record_search_provider_event(
                        provider=provider,
                        now=ctx.now,
                        success=True,
                        cached=False,
                        rate_limited=False,
                    )
                    break
                errors[provider] = "No results"
                ctx.db.record_search_provider_event(
                    provider=provider,
                    now=ctx.now,
                    success=False,
                    cached=False,
                    rate_limited=False,
                    error="No results",
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                msg = f"HTTP {status}" if status else str(exc)
                errors[provider] = msg
                ctx.db.record_search_provider_event(
                    provider=provider,
                    now=ctx.now,
                    success=False,
                    cached=False,
                    rate_limited=(status == 429),
                    status_code=status,
                    error=msg,
                )
            except Exception as exc:
                errors[provider] = str(exc)
                ctx.db.record_search_provider_event(
                    provider=provider,
                    now=ctx.now,
                    success=False,
                    cached=False,
                    rate_limited=False,
                    error=str(exc),
                )
                continue

        deduped: list[SearchItem] = []
        seen_urls: set[str] = set()
        for item in results:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            deduped.append(item)

        if not deduped:
            err_text = ", ".join(f"{k}: {v}" for k, v in errors.items()) if errors else "No provider returned results"
            return ToolResult(ok=False, content=f"Search failed: {err_text}", metadata={"provider": selected_provider, "cached": False})

        content = _short(deduped, limit=max_results)
        ctx.db.set_tool_cache(
            tool_name=self.name,
            cache_key=cache_key,
            payload={"content": content, "provider": selected_provider or "unknown"},
            fetched_at=ctx.now,
            ttl_seconds=ttl,
        )
        return ToolResult(
            ok=True,
            content=content,
            metadata={
                "provider": selected_provider,
                "cached": False,
                "count": len(deduped),
            },
        )
