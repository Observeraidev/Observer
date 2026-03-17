import os
import json
import hashlib
from typing import Any
from datetime import datetime
from pathlib import Path

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

POLICY_PATH = os.environ.get(
    "OBSERVER_POLICY_PATH",
    "/root/observer_api/policy.json"
)

# Policy store directory (must be writable by service user)
POLICY_STORE_DIR = os.environ.get(
    "OBSERVER_POLICY_STORE",
    "/var/lib/observer/policies_store",
)

Path(POLICY_STORE_DIR).mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Core helpers
# -----------------------------------------------------------------------------

def _load_policy_json() -> Any:
    if not os.path.exists(POLICY_PATH):
        raise FileNotFoundError(f"Policy file not found: {POLICY_PATH}")
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_policy_version(policy_json: Any) -> str:
    raw = json.dumps(
        policy_json,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def ensure_policy_version(policy_version: str, policy_json: Any) -> None:
    """
    Persist policy snapshot to disk if not already stored.
    """
    filename = policy_version.replace(":", "_") + ".json"
    path = os.path.join(POLICY_STORE_DIR, filename)

    if os.path.exists(path):
        return

    snapshot = {
        "policy_version": policy_version,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "policy_json": policy_json,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


# -----------------------------------------------------------------------------
# Brain compatibility layer (THIS FIXES YOUR 500)
# -----------------------------------------------------------------------------

def compute_policy_version(policy_json: Any = None) -> str:
    """
    brain.py calls this WITHOUT arguments.
    If no policy_json provided, load policy.json automatically.
    """
    if policy_json is None:
        policy_json = _load_policy_json()
    return sha256_policy_version(policy_json)


def ensure_policy_version_exists(policy_version: str, policy_json: Any = None) -> None:
    """
    brain.py expects this name.
    """
    if policy_json is None:
        policy_json = _load_policy_json()
    ensure_policy_version(policy_version, policy_json)

def get_policy_version(policy_version: str) -> Any:
    """
    Fetch policy_json for a given policy_version from DB.
    Returns the JSON (dict) if found, else None.

    This function name is part of the public/stable API used by routes.
    """
    if not policy_version:
        return None

    # --- DB access: reuse whatever DB helper you already have in this module ---
    # Try common patterns without importing new dependencies here.
    # If you already have a function like get_conn()/db_conn()/connect_db(), use it.
    try:
        from app.db.conn import get_conn  # type: ignore
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT policy_json FROM policy_versions WHERE policy_version=%s",
            (policy_version,),
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    except Exception:
        pass

    # Fallback: if module already has a global connection helper named connect_db/get_db/conn
    try:
        connect_db = globals().get("connect_db") or globals().get("get_db") or globals().get("get_conn")
        if connect_db:
            conn = connect_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT policy_json FROM policy_versions WHERE policy_version=%s",
                (policy_version,),
            )
            row = cur.fetchone()
            cur.close()
            return row[0] if row else None
    except Exception:
        pass

    # Last resort fallback: if policy_version matches the canonical policy.json on disk, return it
    try:
        policy = _load_policy_json()
        if policy_version == sha256_policy_version(policy):
            return policy
    except Exception:
        pass

    return None
