import json, hashlib
from typing import Any, Dict, Optional

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def record_hash(prev_hash: Optional[str], record: Dict[str, Any]) -> str:
    base = (prev_hash or "") + canonical_json(record)
    return "sha256:" + sha256_hex(base)
