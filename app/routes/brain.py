import os
from app.core.approvals import approve_pending_approval
from app.core.approvals import insert_pending_approval
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Any, Tuple, List, Dict
import logging
import uuid
import hashlib

from app.core.auth import require_auth
from app.core.brain_execute import (
    execute_task,
    ApprovalRequired,
    Conflict,
    NotFound,
    ExecuteError,
)
from app.core.brain_store import (
    create_task,
    insert_ops,
    get_task_with_ops,
)
from app.core.policy_store import (
    compute_policy_version,
    ensure_policy_version_exists,
)

router = APIRouter()
logger = logging.getLogger("observer_api.brain")


def _extract_auth(ctx: Any) -> Tuple[str, str]:
    if isinstance(ctx, dict):
        org_id = ctx.get("org_id") or ctx.get("org") or ctx.get("X-Org-Id")
        caller = ctx.get("user_id") or ctx.get("sub") or ctx.get("caller") or ""
        if not org_id:
            raise HTTPException(status_code=500, detail="Auth context missing org_id")
        return str(org_id), str(caller)

    if isinstance(ctx, str):
        return ctx, ""

    raise HTTPException(status_code=500, detail="Invalid auth context")


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _risk_and_approval(op_type: str) -> Tuple[str, bool]:
    """
    V0 policy:
      - systemd.status => LOW, no approval
      - systemd.restart/stop/start => HIGH, approval required
      - db.query, fs.read => MED, no approval (tune later)
      - fs.write, systemd.*(non-status) => HIGH, approval required
    """
    if op_type.startswith("systemd.status:"):
        return ("LOW", False)

    if (
        op_type.startswith("systemd.restart:")
        or op_type.startswith("systemd.stop:")
        or op_type.startswith("systemd.start:")
    ):
        return ("HIGH", True)

    if op_type.startswith("fs.write:"):
        return ("HIGH", True)

    if op_type.startswith("fs.read:") or op_type.startswith("db.query:"):
        return ("MED", False)

    return ("HIGH", True)


def _normalize_ops(ops: List[str], policy_version: str) -> List[Dict[str, Any]]:
    """
    Convert list[str] into list[dict] for brain_ops insert.
    Deterministic hashing: include policy_version so a plan is pinned to policy.
    """
    out: List[Dict[str, Any]] = []
    for raw in ops:
        if not isinstance(raw, str) or ":" not in raw:
            raise HTTPException(status_code=400, detail=f"Invalid op format: {raw!r}")

        op_type = raw.strip()
        risk_level, requires_approval = _risk_and_approval(op_type)

        op_id = str(uuid.uuid4())
        op_hash = _sha256(f"{policy_version}|{op_type}")

        out.append(
            {
                "op_id": op_id,
                "op_type": op_type,
                "op_hash": op_hash,
                "risk_level": risk_level,
                "requires_approval": requires_approval,
            }
        )
    return out


@router.post("/v1/brain/approve")
def brain_approve(req: dict, ctx=Depends(require_auth)):
    org_id, caller = _extract_auth(ctx)
    if not caller:
        caller = os.getenv("OBSERVER_API_KEY", "devkey_1")

    if not isinstance(req, dict):
        raise HTTPException(status_code=400, detail="Invalid request payload")

    task_id = req.get("task_id")
    op_id = req.get("op_id")
    op_hash = req.get("op_hash")

    if not task_id or not isinstance(task_id, str):
        raise HTTPException(status_code=400, detail="task_id required")
    if not op_id or not isinstance(op_id, str):
        raise HTTPException(status_code=400, detail="op_id required")
    if not op_hash or not isinstance(op_hash, str):
        raise HTTPException(status_code=400, detail="op_hash required")

    try:
        out = approve_pending_approval(
            org_id=org_id,
            task_id=task_id,
            op_id=op_id,
            op_hash=op_hash,
            approved_by=caller,
        )
        return out

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"approve failed: {type(e).__name__}: {e}")


@router.post("/v1/brain/plan")
def brain_plan(req: dict, ctx=Depends(require_auth)):
    org_id, caller = _extract_auth(ctx)

    if not caller:
        caller = os.getenv("OBSERVER_API_KEY", "devkey_1")

    if not isinstance(req, dict):
        raise HTTPException(status_code=400, detail="Invalid request payload")

    intent = req.get("intent")

    if intent and isinstance(intent, str):
        agent_id = req.get("agent_id") or "agent_intent_1"
        ops = [intent]
    else:
        agent_id = req.get("agent_id")
        ops = req.get("ops")

    if not agent_id or not isinstance(agent_id, str):
        raise HTTPException(status_code=400, detail="agent_id required")

    if ops is None or not isinstance(ops, list):
        raise HTTPException(status_code=400, detail="ops must be a list")

    policy_version = compute_policy_version()
    ensure_policy_version_exists(policy_version)

    task_id = str(uuid.uuid4())

    create_task(
        org_id=org_id,
        task_id=task_id,
        created_by=agent_id,
        policy_version=policy_version,
    )

    op_objs = _normalize_ops(ops, policy_version=policy_version)
    plan_hash = insert_ops(org_id, task_id, policy_version, op_objs)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    for o in op_objs:
        if bool(o.get("requires_approval")):
            insert_pending_approval(
                org_id=org_id,
                task_id=task_id,
                op_id=o["op_id"],
                op_hash=o["op_hash"],
                user_id=caller,
                risk_level=o.get("risk_level", ""),
                expires_at=expires_at,
            )

    return {
        "task_id": task_id,
        "ops": [o["op_type"] for o in op_objs],
        "policy_version": policy_version,
        "plan_hash": plan_hash,
    }


@router.post("/v1/brain/execute/{task_id}")
def brain_execute(task_id: str, request: Request, ctx=Depends(require_auth)):
    org_id = request.headers.get("X-Org-Id") or ""
    if not org_id:
        raise HTTPException(status_code=400, detail="X-Org-Id header required")

    caller_id = None
    try:
        caller_id = getattr(ctx, "agent_id", None) or getattr(ctx, "sub", None)
    except Exception:
        caller_id = None

    try:
        result = execute_task(org_id=org_id, task_id=task_id, caller_id=caller_id)
        return result
    except ApprovalRequired as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Conflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ExecuteError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"execute crashed: {type(e).__name__}: {e}")


@router.get("/v1/brain/status/{task_id}")
def brain_status(task_id: str, ctx=Depends(require_auth)):
    org_id, _ = _extract_auth(ctx)
    task = get_task_with_ops(org_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
