"""
OBSERVER Public API v1
Endpoints para clientes externos.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg import connect
from psycopg.rows import dict_row

from app.core.auth import require_auth
from app.db.conn import get_conn
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/v1/public")

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


# ─── Models ───────────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    label: str = "default"


class IntentRequest(BaseModel):
    intent: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── GET /v1/public/health ────────────────────────────────────────────────────

@router.get("/health")
def public_health():
    """Estado público del sistema. No requiere auth."""
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM brain_tasks WHERE status='DONE' AND created_at > now() - interval '1 hour'")
                done_1h = cur.fetchone()["n"]
                cur.execute("SELECT count(*) AS n FROM incident_registry WHERE status IN ('OPEN','MONITORING')")
                open_incidents = cur.fetchone()["n"]
                cur.execute("SELECT value FROM runtime_flags WHERE key='safe_mode'")
                row = cur.fetchone()
                safe_mode = row["value"] == "true" if row else False
        return {
            "ok": True,
            "status": "degraded" if open_incidents > 0 else "healthy",
            "safe_mode": safe_mode,
            "open_incidents": open_incidents,
            "tasks_done_1h": done_1h,
            "ts": _now_iso(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "ts": _now_iso()}


# ─── GET /v1/public/incidents ─────────────────────────────────────────────────

@router.get("/incidents")
def list_incidents(
    status: Optional[str] = None,
    limit: int = 20,
    org_id: str = Depends(require_auth),
):
    """Lista incidentes. status: OPEN|MONITORING|RESOLVED (default: activos)"""
    if limit > 100:
        limit = 100

    statuses = [status] if status else ["OPEN", "MONITORING"]
    placeholders = ",".join(["%s"] * len(statuses))

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    incident_id, incident_key, incident_class,
                    title, severity, status,
                    entity_type, entity_name,
                    occurrence_count, first_seen_at, last_seen_at,
                    resolved_at, resolution_notes
                FROM incident_registry
                WHERE status IN ({placeholders})
                ORDER BY
                    CASE severity WHEN 'HIGH' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END,
                    last_seen_at DESC
                LIMIT %s
            """, statuses + [limit])
            rows = cur.fetchall()

    return {
        "incidents": [dict(r) for r in rows],
        "count": len(rows),
        "ts": _now_iso(),
    }


# ─── GET /v1/public/metrics ───────────────────────────────────────────────────

@router.get("/metrics")
def get_metrics(org_id: str = Depends(require_auth)):
    """KPIs del sistema: tasa de éxito, MTTR, incidentes por severidad."""
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            # Tareas 24h
            cur.execute("""
                SELECT
                    count(*) FILTER (WHERE status='DONE') AS done,
                    count(*) FILTER (WHERE status='FAILED') AS failed,
                    count(*) AS total
                FROM brain_tasks
                WHERE created_at > now() - interval '24 hours'
            """)
            tasks_24h = dict(cur.fetchone())

            # MTTR
            cur.execute("""
                SELECT round(avg(extract(epoch FROM (resolved_at - first_seen_at)) / 60), 1) AS mttr_minutes
                FROM incident_registry
                WHERE status = 'RESOLVED' AND resolved_at IS NOT NULL
            """)
            row = cur.fetchone()
            mttr = float(row["mttr_minutes"]) if row and row["mttr_minutes"] else None

            # Incidentes por severidad (últimos 30 días)
            cur.execute("""
                SELECT severity, count(*) AS n
                FROM incident_registry
                WHERE created_at > now() - interval '30 days'
                GROUP BY severity
            """)
            by_severity = {r["severity"]: r["n"] for r in cur.fetchall()}

            # Tasa últimos 7 días
            cur.execute("""
                SELECT
                    date_trunc('day', created_at)::date AS day,
                    round(count(*) FILTER (WHERE status='DONE') * 100.0 / nullif(count(*),0), 1) AS success_pct
                FROM brain_tasks
                WHERE created_at > now() - interval '7 days'
                GROUP BY 1
                ORDER BY 1 DESC
            """)
            daily = [dict(r) for r in cur.fetchall()]

    total = tasks_24h["total"] or 1
    return {
        "tasks_24h": {
            "done": tasks_24h["done"],
            "failed": tasks_24h["failed"],
            "total": tasks_24h["total"],
            "success_pct": round(tasks_24h["done"] * 100 / total, 1),
        },
        "mttr_minutes": mttr,
        "incidents_30d_by_severity": by_severity,
        "daily_success_7d": daily,
        "ts": _now_iso(),
    }


# ─── GET /v1/public/services ──────────────────────────────────────────────────

