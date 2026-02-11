from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from tg_time_logger.config import Settings
from tg_time_logger.db import Database, Entry
from tg_time_logger.service import compute_status
from tg_time_logger.time_utils import week_range_for

NOTION_VERSION = "2022-06-28"
MAX_NOTION_TEXT = 1800
MAX_BLOCKS = 80


@dataclass(frozen=True)
class NotionBackupRecord:
    user_id: int
    path: Path
    remote_status: str
    remote_message: str


def _entry_to_dict(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "category": entry.category,
        "minutes": entry.minutes,
        "xp_earned": entry.xp_earned,
        "fun_earned": entry.fun_earned,
        "note": entry.note,
        "created_at": entry.created_at.isoformat(),
        "source": entry.source,
    }


def build_backup_payload(db: Database, user_id: int, now: datetime) -> dict[str, Any]:
    view = compute_status(db, user_id, now)
    week = week_range_for(now)
    recent = db.list_recent_entries(user_id, limit=300)
    return {
        "version": "notion-backup-scaffold-v1",
        "generated_at": now.isoformat(),
        "user_id": user_id,
        "week": {
            "start": week.start.isoformat(),
            "end": week.end.isoformat(),
        },
        "status": {
            "level": view.level,
            "title": view.title,
            "xp_total": view.xp_total,
            "xp_week": view.xp_week,
            "streak_current": view.streak_current,
            "streak_longest": view.streak_longest,
            "productive_week_minutes": view.week.productive_minutes,
            "spent_week_minutes": view.week.spent_minutes,
            "fun_remaining_minutes": view.economy.remaining_fun_minutes,
            "plan_done_minutes": view.week_plan_done_minutes,
            "plan_target_minutes": view.week_plan_target_minutes,
            "active_quests": view.active_quests,
        },
        "entries": [_entry_to_dict(e) for e in recent],
    }


def write_local_backup(payload: dict[str, Any], backup_dir: Path, user_id: int, now: datetime) -> Path:
    day_dir = backup_dir / now.date().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_{user_id}_{now.strftime('%H%M%S')}.json"
    path = day_dir / filename
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _notion_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _chunk_text(text: str, chunk_size: int = MAX_NOTION_TEXT) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size
    return chunks


def _resolve_title_property(client: httpx.Client, database_id: str, headers: dict[str, str]) -> str | None:
    resp = client.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers)
    if resp.status_code >= 400:
        return None
    data = resp.json()
    props = data.get("properties")
    if not isinstance(props, dict):
        return None
    for key, payload in props.items():
        if isinstance(payload, dict) and payload.get("type") == "title":
            return str(key)
    return None


def _post_with_retry(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> httpx.Response:
    resp = client.post(url, headers=headers, json=payload)
    if resp.status_code != 429:
        return resp
    retry_after = resp.headers.get("Retry-After")
    wait_seconds = 2
    try:
        if retry_after:
            wait_seconds = max(1, int(retry_after))
    except ValueError:
        wait_seconds = 2
    import time

    time.sleep(min(wait_seconds, 5))
    return client.post(url, headers=headers, json=payload)


def push_to_notion_scaffold(payload: dict[str, Any], settings: Settings) -> tuple[str, str]:
    if not settings.notion_api_key or not settings.notion_database_id:
        return "skipped", "NOTION_API_KEY or NOTION_DATABASE_ID is not configured."
    user_id = int(payload.get("user_id") or 0)
    ts = str(payload.get("generated_at") or "")[:19]
    title = f"TG Backup u{user_id} {ts}"
    payload_text = json.dumps(payload, ensure_ascii=False)
    summary = payload.get("status", {}) if isinstance(payload.get("status"), dict) else {}
    summary_line = (
        f"user={user_id} | level={summary.get('level', 0)} | "
        f"xp_total={summary.get('xp_total', 0)} | "
        f"week_prod={summary.get('productive_week_minutes', 0)}m | "
        f"fun_remaining={summary.get('fun_remaining_minutes', 0)}m"
    )

    try:
        with httpx.Client(timeout=30) as client:
            headers = _notion_headers(settings.notion_api_key)
            title_prop = _resolve_title_property(client, settings.notion_database_id, headers)
            if not title_prop:
                return "failed", "Could not detect title property in Notion database."

            chunks = _chunk_text(payload_text)[:MAX_BLOCKS]
            children: list[dict[str, Any]] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": summary_line[:MAX_NOTION_TEXT]}}
                        ]
                    },
                }
            ]
            for chunk in chunks:
                children.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        },
                    }
                )

            create_payload: dict[str, Any] = {
                "parent": {"database_id": settings.notion_database_id},
                "properties": {
                    title_prop: {
                        "title": [{"type": "text", "text": {"content": title[:180]}}],
                    }
                },
                "children": children,
            }
            resp = _post_with_retry(client, "https://api.notion.com/v1/pages", headers, create_payload)
            if resp.status_code >= 400:
                text = resp.text[:400].replace("\n", " ")
                return "failed", f"Notion API error {resp.status_code}: {text}"
            page_id = str(resp.json().get("id") or "")
            if not page_id:
                return "failed", "Notion API returned no page id."
            return "synced", f"Created page {page_id}"
    except Exception as exc:
        return "failed", f"Notion sync exception: {exc}"


def run_notion_backup_job(db: Database, settings: Settings, now: datetime) -> list[NotionBackupRecord]:
    records: list[NotionBackupRecord] = []
    for profile in db.get_all_user_profiles():
        user_id = int(profile["user_id"])
        payload = build_backup_payload(db, user_id, now)
        local_path = write_local_backup(payload, settings.notion_backup_dir, user_id, now)
        remote_status, remote_message = push_to_notion_scaffold(payload, settings)
        db.add_admin_audit(
            actor="jobs",
            action="notion.backup",
            target=f"user:{user_id}",
            payload={
                "path": str(local_path),
                "remote_status": remote_status,
                "remote_message": remote_message,
                "entries": len(payload.get("entries", [])),
            },
            created_at=now,
        )
        records.append(
            NotionBackupRecord(
                user_id=user_id,
                path=local_path,
                remote_status=remote_status,
                remote_message=remote_message,
            )
        )
    return records
