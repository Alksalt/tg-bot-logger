from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Protocol

from tg_time_logger.db_constants import APP_CONFIG_DEFAULTS, JOB_CONFIG_KEYS


class DbProtocol(Protocol):
    def _connect(self) -> sqlite3.Connection: ...
    def get_app_config(self) -> dict[str, Any]: ...
    def get_app_config_value(self, key: str) -> Any: ...


class SystemMixin:
    def get_app_config(self: DbProtocol) -> dict[str, Any]:
        config = dict(APP_CONFIG_DEFAULTS)
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value_json FROM app_config").fetchall()
        for row in rows:
            key = str(row["key"])
            if key not in APP_CONFIG_DEFAULTS:
                continue
            try:
                config[key] = json.loads(str(row["value_json"]))
            except json.JSONDecodeError:
                continue
        return config

    def set_app_config(self: DbProtocol, updates: dict[str, Any], actor: str = "system", note: str | None = None) -> dict[str, Any]:
        if not updates:
            return self.get_app_config()
        now = datetime.now().isoformat()
        with self._connect() as conn:
            for key, value in updates.items():
                if key not in APP_CONFIG_DEFAULTS:
                    continue
                conn.execute(
                    """
                    INSERT INTO app_config(key, value_json, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json=excluded.value_json,
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                    """,
                    (key, json.dumps(value), now, actor),
                )
                conn.execute(
                    """
                    INSERT INTO admin_audit_log(actor, action, target, payload_json, created_at)
                    VALUES (?, 'config.update', ?, ?, ?)
                    """,
                    (actor, key, json.dumps({"value": value, "note": note}), now),
                )
        return self.get_app_config()

    def get_app_config_value(self: DbProtocol, key: str) -> Any:
        config = self.get_app_config()
        return config.get(key, APP_CONFIG_DEFAULTS.get(key))

    def is_feature_enabled(self: DbProtocol, feature_name: str) -> bool:
        key = f"feature.{feature_name}_enabled"
        value = self.get_app_config_value(key)
        if value is None:
            return True
        return bool(value)

    def is_job_enabled(self: DbProtocol, job_name: str) -> bool:
        key = JOB_CONFIG_KEYS.get(job_name)
        if not key:
            return True
        value = self.get_app_config_value(key)
        if value is None:
            return True
        return bool(value)

    def get_economy_tuning(self: DbProtocol) -> dict[str, int]:
        config = self.get_app_config()

        def _i(key: str, default: int) -> int:
            try:
                return int(config.get(key, default))
            except (TypeError, ValueError):
                return default

        return {
            "fun_rate_study": _i("economy.fun_rate.study", 15),
            "fun_rate_build": _i("economy.fun_rate.build", 20),
            "fun_rate_training": _i("economy.fun_rate.training", 20),
            "fun_rate_job": _i("economy.fun_rate.job", 4),
            "milestone_block_minutes": max(1, _i("economy.milestone_block_minutes", 600)),
            "milestone_bonus_minutes": max(0, _i("economy.milestone_bonus_minutes", 180)),
            "xp_level2_base": max(1, _i("economy.xp_level2_base", 300)),
            "xp_linear": max(0, _i("economy.xp_linear", 80)),
            "xp_quadratic": max(0, _i("economy.xp_quadratic", 4)),
            "level_bonus_scale_percent": max(0, _i("economy.level_bonus_scale_percent", 100)),
        }

    def create_config_snapshot(self: DbProtocol, actor: str = "system", note: str | None = None) -> int:
        now = datetime.now().isoformat()
        payload = json.dumps(self.get_app_config())
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO config_snapshots(config_json, created_at, created_by, note)
                VALUES (?, ?, ?, ?)
                """,
                (payload, now, actor, note),
            )
            conn.execute(
                """
                INSERT INTO admin_audit_log(actor, action, target, payload_json, created_at)
                VALUES (?, 'config.snapshot', 'all', ?, ?)
                """,
                (actor, json.dumps({"snapshot_id": int(cur.lastrowid), "note": note}), now),
            )
        return int(cur.lastrowid)

    def list_config_snapshots(self: DbProtocol, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, created_by, note
                FROM config_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def restore_config_snapshot(self: DbProtocol, snapshot_id: int, actor: str = "system") -> bool:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, config_json FROM config_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
            if row is None:
                return False
            try:
                payload = json.loads(str(row["config_json"]))
            except json.JSONDecodeError:
                return False
            if not isinstance(payload, dict):
                return False
            for key, value in payload.items():
                if key not in APP_CONFIG_DEFAULTS:
                    continue
                conn.execute(
                    """
                    INSERT INTO app_config(key, value_json, updated_at, updated_by)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json=excluded.value_json,
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                    """,
                    (key, json.dumps(value), now, actor),
                )
            conn.execute(
                """
                INSERT INTO admin_audit_log(actor, action, target, payload_json, created_at)
                VALUES (?, 'config.restore', 'all', ?, ?)
                """,
                (actor, json.dumps({"snapshot_id": snapshot_id}), now),
            )
        return True

    def list_admin_audit(self: DbProtocol, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, actor, action, target, payload_json, created_at
                FROM admin_audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_admin_audit(
        self: DbProtocol,
        *,
        actor: str,
        action: str,
        target: str,
        payload: dict[str, Any] | None,
        created_at: datetime,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_audit_log(actor, action, target, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    actor,
                    action,
                    target,
                    json.dumps(payload) if payload is not None else None,
                    created_at.isoformat(),
                ),
            )

    def get_tool_cache(self: DbProtocol, tool_name: str, cache_key: str, now: datetime) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT response_json, expires_at
                FROM tool_cache
                WHERE tool_name = ? AND cache_key = ?
                """,
                (tool_name, cache_key),
            ).fetchone()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(str(row["expires_at"]))
        if expires_at <= now:
            return None
        try:
            payload = json.loads(str(row["response_json"]))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def set_tool_cache(self: DbProtocol, tool_name: str, cache_key: str, payload: dict[str, Any], fetched_at: datetime, ttl_seconds: int) -> None:
        expires_at = fetched_at + timedelta(seconds=max(1, ttl_seconds))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_cache(tool_name, cache_key, response_json, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tool_name, cache_key) DO UPDATE SET
                    response_json=excluded.response_json,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at
                """,
                (
                    tool_name,
                    cache_key,
                    json.dumps(payload),
                    fetched_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )

    def record_search_provider_event(
        self: DbProtocol,
        *,
        provider: str,
        now: datetime,
        success: bool,
        cached: bool,
        rate_limited: bool,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        p = provider.strip().lower()
        if not p:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO search_provider_stats(
                    provider, request_count, success_count, fail_count, cache_hit_count,
                    rate_limit_count, last_status_code, last_error, last_request_at, updated_at
                )
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    request_count = request_count + 1,
                    success_count = success_count + excluded.success_count,
                    fail_count = fail_count + excluded.fail_count,
                    cache_hit_count = cache_hit_count + excluded.cache_hit_count,
                    rate_limit_count = rate_limit_count + excluded.rate_limit_count,
                    last_status_code = excluded.last_status_code,
                    last_error = excluded.last_error,
                    last_request_at = excluded.last_request_at,
                    updated_at = excluded.updated_at
                """,
                (
                    p,
                    1 if success else 0,
                    0 if success else 1,
                    1 if cached else 0,
                    1 if rate_limited else 0,
                    status_code,
                    error,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

    def list_search_provider_stats(self: DbProtocol) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT provider, request_count, success_count, fail_count, cache_hit_count,
                       rate_limit_count, last_status_code, last_error, last_request_at, updated_at
                FROM search_provider_stats
                ORDER BY provider ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def was_event_sent(self: DbProtocol, user_id: int, event_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reminder_events WHERE user_id = ? AND event_key = ?",
                (user_id, event_key),
            ).fetchone()
        return row is not None

    def mark_event_sent(self: DbProtocol, user_id: int, event_key: str, sent_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO reminder_events(user_id, event_key, sent_at)
                VALUES (?, ?, ?)
                """,
                (user_id, event_key, sent_at.isoformat()),
            )