@router.get("/services")
def list_services(org_id: str = Depends(require_auth)):
    """Estado de todos los servicios monitorizados."""
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    m.service_name,
                    m.status AS monitor_status,
                    (SELECT result_status FROM service_monitor_log l
                     WHERE l.service_name = m.service_name
                     ORDER BY l.created_at DESC LIMIT 1) AS last_result,
                    (SELECT created_at FROM service_monitor_log l
                     WHERE l.service_name = m.service_name
                     ORDER BY l.created_at DESC LIMIT 1) AS last_observed,
                    (SELECT count(*) FROM incident_registry i
                     WHERE i.entity_name = m.service_name
                       AND i.status IN ('OPEN','MONITORING')) AS open_incidents
                FROM service_monitors m
                ORDER BY m.service_name
            """)
            services = [dict(r) for r in cur.fetchall()]

    return {
        "services": services,
        "count": len(services),
        "ts": _now_iso(),
    }


# ─── POST /v1/public/intent ───────────────────────────────────────────────────

@router.post("/intent")
def send_intent(req: IntentRequest, org_id: str = Depends(require_auth)):
    """Lanza un intent al brain. El intent debe estar en el catalog."""
    from app.routes.brain_intent import handle_brain_intent, BrainIntent
    from app.core.auth import require_auth as _auth

    brain_req = BrainIntent(intent=req.intent)

    class FakeCtx:
        def __str__(self):
            return org_id

    try:
        result = handle_brain_intent(brain_req, ctx=org_id)
        return {
            "ok": result.get("status") in ("executed", "idempotent"),
            "result": result,
            "ts": _now_iso(),
        }
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── POST /v1/public/orgs ─────────────────────────────────────────────────────

@router.post("/orgs")
def create_org(req: OrgCreate):
    """
    Crea una nueva organización y genera una API key.
    Devuelve la API key en texto plano — solo se muestra una vez.
    No requiere auth (endpoint de onboarding).
    """
    org_id = f"org_{secrets.token_hex(6)}"
    raw_key = f"obs_{secrets.token_urlsafe(32)}"
    key_hash = _sha256(raw_key)

    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Crear org
            cur.execute(
                "INSERT INTO orgs (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (org_id, req.name)
            )
            # Crear API key
            cur.execute(
                "INSERT INTO api_keys (key_hash, org_id, label, is_active) VALUES (%s, %s, %s, true)",
                (key_hash, org_id, req.label)
            )
        conn.commit()

    return {
        "org_id": org_id,
        "api_key": raw_key,
        "label": req.label,
        "warning": "Guarda esta API key — no se mostrará de nuevo.",
        "ts": _now_iso(),
    }


# ─── GET /v1/public/action-memory ────────────────────────────────────────────

@router.get("/action-memory")
def get_action_memory(org_id: str = Depends(require_auth)):
    """Action Memory: métricas vivas por acción desde brain_exec_log."""
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    action_name, risk_class, requires_approval,
                    total_executions, total_success, total_failed,
                    success_rate_pct, avg_duration_ms,
                    executions_24h, executions_7d,
                    last_executed_at, health_score
                FROM v_action_memory_full
                ORDER BY total_executions DESC
            """)
            rows = cur.fetchall()
    return {
        "action_memory": [dict(r) for r in rows],
        "count": len(rows),
        "ts": _now_iso(),
    }


@router.get("/reputation")
def get_reputation(org_id: str = Depends(require_auth)):
    """Reputation Layer: score operativo por actor basado en historial real."""
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT actor_id, total_tasks, tasks_done, tasks_failed,
                       tasks_failed_real, tasks_rejected_by_human,
                       success_rate_pct, tasks_24h, tasks_7d,
                       last_active_at, reputation_score, reputation_tier
                FROM v_agent_reputation
                ORDER BY reputation_score DESC
            """)
            rows = cur.fetchall()
    return {
        "reputation": [dict(r) for r in rows],
        "count": len(rows),
        "ts": _now_iso(),
    }


@router.get("/simulate")
def simulate_intent(intent: str, actor_id: str = "unknown", org_id: str = Depends(require_auth)):
    """Pre-Execution Simulation: muestra que pasaria sin ejecutar nada."""
    import json as _json
    policy_path = "/etc/observer/policy.json"
    try:
        policy = _json.load(open(policy_path))
        rules = {r["action_type"]: r for r in policy.get("policy_json", {}).get("rules", [])}
        default_decision = policy.get("policy_json", {}).get("defaults", {}).get("decision_on_no_match", "APPROVED")
        policy_version = policy.get("policy_version", "unknown")
    except Exception:
        rules = {}
        default_decision = "APPROVED"
        policy_version = "unknown"

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.action_name, m.target, m.execution_order,
                       ar.risk_class, ar.requires_approval
                FROM intent_action_map m
                JOIN action_registry ar ON ar.action_name = m.action_name
                WHERE m.intent_name = %s AND m.status = 'ACTIVE'
                ORDER BY m.execution_order
            """, (intent,))
            actions = cur.fetchall()

            simulated = []
            for a in actions:
                action_name = a["action_name"]
                rule = rules.get(action_name)
                if rule:
                    policy_decision = rule["decision"]
                    policy_rule_id = rule["id"]
                else:
                    policy_decision = "REQUIRES_APPROVAL" if a["requires_approval"] else default_decision
                    policy_rule_id = "default"

                cur.execute("""
                    SELECT total_executions, success_rate_pct,
                           executions_24h, health_score
                    FROM v_action_memory_full
                    WHERE action_name = %s
                """, (action_name,))
                mem = cur.fetchone()

                simulated.append({
                    "order": a["execution_order"],
                    "action": action_name,
                    "target": a["target"],
                    "risk_class": a["risk_class"],
                    "policy_decision": policy_decision,
                    "policy_rule": policy_rule_id,
                    "requires_approval": a["requires_approval"],
                    "history": {
                        "total_executions": mem["total_executions"] if mem else 0,
                        "success_rate_pct": float(mem["success_rate_pct"]) if mem else 0,
                        "executions_24h": mem["executions_24h"] if mem else 0,
                        "health_score": int(mem["health_score"]) if mem else 0,
                    },
                })

            cur.execute("""
                SELECT reputation_score, reputation_tier, tasks_failed_real
                FROM v_agent_reputation
                WHERE actor_id = %s
            """, (actor_id,))
            actor = cur.fetchone()

    return {
        "simulation": {
            "intent": intent,
            "actor_id": actor_id,
            "actor_reputation": dict(actor) if actor else {
                "reputation_score": 0,
                "reputation_tier": "unknown",
                "tasks_failed_real": 0
            },
            "policy_version": policy_version,
            "actions": simulated,
            "would_require_approval": any(a["requires_approval"] for a in simulated),
            "would_be_blocked": any(a["policy_decision"] == "REJECTED" for a in simulated),
        },
        "ts": _now_iso(),
    }
