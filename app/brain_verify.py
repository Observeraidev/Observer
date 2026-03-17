from typing import Dict, Any, Optional
import json
import datetime

import requests
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings

CONTROL_URL = "http://127.0.0.1:8090"
CONTROL_KEY_PATH = "/var/lib/observer/secrets/control_api_key.txt"
DATABASE_URL = settings.DATABASE_URL


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _control_headers() -> Dict[str, str]:
    key = open(CONTROL_KEY_PATH, "r", encoding="utf-8").read().strip()
    return {"X-Control-Key": key}


def _control_post(path: str, payload: Dict[str, Any], timeout_s: float = 5.0) -> Dict[str, Any]:
    r = requests.post(
        CONTROL_URL + path,
        json=payload,
        headers=_control_headers(),
        timeout=timeout_s,
    )
    try:
        return r.json()
    except Exception:
        return {"ok": False}


def _is_active_from_control(resp: Dict[str, Any]) -> bool:
    if not isinstance(resp, dict):
        return False

    out = str(resp.get("output") or "")
    if "Active: active (running)" in out or "Active: active" in out:
        return True

    st = str(resp.get("state") or resp.get("status") or "").lower().strip()
    if st in ("active", "running"):
        return True

    return False


def _parse_result_json(v: Any) -> Dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return {}


def _mark_op_status(cur, org_id: str, task_id: str, op_id: str, status: str) -> None:
    cur.execute(
        """
        UPDATE brain_ops
        SET status=%s
        WHERE org_id=%s AND task_id=%s AND op_id=%s
        """,
        (status, org_id, task_id, op_id),
    )


def _mark_task_status(cur, org_id: str, task_id: str, status: str) -> None:
    cur.execute(
        """
        UPDATE brain_tasks
        SET status=%s
        WHERE org_id=%s AND task_id=%s
        """,
        (status, org_id, task_id),
    )


def main() -> int:
    processed = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT org_id, task_id, exec_id, result_json
                FROM brain_exec_log
                WHERE needs_verify=true
                ORDER BY created_at ASC
                LIMIT 50
                FOR UPDATE SKIP LOCKED
                """
            )
            rows = cur.fetchall()

            for r in rows:
                org_id = r["org_id"]
                task_id = r["task_id"]
                exec_id = r["exec_id"]

                result = _parse_result_json(r.get("result_json"))
                unit = str(result.get("unit") or "").strip()
                op_id = str(result.get("op_id") or "").strip()

                evidence: Dict[str, Any] = {
                    "verified_at": _utcnow().isoformat(),
                    "unit": unit,
                    "op_id": op_id or None,
                }

                exec_status = "FAILED"
                final_status = "FAILED"
                err: Optional[str] = None

                try:
                    if not unit:
                        raise Exception("missing unit in result_json")
                    if not op_id:
                        raise Exception("missing op_id in result_json")

                    resp = _control_post("/control/systemd/status", {"unit": unit})
                    evidence["control_status"] = resp

                    if _is_active_from_control(resp):
                        exec_status = "SUCCESS"
                        final_status = "DONE"
                    else:
                        st = str(resp.get("state") or resp.get("status") or "").strip()
                        err = f"verify not active: state={st}"

                except Exception as e:
                    err = f"{type(e).__name__}: {e}"

                cur.execute(
                    """
                    UPDATE brain_exec_log
                    SET status=%s,
                        needs_verify=false,
                        verified_at=now(),
                        verification_evidence=%s,
                        error=COALESCE(error, %s)
                    WHERE org_id=%s AND task_id=%s AND exec_id=%s
                    """,
                    (
                        exec_status,
                        json.dumps(evidence),
                        err,
                        org_id,
                        task_id,
                        exec_id,
                    ),
                )

                if op_id:
                    if exec_status == "SUCCESS":
                        _mark_op_status(cur, org_id, task_id, op_id, "EXECUTED")
                        _mark_task_status(cur, org_id, task_id, "DONE")
                    else:
                        _mark_op_status(cur, org_id, task_id, op_id, "FAILED")
                        _mark_task_status(cur, org_id, task_id, "FAILED")

                processed += 1

        conn.commit()

    print(f"[brain_verify] processed={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
