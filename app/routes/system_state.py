from fastapi import APIRouter, Depends, HTTPException
from psycopg import connect
from psycopg.rows import dict_row
import subprocess

from app.core.auth import require_auth
from app.core.settings import settings

router = APIRouter()

DATABASE_URL = settings.DATABASE_URL


def timer_state(unit: str) -> str:
    r = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return "inactive"
    return (r.stdout or "").strip() or "unknown"


@router.get("/system/state")
def system_state(ctx=Depends(require_auth)):
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key, value
                    FROM runtime_flags
                    WHERE key IN ('safe_mode', 'storm_risk')
                    """
                )
                flag_rows = cur.fetchall()

                flags = {str(r["key"]): str(r["value"]).lower() for r in flag_rows}

                cur.execute(
                    "SELECT COUNT(*) AS n FROM improvement_registry WHERE status='new';"
                )
                new_count = int(cur.fetchone()["n"])

                cur.execute(
                    "SELECT COUNT(*) AS n FROM improvement_registry WHERE status='waiting_approval';"
                )
                waiting_approval_count = int(cur.fetchone()["n"])

                cur.execute(
                    "SELECT COUNT(*) AS n FROM improvement_registry WHERE status='accepted';"
                )
                accepted_count = int(cur.fetchone()["n"])

                cur.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM approvals
                    WHERE status='PENDING'
                      AND expires_at > NOW();
                    """
                )
                pending_approvals = int(cur.fetchone()["n"])

                cur.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM service_action_log
                    WHERE action_type='restart'
                      AND created_at > now() - interval '24 hours';
                    """
                )
                repairs_last_24h = int(cur.fetchone()["n"])

        return {
            "runtime": {
                "safe_mode": flags.get("safe_mode", "false") == "true",
                "storm_risk": flags.get("storm_risk", "false") == "true",
            },
            "improvements": {
                "new": new_count,
                "waiting_approval": waiting_approval_count,
                "accepted": accepted_count,
            },
            "approvals": {
                "pending": pending_approvals,
            },
            "repairs": {
                "last_24h": repairs_last_24h,
            },
            "timers": {
                "intent_scheduler": timer_state("observer-intent-scheduler.timer"),
                "improvement_dispatcher": timer_state("observer-improvement-dispatcher.timer"),
                "improvement_analyzer": timer_state("observer-improvement-analyzer.timer"),
                "repair_executor": timer_state("observer-repair-executor.timer"),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"system_state_failed: {type(e).__name__}: {e}"
        )
