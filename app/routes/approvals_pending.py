from fastapi import APIRouter, Depends, HTTPException
from psycopg import connect
from psycopg.rows import dict_row

from app.core.auth import require_auth
from app.core.settings import settings

router = APIRouter()

DATABASE_URL = settings.DATABASE_URL


@router.get("/approvals/pending")
def approvals_pending(ctx=Depends(require_auth)):
    try:
        org_id = str(ctx)

        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        org_id,
                        task_id,
                        op_id,
                        op_hash,
                        status,
                        risk_level,
                        created_at,
                        expires_at,
                        approved_at,
                        approved_by,
                        used_at,
                        used_by,
                        consumed_at,
                        consumed_by
                    FROM approvals
                    WHERE org_id=%s
                      AND status='PENDING'
                      AND expires_at > NOW()
                    ORDER BY created_at ASC
                    """,
                    (org_id,),
                )
                rows = cur.fetchall()

        return {
            "pending": rows,
            "count": len(rows),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"approvals_pending_failed: {type(e).__name__}: {e}"
        )
