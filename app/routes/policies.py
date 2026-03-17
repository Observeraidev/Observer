from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Tuple

from app.core.auth import require_auth
from app.core.policy_store import get_policy_version

router = APIRouter()


def _extract_auth(ctx: Any) -> Tuple[str, str]:
    """
    Normaliza el contexto devuelto por require_auth.
    Soporta dict o string.
    """
    if isinstance(ctx, dict):
        org_id = ctx.get("org_id") or ctx.get("org") or ctx.get("X-Org-Id")
        caller = ctx.get("user_id") or ctx.get("sub") or ctx.get("caller") or ""
        if not org_id:
            raise HTTPException(status_code=500, detail="Auth context missing org_id")
        return str(org_id), str(caller)

    if isinstance(ctx, str):
        return ctx, ""

    raise HTTPException(status_code=500, detail="Unsupported auth context type")


@router.get("/v1/policies/{policy_version}")
def read_policy_version(policy_version: str, ctx=Depends(require_auth)):
    """
    Devuelve siempre un snapshot consistente:
    {
        "policy_version": str,
        "created_at": str,
        "policy_json": dict
    }

    Acepta dos posibles retornos desde get_policy_version():
    1) Snapshot completo con claves policy_version/created_at/policy_json
    2) Policy dict "pelado" (legacy) -> lo envolvemos
    """
    _org_id, _caller = _extract_auth(ctx)

    row = get_policy_version(policy_version)

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    # Caso 1: snapshot completo correcto
    if isinstance(row, dict) and "policy_json" in row:
        return {
            "policy_version": row.get("policy_version", policy_version),
            "created_at": row.get("created_at", ""),
            "policy_json": row.get("policy_json"),
        }

    # Caso 2: policy dict simple (sin wrapper)
    if isinstance(row, dict):
        return {
            "policy_version": policy_version,
            "created_at": "",
            "policy_json": row,
        }

    # Cualquier otra cosa es bug del store
    raise HTTPException(status_code=500, detail="Invalid policy store return type")
