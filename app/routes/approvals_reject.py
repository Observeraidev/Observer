from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.core.approvals import reject_pending_approval

router = APIRouter()


class RejectApprovalRequest(BaseModel):
    task_id: str
    op_id: str
    op_hash: str


@router.post("/approvals/reject")
def reject_approval(
    req: RejectApprovalRequest,
    x_org_id: str = Header(...),
    x_user_id: str = Header("operator"),
):

    try:
        result = reject_pending_approval(
            org_id=x_org_id,
            task_id=req.task_id,
            op_id=req.op_id,
            op_hash=req.op_hash,
            rejected_by=x_user_id,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
