from __future__ import annotations

from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from tg_time_logger.config import load_settings
from tg_time_logger.db import Database
from tg_time_logger.db_constants import APP_CONFIG_DEFAULTS
from tg_time_logger.gamification import build_economy
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


class FunAdjustmentRequest(BaseModel):
    minutes: int
    note: str = ""


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
    table th, table td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #e2e8f0; }
    table th { font-weight: 600; color: #374151; }
    h3 { margin: 0 0 8px; font-size: 15px; }
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
    <h2>User Data</h2>
    <div class="row" style="margin-bottom:12px">
      <input type="number" id="userId" placeholder="User ID" />
      <button id="loadUserBtn" class="secondary">Load User</button>
    </div>
    <div id="userData" style="display:none">
      <h3>Economy</h3>
      <div id="economyInfo" class="grid"></div>

      <h3 style="margin-top:12px">Fun Adjustment</h3>
      <div class="row" style="margin-bottom:12px">
        <input type="number" id="adjMinutes" placeholder="Minutes (+/-)" />
        <input type="text" id="adjNote" placeholder="Note" />
        <button id="adjBtn" class="secondary">Adjust</button>
      </div>

      <h3 style="margin-top:12px">Streak</h3>
      <div class="row" style="margin-bottom:12px">
        <span id="streakInfo" style="align-self:center"></span>
        <button id="resetStreakBtn" class="secondary">Reset Streak</button>
      </div>

      <h3 style="margin-top:12px">Level-Up Events</h3>
      <table id="levelUps" style="width:100%;font-size:13px;border-collapse:collapse">
        <thead><tr><th>ID</th><th>Level</th><th>Bonus Fun</th><th>Date</th><th></th></tr></thead>
        <tbody></tbody>
      </table>

      <h3 style="margin-top:12px">Recent Entries</h3>
      <label><input type="checkbox" id="showDeleted" /> Show deleted</label>
      <table id="entries" style="width:100%;font-size:13px;border-collapse:collapse;margin-top:6px">
        <thead><tr><th>ID</th><th>Kind</th><th>Cat</th><th>Min</th><th>XP</th><th>Fun</th><th>Note</th><th>Date</th><th></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>Audit Log (latest 50)</h2>
    <pre id="audit"></pre>
  </div>

  <script>
    const featureKeys = [
      "feature.reminders_enabled", "feature.economy_enabled"
    ];
    const jobKeys = [
      "job.sunday_summary_enabled", "job.reminders_enabled"
    ];
    const economyKeys = [
      "economy.fun_rate.study", "economy.fun_rate.build", "economy.fun_rate.training", "economy.fun_rate.job",
      "economy.milestone_block_minutes", "economy.milestone_bonus_minutes",
      "economy.xp_level2_base", "economy.xp_linear", "economy.xp_quadratic", "economy.level_bonus_scale_percent"
    ];

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

    async function loadAll() {
      const cfgRes = await fetch(withToken("/api/config"));
      const cfg = await cfgRes.json();
      Object.assign(state, cfg.config || {});
      document.getElementById("features").innerHTML = featureKeys.map(k => boolInput(k, !!state[k])).join("");
      document.getElementById("jobs").innerHTML = jobKeys.map(k => boolInput(k, !!state[k])).join("");
      document.getElementById("economy").innerHTML = economyKeys.map(k => numberInput(k, state[k] ?? 0)).join("");

      const snapRes = await fetch(withToken("/api/snapshots?limit=20"));
      const snaps = await snapRes.json();
      const select = document.getElementById("snapshotSelect");
      select.innerHTML = (snaps.snapshots || []).map(s => `<option value="${s.id}">#${s.id} | ${s.created_at} | ${s.created_by || "unknown"} | ${s.note || ""}</option>`).join("");

      const auditRes = await fetch(withToken("/api/audit?limit=50"));
      const audit = await auditRes.json();
      document.getElementById("audit").textContent = JSON.stringify(audit.rows || [], null, 2);
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

    // --- User Data ---
    let currentUserId = null;

    async function loadUserData() {
      const uid = document.getElementById("userId").value;
      if (!uid) return;
      currentUserId = uid;
      document.getElementById("userData").style.display = "block";

      // Economy
      const ecoRes = await fetch(withToken(`/api/user/${uid}/economy`));
      const eco = await ecoRes.json();
      document.getElementById("economyInfo").innerHTML = [
        `<div><b>Fun Balance:</b> ${eco.fun_balance}m</div>`,
        `<div><b>Base Fun Earned:</b> ${eco.base_fun_earned}m</div>`,
        `<div><b>Adjustments:</b> ${eco.fun_adjustments}m</div>`,
        `<div><b>Level Bonus:</b> ${eco.level_bonus}m</div>`,
        `<div><b>Milestone Bonus:</b> ${eco.milestone_bonus}m</div>`,
        `<div><b>Total Spent:</b> ${eco.total_spent}m</div>`,
        `<div><b>Total Productive:</b> ${eco.total_productive}m</div>`,
      ].join("");

      // Streak
      const stRes = await fetch(withToken(`/api/user/${uid}/streak`));
      const st = await stRes.json();
      document.getElementById("streakInfo").textContent =
        `Current: ${st.current_streak}d | Longest: ${st.longest_streak}d | Last: ${st.last_productive_date || "never"}`;

      // Level-ups
      const luRes = await fetch(withToken(`/api/user/${uid}/level-ups`));
      const lu = await luRes.json();
      document.querySelector("#levelUps tbody").innerHTML = (lu.level_ups || []).map(e =>
        `<tr><td>${e.id}</td><td>${e.level}</td><td>+${e.bonus_fun_minutes}m</td><td>${e.created_at.slice(0,16)}</td><td><button onclick="deleteLevelUp(${e.id})" style="width:auto;padding:2px 8px;background:#dc2626">Del</button></td></tr>`
      ).join("");

      await loadEntries();
    }

    async function loadEntries() {
      const uid = currentUserId;
      if (!uid) return;
      const del = document.getElementById("showDeleted").checked;
      const res = await fetch(withToken(`/api/user/${uid}/entries?limit=50&include_deleted=${del}`));
      const data = await res.json();
      document.querySelector("#entries tbody").innerHTML = (data.entries || []).map(e => {
        const cls = e.deleted_at ? 'style="opacity:0.4"' : '';
        const btn = e.deleted_at ? '' : `<button onclick="deleteEntry(${e.id})" style="width:auto;padding:2px 8px;background:#dc2626">Del</button>`;
        return `<tr ${cls}><td>${e.id}</td><td>${e.kind}</td><td>${e.category}</td><td>${e.minutes}</td><td>${e.xp_earned}</td><td>${e.fun_earned}</td><td>${e.note||""}</td><td>${e.created_at.slice(0,16)}</td><td>${btn}</td></tr>`;
      }).join("");
    }

    async function deleteEntry(id) {
      if (!confirm(`Delete entry #${id}?`)) return;
      await fetch(withToken(`/api/entries/${id}`), {method:"DELETE"});
      await loadUserData();
    }

    async function deleteLevelUp(id) {
      if (!confirm(`Delete level-up event #${id}?`)) return;
      await fetch(withToken(`/api/level-ups/${id}`), {method:"DELETE"});
      await loadUserData();
    }

    document.getElementById("loadUserBtn").addEventListener("click", loadUserData);
    document.getElementById("showDeleted").addEventListener("change", loadEntries);

    document.getElementById("adjBtn").addEventListener("click", async () => {
      const minutes = parseInt(document.getElementById("adjMinutes").value);
      if (isNaN(minutes) || !currentUserId) return;
      const note = document.getElementById("adjNote").value || "admin adjustment";
      await fetch(withToken(`/api/user/${currentUserId}/fun-adjustment`), {
        method:"POST", headers:{"content-type":"application/json"},
        body: JSON.stringify({minutes, note})
      });
      document.getElementById("adjMinutes").value = "";
      document.getElementById("adjNote").value = "";
      await loadUserData();
    });

    document.getElementById("resetStreakBtn").addEventListener("click", async () => {
      if (!currentUserId || !confirm("Reset streak to 0?")) return;
      await fetch(withToken(`/api/user/${currentUserId}/streak/reset`), {method:"POST", headers:{"content-type":"application/json"}, body:"{}"});
      await loadUserData();
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

    # --- User Data Endpoints ---

    @app.get("/api/user/{user_id}/entries")
    async def api_user_entries(user_id: int, request: Request, limit: int = 50, include_deleted: bool = False) -> dict[str, Any]:
        _require_auth(request, admin_token)
        entries = db.list_entries(user_id, limit=limit, include_deleted=include_deleted)
        return {"entries": [_entry_to_dict(e) for e in entries]}

    @app.delete("/api/entries/{entry_id}")
    async def api_delete_entry(entry_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        now = datetime.utcnow()
        entry = db.soft_delete_entry(entry_id, deleted_at=now)
        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found or already deleted")
        db.add_admin_audit(actor="admin", action="delete_entry", target=str(entry_id), payload=None, created_at=now)
        return {"ok": True, "entry": _entry_to_dict(entry)}

    @app.get("/api/user/{user_id}/economy")
    async def api_user_economy(user_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        tuning = db.get_economy_tuning()
        base_fun = db.sum_fun_earned_entries(user_id)
        adjustments = db.sum_fun_adjustments(user_id)
        level_bonus = db.sum_level_bonus(user_id)
        all_productive = db.sum_minutes(user_id, "productive")
        all_spent = db.sum_minutes(user_id, "spend")
        all_categories = db.sum_productive_by_category(user_id)
        milestone_productive = all_productive - all_categories.get("job", 0)
        economy = build_economy(
            base_fun_minutes=base_fun + adjustments,
            productive_minutes=milestone_productive,
            level_bonus_minutes=level_bonus,
            spent_fun_minutes=all_spent,
            tuning=tuning,
        )
        return {
            "base_fun_earned": base_fun,
            "fun_adjustments": adjustments,
            "level_bonus": level_bonus,
            "milestone_bonus": economy.milestone_bonus_minutes,
            "total_spent": all_spent,
            "fun_balance": economy.remaining_fun_minutes,
            "total_productive": all_productive,
        }

    @app.post("/api/user/{user_id}/fun-adjustment")
    async def api_fun_adjustment(user_id: int, request: Request, payload: FunAdjustmentRequest) -> dict[str, Any]:
        _require_auth(request, admin_token)
        now = datetime.utcnow()
        entry = db.add_fun_adjustment(user_id, minutes=payload.minutes, note=payload.note or "admin adjustment", created_at=now)
        db.add_admin_audit(actor="admin", action="fun_adjustment", target=str(user_id), payload={"minutes": payload.minutes, "note": payload.note}, created_at=now)
        return {"ok": True, "entry": _entry_to_dict(entry)}

    @app.get("/api/user/{user_id}/level-ups")
    async def api_user_level_ups(user_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        events = db.list_level_up_events(user_id)
        return {"level_ups": [{"id": e.id, "level": e.level, "bonus_fun_minutes": e.bonus_fun_minutes, "created_at": e.created_at.isoformat()} for e in events]}

    @app.delete("/api/level-ups/{event_id}")
    async def api_delete_level_up(event_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        ok = db.delete_level_up_event(event_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Level-up event not found")
        db.add_admin_audit(actor="admin", action="delete_level_up", target=str(event_id), payload=None, created_at=datetime.utcnow())
        return {"ok": True}

    @app.get("/api/user/{user_id}/streak")
    async def api_user_streak(user_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        now = datetime.utcnow()
        streak = db.get_streak(user_id, now)
        return {
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "last_productive_date": streak.last_productive_date.isoformat() if streak.last_productive_date else None,
        }

    @app.post("/api/user/{user_id}/streak/reset")
    async def api_reset_streak(user_id: int, request: Request) -> dict[str, Any]:
        _require_auth(request, admin_token)
        now = datetime.utcnow()
        db.reset_streak(user_id, now)
        db.add_admin_audit(actor="admin", action="reset_streak", target=str(user_id), payload=None, created_at=now)
        return {"ok": True}

    return app


def _entry_to_dict(e: Any) -> dict[str, Any]:
    return {
        "id": e.id,
        "user_id": e.user_id,
        "kind": e.kind,
        "category": e.category,
        "minutes": e.minutes,
        "xp_earned": e.xp_earned,
        "fun_earned": e.fun_earned,
        "note": e.note,
        "created_at": e.created_at.isoformat(),
        "deleted_at": e.deleted_at.isoformat() if e.deleted_at else None,
        "source": e.source,
    }


def run_admin() -> None:
    setup_logging()
    settings = load_settings()
    db = Database(settings.database_path)
    app = build_admin_app(db, settings.admin_panel_token)
    uvicorn.run(app, host=settings.admin_host, port=settings.admin_port)
