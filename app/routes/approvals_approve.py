from fastapi import APIRouter, Depends, HTTPException
from psycopg import connect
from psycopg.rows import dict_row

from app.core.auth import require_auth
from app.core.settings import settings

router = APIRouter()

DATABASE_URL = settings.DATABASE_URL


@router.post("/approvals/approve")
def approve(payload: dict, ctx=Depends(require_auth)):
    try:
        org_id = str(ctx)
        task_id = payload.get("task_id")
        op_id = payload.get("op_id")

        if not task_id or not op_id:
            raise HTTPException(
                status_code=400,
                detail="task_id and op_id required"
            )

        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE approvals
                    SET
                        status='APPROVED',
                        approved_at=now(),
                        approved_by='strategic_bridge'
                    WHERE
                        org_id=%s
                        AND task_id=%s
                        AND op_id=%s
                        AND status='PENDING'
                        AND expires_at > NOW()
                    RETURNING *
                    """,
                    (org_id, task_id, op_id),
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="approval_not_found_or_not_pending"
                    )

                cur.execute(
                    """
                    UPDATE brain_ops
                    SET status='APPROVED'
                    WHERE
                        org_id=%s
                        AND task_id=%s
                        AND op_id=%s
                        AND requires_approval = true
                    """,
                    (org_id, task_id, op_id),
                )

                cur.execute(
                    """
                    UPDATE brain_tasks
                    SET status='PLANNED'
                    WHERE
                        org_id=%s
                        AND task_id=%s
                        AND status='RUNNING'
                    """,
                    (org_id, task_id),
                )

            conn.commit()

        return {
            "approved": row,
            "task_resumed": True,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"approval_failed: {type(e).__name__}: {e}"
        )
