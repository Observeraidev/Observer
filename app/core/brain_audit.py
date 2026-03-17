from typing import Any, Dict, Optional, List
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings

DATABASE_URL = settings.DATABASE_URL


def get_task_audit(org_id: str, task_id: str, limit: int = 20) -> Optional[Dict[str, Any]]:
    if limit <= 0:
        limit = 20
    if limit > 200:
        limit = 200

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Task
            cur.execute(
                """
                SELECT org_id, task_id, created_by, status, created_at, policy_version
                FROM brain_tasks
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )
            task = cur.fetchone()
            if not task:
                return None

            # Ops
            cur.execute(
                """
                SELECT org_id, task_id, op_id, op_type, op_hash, risk_level,
                       requires_approval, status, created_at
                FROM brain_ops
                WHERE org_id=%s AND task_id=%s
                ORDER BY created_at ASC
                """,
                (org_id, task_id),
            )
            ops: List[Dict[str, Any]] = cur.fetchall()

            # Approvals
            cur.execute(
                """
                SELECT org_id, task_id, op_id, op_hash, risk_level, status,
                       expires_at, approved_by, approved_at, created_at
                FROM approvals
                WHERE org_id=%s AND task_id=%s
                ORDER BY created_at ASC
                """,
                (org_id, task_id),
            )
            approvals: List[Dict[str, Any]] = cur.fetchall()

            # Exec log
            cur.execute(
                """
                SELECT org_id, task_id, exec_id, created_at, started_at, finished_at,
                       policy_version, plan_hash, status, error, result_json, evidence_json
                FROM brain_exec_log
                WHERE org_id=%s AND task_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (org_id, task_id, limit),
            )
            exec_log: List[Dict[str, Any]] = cur.fetchall()

            # Policy JSON for the task's policy_version (best-effort)
            policy_json = None
            pv = task.get("policy_version") or ""
            if pv:
                cur.execute(
                    """
                    SELECT policy_json
                    FROM policy_versions
                    WHERE policy_version=%s
                    """,
                    (pv,),
                )
                row = cur.fetchone()
                if row:
                    policy_json = row.get("policy_json")

            return {
                "task": task,
                "ops": ops,
                "approvals": approvals,
                "exec_log": exec_log,
                "policy": {
                    "policy_version": pv,
                    "policy_json": policy_json,
                },
            }
