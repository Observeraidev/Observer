from fastapi import APIRouter, Depends, HTTPException
from psycopg import connect
from psycopg.rows import dict_row

from app.core.auth import require_auth
from app.core.settings import settings

router = APIRouter()

DATABASE_URL = settings.DATABASE_URL


@router.get("/improvements")
def improvements(ctx=Depends(require_auth)):
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        created_at,
                        pattern_type,
                        operation,
                        recommended_action,
                        reason,
                        risk,
                        status,
                        improvement_class
                    FROM improvement_registry
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                )

                rows = cur.fetchall()

        return {
            "improvements": rows,
            "count": len(rows),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"improvements_failed: {type(e).__name__}: {e}"
        )
