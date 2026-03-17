from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.db import connect, DATABASE_URL, dict_row


def insert_pending_approval(
    org_id: str,
    task_id: str,
    op_id: str,
    op_hash: str,
    user_id: str,
    risk_level: str,
    expires_at,
) -> None:
    """
    Create a PENDING approval row. expires_at should be a timestamptz-compatible value.
    """
    with connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO approvals
                    (org_id, task_id, op_id, op_hash, user_id, risk_level, status, expires_at, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, 'PENDING', %s, NOW())
                """,
                (org_id, task_id, op_id, op_hash, user_id, risk_level, expires_at),
            )
        conn.commit()


def get_approval(org_id: str, task_id: str, op_id: str) -> Optional[Dict[str, Any]]:
    """
    Return approval row for (org_id, task_id, op_id), or None.
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM approvals
                WHERE org_id=%s AND task_id=%s AND op_id=%s
                """,
                (org_id, task_id, op_id),
            )
            return cur.fetchone()


def get_pending_approval(org_id: str, task_id: str, op_id: str) -> Optional[Dict[str, Any]]:
    """
    Back-compat helper (some older code may call this).
    """
    row = get_approval(org_id, task_id, op_id)
    if not row:
        return None
    if row.get("status") == "PENDING":
        return row
    return None


def approve_pending_approval(
    org_id: str,
    task_id: str,
    op_id: str,
    op_hash: str,
    approved_by: str,
) -> Dict[str, Any]:
    """
    Transition approval PENDING -> APPROVED atomically, only if not expired.
    All expiry logic is handled by Postgres (expires_at > NOW()).
    """

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status='APPROVED',
                    approved_by=%s,
                    approved_at=NOW()
                WHERE org_id=%s
                  AND task_id=%s
                  AND op_id=%s
                  AND op_hash=%s
                  AND status='PENDING'
                  AND expires_at > NOW()
                """,
                (approved_by, org_id, task_id, op_id, op_hash),
            )

            if cur.rowcount == 0:
                cur.execute(
                    """
                    SELECT status, expires_at
                    FROM approvals
                    WHERE org_id=%s
                      AND task_id=%s
                      AND op_id=%s
                      AND op_hash=%s
                    """,
                    (org_id, task_id, op_id, op_hash),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("approval not found")

                status = row.get("status")
                if status != "PENDING":
                    return {"ok": True, "status": status, "note": "already not pending"}

                raise ValueError("approval expired")

        conn.commit()

    return {
        "ok": True,
        "org_id": org_id,
        "task_id": task_id,
        "op_id": op_id,
        "op_hash": op_hash,
        "status": "APPROVED",
        "approved_by": approved_by,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }


def reject_pending_approval(
    org_id: str,
    task_id: str,
    op_id: str,
    op_hash: str,
    rejected_by: str,
) -> Dict[str, Any]:
    """
    Transition approval PENDING -> REJECTED atomically, only if not expired.
    All expiry logic is handled by Postgres (expires_at > NOW()).
    """

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status='REJECTED',
                    rejected_by=%s,
                    rejected_at=NOW()
                WHERE org_id=%s
                  AND task_id=%s
                  AND op_id=%s
                  AND op_hash=%s
                  AND status='PENDING'
                  AND expires_at > NOW()
                """,
                (rejected_by, org_id, task_id, op_id, op_hash),
            )

            if cur.rowcount == 0:
                cur.execute(
                    """
                    SELECT status, expires_at
                    FROM approvals
                    WHERE org_id=%s
                      AND task_id=%s
                      AND op_id=%s
                      AND op_hash=%s
                    """,
                    (org_id, task_id, op_id, op_hash),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("approval not found")

                status = row.get("status")
                if status != "PENDING":
                    return {"ok": True, "status": status, "note": "already not pending"}

                raise ValueError("approval expired")

        conn.commit()

    return {
        "ok": True,
        "org_id": org_id,
        "task_id": task_id,
        "op_id": op_id,
        "op_hash": op_hash,
        "status": "REJECTED",
        "rejected_by": rejected_by,
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    }


def consume_approval(org_id: str, task_id: str, op_id: str, op_hash: str, consumed_by: str) -> Dict[str, Any]:
    """
    Consume an APPROVED approval (APPROVED -> CONSUMED) atomically.
    This enforces consume-before semantics (execute must consume before action).
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status='CONSUMED',
                    consumed_by=%s,
                    consumed_at=NOW()
                WHERE org_id=%s
                  AND task_id=%s
                  AND op_id=%s
                  AND op_hash=%s
                  AND status='APPROVED'
                  AND expires_at > NOW()
                """,
                (consumed_by, org_id, task_id, op_id, op_hash),
            )

            if cur.rowcount == 0:
                cur.execute(
                    """
                    SELECT status, expires_at
                    FROM approvals
                    WHERE org_id=%s
                      AND task_id=%s
                      AND op_id=%s
                      AND op_hash=%s
                    """,
                    (org_id, task_id, op_id, op_hash),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("approval not found")

                status = row.get("status")
                if status == "CONSUMED":
                    return {"ok": True, "status": "CONSUMED", "note": "already consumed"}
                if status != "APPROVED":
                    raise ValueError(f"approval not approved (status={status})")

                raise ValueError("approval expired")

        conn.commit()

    return {
        "ok": True,
        "org_id": org_id,
        "task_id": task_id,
        "op_id": op_id,
        "op_hash": op_hash,
        "status": "CONSUMED",
        "consumed_by": consumed_by,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
    }
