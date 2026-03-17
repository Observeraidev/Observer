from typing import Dict, Any, Optional, Tuple
import json
import uuid

import requests
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
from app.core.approvals import get_approval, consume_approval

CONTROL_URL = "http://127.0.0.1:8090"
CONTROL_KEY_PATH = "/var/lib/observer/secrets/control_api_key.txt"
DATABASE_URL = settings.DATABASE_URL

from app.core.action_resolver import get_allowed_ops
ALLOWED_OPS = get_allowed_ops()


class ExecuteError(Exception):
    pass


class ApprovalRequired(Exception):
    pass


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


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
    return r.json()


def _split_op_type(op_type: str) -> Tuple[str, str]:
    s = (op_type or "").strip()
    if ":" in s:
        name, unit = s.split(":", 1)
        return name.strip(), unit.strip()
    return s, ""


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


def _insert_exec_log_pending_verify(
    cur,
    org_id: str,
    task_id: str,
    exec_id: str,
    policy_version: str,
    plan_hash: str,
    op_id: str,
    unit: str,
) -> None:
    result_json = {
        "unit": unit,
        "op_id": op_id,
        "scheduled": True,
    }

    cur.execute(
        """
        INSERT INTO brain_exec_log (
            org_id,
            task_id,
            exec_id,
            created_at,
            started_at,
            policy_version,
            plan_hash,
            status,
            result_json,
            needs_verify
        )
        VALUES (
            %s,
            %s,
            %s,
            now(),
            now(),
            %s,
            %s,
            %s,
            %s,
            true
        )
        """,
        (
            org_id,
            task_id,
            exec_id,
            policy_version,
            plan_hash,
            "PENDING_VERIFY",
            json.dumps(result_json),
        ),
    )


def _insert_exec_log_success(
    cur,
    org_id: str,
    task_id: str,
    exec_id: str,
    policy_version: str,
    plan_hash: str,
    result_json: Dict[str, Any],
) -> None:
    cur.execute(
        """
        INSERT INTO brain_exec_log (
            org_id,
            task_id,
            exec_id,
            created_at,
            started_at,
            finished_at,
            policy_version,
            plan_hash,
            status,
            result_json,
            needs_verify
        )
        VALUES (
            %s,
            %s,
            %s,
            now(),
            now(),
            now(),
            %s,
            %s,
            %s,
            %s,
            false
        )
        ON CONFLICT DO NOTHING
        """,
        (
            org_id,
            task_id,
            exec_id,
            policy_version,
            plan_hash,
            "SUCCESS",
            json.dumps(result_json),
        ),
    )


