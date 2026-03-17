from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.auth import require_auth
from app.routes.brain import brain_plan, brain_execute
from app.core.brain_execute import Conflict
from app.core.intent_catalog import INTENT_CATALOG
from app.core.action_resolver import resolve_intent as _resolve_from_db

router = APIRouter()


class BrainIntent(BaseModel):
    intent: str


def resolve_intent(intent: str):
    text = intent.lower().strip()
    ops = _resolve_from_db(text)
    if ops:
        return ops
    for key, catalog_ops in INTENT_CATALOG.items():
        if key in text:
            return catalog_ops
    return None


@router.post("/brain/intent")
def handle_brain_intent(req: BrainIntent, ctx=Depends(require_auth)):
    ops = resolve_intent(req.intent)

    if not ops:
        return {
            "status": "rejected",
            "reason": "intent_not_understood",
            "intent": req.intent,
        }

    try:
        org_id = str(ctx)

        plan_result = brain_plan(
            {
                "agent_id": "brain_intent_router",
                "ops": ops,
            },
            ctx=org_id,
        )

        task_id = plan_result["task_id"]

        class DummyRequest:
            def __init__(self, org_id: str):
                self.headers = {"X-Org-Id": org_id}

        execute_result = brain_execute(
            task_id=task_id,
            request=DummyRequest(org_id),
            ctx=org_id,
        )

        return {
            "status": "executed",
            "intent": req.intent,
            "operations": ops,
            "task_id": task_id,
            "plan": plan_result,
            "execution": execute_result,
        }

    except HTTPException:
        raise
    except Conflict:
        return {
            "status": "idempotent",
            "intent": req.intent,
            "note": "plan already executed with same ops and policy",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"brain_intent_failed: {type(e).__name__}: {e}",
        )
