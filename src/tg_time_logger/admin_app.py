from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from tg_time_logger.config import load_settings
from tg_time_logger.db import Database
from tg_time_logger.db_constants import APP_CONFIG_DEFAULTS
from tg_time_logger.logging_setup import setup_logging


def _coerce_value(key: str, value: Any) -> Any:
    default = APP_CONFIG_DEFAULTS.get(key)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return value


def _require_auth(request: Request, token: str | None) -> None:
    if not token:
        return
    header = request.headers.get("x-admin-token")
    query = request.query_params.get("token")
    if header == token or query == token:
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


class ConfigUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
    actor: str = "admin"
    note: str | None = None


class SnapshotRequest(BaseModel):
    actor: str = "admin"
    note: str | None = None


def build_admin_app(db: Database, admin_token: str | None) -> FastAPI:
    app = FastAPI(title="TG Time Logger Admin", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> str:
        _require_auth(request, admin_token)
        return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Admin Panel</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f5f7fb; }
    h1, h2 { margin: 0 0 12px; }
    .card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
    .grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
    label { display: block; font-size: 14px; margin-bottom: 6px; color: #374151; }
    input, select, button { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
    .row { display: flex; gap: 8px; }
    .row > * { flex: 1; }
    button { background: #111827; color: #fff; cursor: pointer; }
    button.secondary { background: #475569; }
    pre { white-space: pre-wrap; background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; max-height: 260px; overflow: auto; }
    .small { color: #475569; font-size: 13px; }
  </style>
</head>
<body>
  <h1>TG Logger Admin Panel</h1>
  <p class="small">Use this to toggle features, tune economy, control jobs, and manage snapshots.</p>

  <div class="card">
    <h2>Features</h2>
    <div class="grid" id="features"></div>
  </div>

  <div class="card">
    <h2>Jobs</h2>
    <div class="grid" id="jobs"></div>
  </div>

  <div class="card">
    <h2>Economy Tuning</h2>
    <div class="grid" id="economy"></div>
  </div>

  <div class="card">
    <h2>Agent</h2>
    <div class="grid" id="agent"></div>
  </div>

  <div class="card">
    <h2>Search</h2>
    <div class="grid" id="search"></div>
  </div>

  <div class="card">
    <h2>Search Provider Health</h2>
    <pre id="searchStats"></pre>
  </div>

  <div class="card">
    <div class="row">
      <button id="saveBtn">Save Config</button>
      <button id="snapshotBtn" class="secondary">Create Snapshot</button>
    </div>
  </div>

  <div class="card">
    <h2>Snapshots</h2>
    <div class="row">
      <select id="snapshotSelect"></select>
      <button id="restoreBtn" class="secondary">Restore Selected</button>
    </div>
  </div>

  <div class="card">
    <h2>Audit Log (latest 50)</h2>
    <pre id="audit"></pre>
  </div>

  <script>
    const featureKeys = [
      "feature.llm_enabled", "feature.quests_enabled", "feature.reminders_enabled",
      "feature.shop_enabled", "feature.savings_enabled", "feature.economy_enabled",
      "feature.notion_backup_enabled"
    ];
    const jobKeys = [
      "job.sunday_summary_enabled", "job.reminders_enabled",
      "job.midweek_enabled", "job.notion_backup_enabled"
    ];
    const economyKeys = [
      "economy.fun_rate.study", "economy.fun_rate.build", "economy.fun_rate.training", "economy.fun_rate.job",
      "economy.milestone_block_minutes", "economy.milestone_bonus_minutes",
      "economy.xp_level2_base", "economy.xp_linear", "economy.xp_quadratic", "economy.level_bonus_scale_percent",
      "economy.nok_to_fun_minutes"
    ];
    const agentBoolKeys = ["feature.agent_enabled", "agent.reasoning_enabled"];
    const agentIntKeys = [
      "agent.max_steps",
      "agent.max_tool_calls",
      "agent.max_step_input_tokens",
      "agent.max_step_output_tokens",
      "agent.max_total_tokens"
    ];
    const agentStringKeys = ["agent.default_tier", "i18n.default_language"];
    const searchBoolKeys = [
      "feature.search_enabled",
      "search.brave_enabled",
      "search.tavily_enabled",
      "search.serper_enabled"
    ];
    const searchIntKeys = ["search.cache_ttl_seconds"];
    const searchStringKeys = ["search.provider_order"];

    const state = {};
    const token = new URLSearchParams(window.location.search).get("token");
    function withToken(url) {
      if (!token) return url;
      const sep = url.includes("?") ? "&" : "?";
      return `${url}${sep}token=${encodeURIComponent(token)}`;
    }

    function boolInput(key, value) {
      return `<label><input type="checkbox" id="${key}" ${value ? "checked": ""}/> ${key}</label>`;
    }

    function numberInput(key, value) {
      return `<label>${key}<input type="number" id="${key}" value="${value}" /></label>`;
    }

    function textInput(key, value) {
      return `<label>${key}<input type="text" id="${key}" value="${value ?? ""}" /></label>`;
    }

    async function loadAll() {
      const cfgRes = await fetch(withToken("/api/config"));
      const cfg = await cfgRes.json();
      Object.assign(state, cfg.config || {});
      document.getElementById("features").innerHTML = featureKeys.map(k => boolInput(k, !!state[k])).join("");
      document.getElementById("jobs").innerHTML = jobKeys.map(k => boolInput(k, !!state[k])).join("");
      document.getElementById("economy").innerHTML = economyKeys.map(k => numberInput(k, state[k] ?? 0)).join("");
      document.getElementById("agent").innerHTML =
        agentBoolKeys.map(k => boolInput(k, !!state[k])).join("") +
        agentIntKeys.map(k => numberInput(k, state[k] ?? 0)).join("") +
        agentStringKeys.map(k => textInput(k, state[k] ?? "")).join("");
      document.getElementById("search").innerHTML =
        searchBoolKeys.map(k => boolInput(k, !!state[k])).join("") +
        searchIntKeys.map(k => numberInput(k, state[k] ?? 0)).join("") +
        searchStringKeys.map(k => textInput(k, state[k] ?? "")).join("");

      const snapRes = await fetch(withToken("/api/snapshots?limit=20"));
      const snaps = await snapRes.json();
      const select = document.getElementById("snapshotSelect");
      select.innerHTML = (snaps.snapshots || []).map(s => `<option value="${s.id}">#${s.id} | ${s.created_at} | ${s.created_by || "unknown"} | ${s.note || ""}</option>`).join("");

      const auditRes = await fetch(withToken("/api/audit?limit=50"));
      const audit = await auditRes.json();
      document.getElementById("audit").textContent = JSON.stringify(audit.rows || [], null, 2);

      const searchStatsRes = await fetch(withToken("/api/search_stats"));
      const searchStats = await searchStatsRes.json();
      document.getElementById("searchStats").textContent = JSON.stringify(searchStats.rows || [], null, 2);
    }

    function collectUpdates() {
      const updates = {};
      for (const k of featureKeys.concat(jobKeys)) {
        const el = document.getElementById(k);
        updates[k] = !!(el && el.checked);
      }
      for (const k of economyKeys) {
        const el = document.getElementById(k);
        updates[k] = Number(el ? el.value : 0);
      }
      for (const k of agentBoolKeys.concat(searchBoolKeys)) {
        const el = document.getElementById(k);
        updates[k] = !!(el && el.checked);
      }
      for (const k of agentIntKeys.concat(searchIntKeys)) {
        const el = document.getElementById(k);
        updates[k] = Number(el ? el.value : 0);
      }
      for (const k of agentStringKeys.concat(searchStringKeys)) {
        const el = document.getElementById(k);
        updates[k] = el ? el.value : "";
      }
      return updates;
    }

    document.getElementById("saveBtn").addEventListener("click", async () => {
      const res = await fetch(withToken("/api/config"), {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({updates: collectUpdates(), actor: "panel"})
      });
      if (!res.ok) { alert("Save failed"); return; }
      await loadAll();
      alert("Saved");
    });

    document.getElementById("snapshotBtn").addEventListener("click", async () => {
      const note = prompt("Snapshot note (optional):") || "";
      const res = await fetch(withToken("/api/snapshots"), {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({actor: "panel", note})
      });
      if (!res.ok) { alert("Snapshot failed"); return; }
      await loadAll();
      alert("Snapshot created");
    });

    document.getElementById("restoreBtn").addEventListener("click", async () => {
      const select = document.getElementById("snapshotSelect");
      const id = select.value;
      if (!id) return;
      if (!confirm(`Restore snapshot #${id}?`)) return;
      const res = await fetch(withToken(`/api/snapshots/${id}/restore`), {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({actor: "panel"})
      });
      if (!res.ok) { alert("Restore failed"); return; }
      await loadAll();
      alert("Snapshot restored");
    });

    loadAll();
  </script>
</body>
</html>
        """

    @app.get("/api/config")
    async def api_config(request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        return {"config": db.get_app_config(), "defaults": APP_CONFIG_DEFAULTS}

    @app.post("/api/config")
    async def api_update_config(request: Request, payload: ConfigUpdateRequest) -> dict[str, Any]:
        _require_auth(request, admin_token)
        sanitized: dict[str, Any] = {}
        for key, value in payload.updates.items():
            if key not in APP_CONFIG_DEFAULTS:
                continue
            sanitized[key] = _coerce_value(key, value)
        cfg = db.set_app_config(sanitized, actor=payload.actor, note=payload.note)
        return {"ok": True, "updated_count": len(sanitized), "config": cfg}

    @app.get("/api/snapshots")
    async def api_snapshots(request: Request, limit: int = 20) -> dict[str, Any]:
        _require_auth(request, admin_token)
        return {"snapshots": db.list_config_snapshots(limit=limit)}

    @app.post("/api/snapshots")
    async def api_create_snapshot(request: Request, payload: SnapshotRequest) -> dict[str, Any]:
        _require_auth(request, admin_token)
        sid = db.create_config_snapshot(actor=payload.actor, note=payload.note)
        return {"ok": True, "snapshot_id": sid}

    @app.post("/api/snapshots/{snapshot_id}/restore")
    async def api_restore_snapshot(snapshot_id: int, request: Request, payload: SnapshotRequest) -> dict[str, Any]:
        _require_auth(request, admin_token)
        ok = db.restore_config_snapshot(snapshot_id, actor=payload.actor)
        if not ok:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return {"ok": True}

    @app.get("/api/audit")
    async def api_audit(request: Request, limit: int = 100) -> dict[str, Any]:
        _require_auth(request, admin_token)
        return {"rows": db.list_admin_audit(limit=limit)}

    @app.get("/api/search_stats")
    async def api_search_stats(request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        return {"rows": db.list_search_provider_stats()}

    return app


def run_admin() -> None:
    setup_logging()
    settings = load_settings()
    db = Database(settings.database_path)
    app = build_admin_app(db, settings.admin_panel_token)
    uvicorn.run(app, host=settings.admin_host, port=settings.admin_port)
