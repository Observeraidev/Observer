import os
import hmac
import hashlib
from datetime import datetime

# V0 secret. En prod: poner esto en settings/env y rotarlo.
APPROVAL_SECRET = os.getenv("APPROVAL_SECRET", "dev_secret_change_this")


def make_signature(op_hash: str, user_id: str, expires_at_epoch: int) -> str:
    payload = f"{op_hash}:{user_id}:{expires_at_epoch}"
    return hmac.new(APPROVAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(op_hash: str, user_id: str, expires_at_iso: str, signature: str) -> bool:
    """
    Server receives expires_at as ISO string currently (we pass approval["expires_at"].isoformat()).
    We canonicalize it to epoch seconds before verifying.
    """
    try:
        # datetime.fromisoformat supports offsets like +00:00 / +01:00
        dt = datetime.fromisoformat(expires_at_iso)
        expires_at_epoch = int(dt.timestamp())
    except Exception:
        return False

    expected = make_signature(op_hash, user_id, expires_at_epoch)
    return hmac.compare_digest(expected, signature)