def execute_task(org_id: str, task_id: str, caller_id: Optional[str] = None) -> Dict[str, Any]:
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT policy_version, plan_hash, status
                FROM brain_tasks
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )
            task = cur.fetchone()

            if not task:
                raise NotFound("task not found")

            task_status = str(task.get("status") or "")
            if task_status == "RUNNING":
                raise Conflict("task already running")

            cur.execute(
                """
                UPDATE brain_tasks
                SET status='RUNNING'
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )

            cur.execute(
                """
                SELECT org_id, task_id, op_id, op_type, requires_approval, status
                FROM brain_ops
                WHERE org_id=%s AND task_id=%s
                ORDER BY created_at ASC, op_id ASC
                """,
                (org_id, task_id),
            )
            ops = cur.fetchall()

            policy_version = str(task.get("policy_version") or "")
            plan_hash = str(task.get("plan_hash") or "")

        conn.commit()

    if not ops:
        raise ExecuteError("no ops for task")

    last_result: Dict[str, Any] = {}
    approval_consumed_any = False

    for op in ops:
        op_id = str(op["op_id"])
        raw_type = str(op["op_type"])
        name, target = _split_op_type(raw_type)

        if name not in ALLOWED_OPS:
            raise ExecuteError(f"op not allowed: {name}")

        if not target:
            raise ExecuteError(f"missing target in op_type: {raw_type}")

        already_executed = str(op.get("status") or "") == "EXECUTED"
        if already_executed and name != "systemd.status":
            continue

        if name == "systemd.status":
            resp = _control_post("/control/systemd/status", {"unit": target})
            last_result = {"op": name, "unit": target, "response": resp}

            exec_id = uuid.uuid4().hex

            with connect(DATABASE_URL) as c:
                with c.cursor() as cu:
                    _mark_op_status(cu, org_id, task_id, op_id, "EXECUTED")
                    _mark_task_status(cu, org_id, task_id, "DONE")
                    _insert_exec_log_success(
                        cu,
                        org_id,
                        task_id,
                        exec_id,
                        policy_version,
                        plan_hash,
                        last_result,
                    )
                c.commit()

        elif name == "fs.read":
            resp = _control_post("/control/fs/read", {"path": target})
            if not resp.get("ok", False):
                raise ExecuteError(f"control fs.read failed: {resp}")

            content = str(resp.get("content", ""))
            last_result = {
                "op": name,
                "path": target,
                "response": {
                    "ok": True,
                    "path": resp.get("path"),
                    "content_preview": content[:1000],
                    "content_length": len(content),
                },
            }

            exec_id = uuid.uuid4().hex

            with connect(DATABASE_URL) as c:
                with c.cursor() as cu:
                    _mark_op_status(cu, org_id, task_id, op_id, "EXECUTED")
                    _mark_task_status(cu, org_id, task_id, "DONE")
                    _insert_exec_log_success(
                        cu,
                        org_id,
                        task_id,
                        exec_id,
                        policy_version,
                        plan_hash,
                        last_result,
                    )
                c.commit()

        elif name == "db.query":
            sql = target
            with connect(DATABASE_URL, row_factory=dict_row) as conn:
                with conn.cursor() as cu:
                    cu.execute(sql)
                    rows = cu.fetchall()
            result_rows = [dict(r) for r in rows]
            last_result = {
                "op": name,
                "query": sql,
                "response": {
                    "ok": True,
                    "rows": result_rows,
                    "row_count": len(result_rows),
                },
            }
            exec_id = uuid.uuid4().hex
            with connect(DATABASE_URL) as c:
                with c.cursor() as cu:
                    _mark_op_status(cu, org_id, task_id, op_id, "EXECUTED")
                    _mark_task_status(cu, org_id, task_id, "DONE")
                    _insert_exec_log_success(
                        cu,
                        org_id,
                        task_id,
                        exec_id,
                        policy_version,
                        plan_hash,
                        last_result,
                    )
                c.commit()
        elif name == "systemd.restart":
            if bool(op.get("requires_approval")):
                appr = get_approval(org_id, task_id, op_id)
                if not appr:
                    raise ApprovalRequired(f"approval required for op_id={op_id}")

                status = str(appr.get("status") or "")
                if status != "APPROVED":
                    raise ApprovalRequired(f"approval not approved (status={status}) for op_id={op_id}")

                op_hash = str(appr.get("op_hash") or "")
                if not op_hash:
                    raise ExecuteError(f"missing op_hash for op_id={op_id}")

                consume_approval(
                    org_id=org_id,
                    task_id=str(task_id),
                    op_id=op_id,
                    op_hash=op_hash,
                    consumed_by=(caller_id or "unknown"),
                )
                approval_consumed_any = True

            if target == "observer-api.service":
                exec_id = uuid.uuid4().hex

                with connect(DATABASE_URL) as c:
                    with c.cursor() as cu:
                        _insert_exec_log_pending_verify(
                            cu,
                            org_id,
                            task_id,
                            exec_id,
                            policy_version,
                            plan_hash,
                            op_id,
                            target,
                        )
                    c.commit()

                try:
                    _control_post("/control/systemd/restart", {"unit": target}, timeout_s=2.5)
                except Exception:
                    pass

                return {
                    "ok": True,
                    "task_id": str(task_id),
                    "status": "PENDING_VERIFY",
                    "unit": target,
                    "op_id": op_id,
                    "scheduled": True,
                    "approval_consumed": approval_consumed_any,
                }

            resp = _control_post("/control/systemd/restart", {"unit": target})
            if not resp.get("ok", False):
                raise ExecuteError(f"control restart failed: {resp}")

            last_result = {"op": name, "unit": target, "response": resp}
            exec_id = uuid.uuid4().hex

            with connect(DATABASE_URL) as c:
                with c.cursor() as cu:
                    _mark_op_status(cu, org_id, task_id, op_id, "EXECUTED")
                    _mark_task_status(cu, org_id, task_id, "DONE")
                    _insert_exec_log_success(
                        cu,
                        org_id,
                        task_id,
                        exec_id,
                        policy_version,
                        plan_hash,
                        last_result,
                    )
                c.commit()

    if not last_result:
        last_result = {"note": "no-op (all non-status ops already EXECUTED)"}

    return {
        "ok": True,
        "task_id": str(task_id),
        "status": "SUCCESS",
        "result": last_result,
        "approval_consumed": approval_consumed_any,
    }
