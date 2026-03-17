from typing import List, Dict, Any, Optional
import hashlib
import json
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings

DATABASE_URL = settings.DATABASE_URL

def _compute_plan_hash(policy_version: str, ops: List[Dict[str, Any]]) -> str:
    # Canonical: only stable fields, sorted
    items = [{"op_id": o["op_id"], "op_hash": o["op_hash"]} for o in ops]
    items.sort(key=lambda x: x["op_id"])
    payload = {"policy_version": policy_version or "", "ops": items}
    s = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(s).hexdigest()


def create_task(org_id: str, task_id: str, created_by: str, policy_version: str = "") -> None:
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brain_tasks (org_id, task_id, created_by, status, policy_version)
                VALUES (%s, %s, %s, 'PLANNED', %s)
                ON CONFLICT (org_id, task_id) DO NOTHING
                """,
                (org_id, task_id, created_by, policy_version),
            )
        conn.commit()


def insert_ops(org_id: str, task_id: str, policy_version: str, ops: List[Dict[str, Any]]) -> str:
    """
    ops: list of dicts with keys:
      op_id, op_type, op_hash, risk_level, requires_approval
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for o in ops:
                cur.execute(
                    """
                    INSERT INTO brain_ops (
                        org_id, task_id, op_id, op_type, op_hash, risk_level, requires_approval, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'PLANNED')
                    ON CONFLICT (org_id, task_id, op_id) DO NOTHING
                    """,
                    (
                        org_id,
                        task_id,
                        o["op_id"],
                        o["op_type"],
                        o["op_hash"],
                        o["risk_level"],
                        bool(o["requires_approval"]),
                    ),
                )
            plan_hash = _compute_plan_hash(policy_version, ops)
            cur.execute(
                """
                UPDATE brain_tasks
                SET plan_hash=%s
                WHERE org_id=%s AND task_id=%s
                """,
                (plan_hash, org_id, task_id),
            )
        conn.commit()
    return plan_hash


def mark_op_status(org_id: str, task_id: str, op_id: str, status: str) -> None:
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE brain_ops
                SET status=%s
                WHERE org_id=%s AND task_id=%s AND op_id=%s
                """,
                (status, org_id, task_id, op_id),
            )
        conn.commit()


def recompute_task_status(org_id: str, task_id: str) -> None:
    """
    Simple V0 state machine:
      - FAILED: any op FAILED
      - DONE: all ops EXECUTED or SKIPPED
      - PARTIAL: any op APPROVED/EXECUTED and some still PLANNED
      - EXPIRED: any op EXPIRED and none APPROVED/EXECUTED
      - PLANNED: otherwise
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status
                FROM brain_ops
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )
            rows = cur.fetchall()
            statuses = [r["status"] for r in rows] if rows else []

            if not statuses:
                task_status = "PLANNED"
            elif "FAILED" in statuses:
                task_status = "FAILED"
            elif all(s in ("EXECUTED", "SKIPPED") for s in statuses):
                task_status = "DONE"
            elif any(s in ("APPROVED", "EXECUTED") for s in statuses) and any(s == "PLANNED" for s in statuses):
                task_status = "PARTIAL"
            elif any(s == "EXPIRED" for s in statuses) and not any(s in ("APPROVED", "EXECUTED") for s in statuses):
                task_status = "EXPIRED"
            else:
                task_status = "PLANNED"

            cur.execute(
                """
                UPDATE brain_tasks
                SET status=%s
                WHERE org_id=%s AND task_id=%s
                """,
                (task_status, org_id, task_id),
            )
        conn.commit()


def get_task_with_ops(org_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT org_id, task_id, created_by, status, created_at, policy_version, plan_hash
                FROM brain_tasks
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )
            task = cur.fetchone()
            if not task:
                return None

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
            ops = cur.fetchall()

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
            approvals = cur.fetchall()

            return {"task": task, "ops": ops, "approvals": approvals}
