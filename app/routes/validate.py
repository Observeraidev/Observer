from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Dict

from app.core.auth import require_auth

router = APIRouter()


class ValidateRequest(BaseModel):
    agent_id: str
    action_type: str
    intent: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    policy_ref: Dict[str, Any] = {}


@router.post("/v1/validate")
def validate(req: ValidateRequest, org_id: str = Depends(require_auth)):
    # Stub minimal para que la API arranque.
    # Si necesitas el validate real, lo restauramos después desde backup/código previo.
    return {"ok": True, "org_id": org_id, "note": "validate stub"}
