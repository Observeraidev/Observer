import hashlib
from fastapi import Header, HTTPException
from app.db.conn import get_conn

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def require_auth(authorization: str = Header(...), x_org_id: str = Header(...)):
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ", 1)[1].strip()
    kh = _sha256(token)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT org_id, is_active FROM api_keys WHERE key_hash=%s",
            (kh,)
        ).fetchone()

    if not row or not row[1]:
        raise HTTPException(status_code=401, detail="Invalid API key")

    org_id = row[0]
    if org_id != x_org_id:
        raise HTTPException(status_code=403, detail="Org mismatch")
    return org_id
