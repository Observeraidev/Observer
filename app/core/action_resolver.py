"""
OBSERVER — action_resolver.py
Phase 2: Resolves intents to op_types from DB instead of intent_catalog.py

This module is a DROP-IN replacement for intent_catalog.py lookups.
It does NOT modify brain_execute.py. It runs alongside the existing system.

Usage:
    from app.core.action_resolver import resolve_intent, get_allowed_ops

    # Replaces: INTENT_CATALOG.get(intent_name, [])
    ops = resolve_intent("check observer api")
    # Returns: ["systemd.status:observer-api.service"]

    # Replaces: ALLOWED_OPS set in brain_execute.py
    allowed = get_allowed_ops()
    # Returns: {"systemd.status", "systemd.restart", "fs.read", "db.query"}
"""

from typing import List, Set, Optional, Dict, Any
import logging

from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def resolve_intent(intent_name: str) -> List[str]:
    """
    Resolve an intent name to a list of op_types.

    Equivalent to: INTENT_CATALOG.get(intent_name, [])

    Returns op_types in execution_order, format: "action_name:target"
    Example: ["systemd.status:observer-api.service", "systemd.status:brain-worker.service"]

    Falls back to intent_catalog.py if DB lookup fails.
    """
    try:
        ops = _resolve_from_db(intent_name)
        if ops:
            return ops
        logger.warning(f"[action_resolver] intent not found in DB: {intent_name!r}, falling back to catalog")
    except Exception as e:
        logger.error(f"[action_resolver] DB error resolving intent {intent_name!r}: {e}, falling back to catalog")

    return _resolve_from_catalog(intent_name)


def get_allowed_ops() -> Set[str]:
    """
    Return the set of allowed op names from action_registry.

    Equivalent to: ALLOWED_OPS in brain_execute.py

    Returns only ACTIVE actions.
    Falls back to hardcoded set if DB fails.
    """
    try:
        return _allowed_ops_from_db()
    except Exception as e:
        logger.error(f"[action_resolver] DB error loading allowed ops: {e}, falling back to hardcoded set")
        return _allowed_ops_fallback()


def get_action_info(action_name: str) -> Optional[Dict[str, Any]]:
    """
    Return full action metadata from action_registry.

    Returns dict with: action_name, risk_class, requires_approval, status
    Returns None if action not found.
    """
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT action_name, description, risk_class,
                           requires_approval, status
                    FROM action_registry
                    WHERE action_name = %s
                    """,
                    (action_name,)
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.error(f"[action_resolver] DB error getting action info for {action_name!r}: {e}")
        return None


def intent_exists(intent_name: str) -> bool:
    """
    Check if an intent is registered and active in DB.
    """
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM intent_registry
                    WHERE intent_name = %s AND status = 'ACTIVE'
                    """,
                    (intent_name,)
                )
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"[action_resolver] DB error checking intent {intent_name!r}: {e}")
        return False


def list_intents() -> List[str]:
    """
    Return all active intent names from DB.
    """
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT intent_name FROM intent_registry
                    WHERE status = 'ACTIVE'
                    ORDER BY intent_name
                    """
                )
                return [row["intent_name"] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"[action_resolver] DB error listing intents: {e}")
        return list(_resolve_from_catalog.__globals__.get("INTENT_CATALOG", {}).keys())


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _resolve_from_db(intent_name: str) -> List[str]:
    """
    Query intent_action_map for op_types in execution_order.
    Returns list of "action_name:target" strings.
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.action_name, m.target, m.execution_order
                FROM intent_action_map m
                JOIN intent_registry i ON i.intent_name = m.intent_name
                WHERE m.intent_name = %s
                  AND m.status = 'ACTIVE'
                  AND i.status = 'ACTIVE'
                ORDER BY m.execution_order ASC, m.id ASC
                """,
                (intent_name,)
            )
            rows = cur.fetchall()

    if not rows:
        return []

    ops = []
    for row in rows:
        action = row["action_name"]
        target = row.get("target") or ""
        if target:
            ops.append(f"{action}:{target}")
        else:
            ops.append(action)

    return ops


def _allowed_ops_from_db() -> Set[str]:
    """
    Query action_registry for ACTIVE action names.
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT action_name FROM action_registry
                WHERE status = 'ACTIVE'
                """
            )
            rows = cur.fetchall()

    return {row["action_name"] for row in rows}


def _resolve_from_catalog(intent_name: str) -> List[str]:
    """
    Fallback: resolve from intent_catalog.py (existing Python dict).
    """
    try:
        from app.core.intent_catalog import INTENT_CATALOG
        return INTENT_CATALOG.get(intent_name, [])
    except ImportError:
        logger.error("[action_resolver] intent_catalog.py not found for fallback")
        return []


def _allowed_ops_fallback() -> Set[str]:
    """
    Fallback: hardcoded ALLOWED_OPS matching brain_execute.py.
    """
    return {"systemd.status", "systemd.restart", "fs.read", "db.query"}


# -----------------------------------------------------------------------
# Parity check (run once to verify DB matches catalog)
# -----------------------------------------------------------------------

def verify_parity() -> Dict[str, Any]:
    """
    Compare DB resolver output against intent_catalog.py.
    Returns dict with match status and any differences found.

    Run this before switching brain_execute.py to use action_resolver.
    """
    try:
        from app.core.intent_catalog import INTENT_CATALOG
    except ImportError:
        return {"error": "intent_catalog.py not found"}

    results = {
        "total": len(INTENT_CATALOG),
        "match": 0,
        "mismatch": 0,
        "missing": 0,
        "differences": []
    }

    for intent_name, expected_ops in INTENT_CATALOG.items():
        try:
            actual_ops = _resolve_from_db(intent_name)
        except Exception as e:
            results["missing"] += 1
            results["differences"].append({
                "intent": intent_name,
                "issue": f"DB error: {e}"
            })
            continue

        if not actual_ops:
            results["missing"] += 1
            results["differences"].append({
                "intent": intent_name,
                "issue": "not found in DB",
                "expected": expected_ops
            })
        elif actual_ops == expected_ops:
            results["match"] += 1
        else:
            results["mismatch"] += 1
            results["differences"].append({
                "intent": intent_name,
                "expected": expected_ops,
                "actual": actual_ops
            })

    results["parity_ok"] = results["mismatch"] == 0 and results["missing"] == 0
    return results


if __name__ == "__main__":
    import json
    print("Running parity check...")
    result = verify_parity()
    print(json.dumps(result, indent=2))
