import os
#!/usr/bin/env python3

import subprocess
import sys
import json

API = "http://127.0.0.1:8088"

sys.path.insert(0, "/opt/observer_api")
from service_health_classifier import classify_systemd_output


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def get_accepted_rows() -> list[tuple[str, str, str]]:
    rc, out = run_cmd([
        "psql", "-U", "observer", "-d", "observer", "-t", "-A", "-F", ",",
        "-c",
        "SELECT id,pattern_type,recommended_action "
        "FROM improvement_registry "
        "WHERE status='accepted' "
        "ORDER BY id "
        "LIMIT 5"
    ])

    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def update_row(row_id: str, status: str, note: str) -> None:
    safe_note = note.replace("'", "''")
    sql = (
        "UPDATE improvement_registry "
        f"SET status='{status}', "
        f"reason=COALESCE(reason,'') || ' | self_healing:{safe_note}' "
        f"WHERE id={row_id};"
    )
    run_cmd(["psql", "-U", "observer", "-d", "observer", "-c", sql])


def update_waiting_approval(row_id: str, note: str, task_id: str | None, op_id: str | None, op_hash: str | None) -> None:
    safe_note = note.replace("'", "''")
    task_sql = "NULL" if not task_id else f"'{task_id}'"
    op_id_sql = "NULL" if not op_id else f"'{op_id}'"
    op_hash_sql = "NULL" if not op_hash else f"'{op_hash}'"

    sql = (
        "UPDATE improvement_registry "
        "SET "
        "status='waiting_approval', "
        f"reason=COALESCE(reason,'') || ' | self_healing:{safe_note}', "
        f"approval_task_id={task_sql}, "
        f"approval_op_id={op_id_sql}, "
        f"approval_op_hash={op_hash_sql} "
        f"WHERE id={row_id};"
    )
    run_cmd(["psql", "-U", "observer", "-d", "observer", "-c", sql])


def extract_service(pattern_type: str) -> str | None:
    if ":" not in pattern_type:
        return None
    return pattern_type.split(":", 1)[1].strip()


def call_brain_intent(intent: str) -> tuple[int, str]:
    payload = json.dumps({"intent": intent})
    return run_cmd([
        "curl", "-s", "-X", "POST", f"{API}/brain/intent",
        "-H", f"Authorization: Bearer {os.getenv('OBSERVER_API_KEY', 'devkey_1')}",
        "-H", "X-Org-Id: org_dev",
        "-H", "Content-Type: application/json",
        "-d", payload
    ])


def verify_service(service: str) -> tuple[str, str]:
    rc, output = run_cmd(["systemctl", "status", service, "--no-pager"])
    verdict = classify_systemd_output(output)
    return verdict.get("health", "unknown"), verdict.get("reason", "unknown")


def extract_approval_refs(output: str) -> tuple[str | None, str | None, str | None]:
    text = output.lower()
    if "approval not approved" not in text and "status=pending" not in text:
        return None, None, None

    rc, out = run_cmd([
        "psql", "-U", "observer", "-d", "observer", "-t", "-A", "-F", ",",
        "-c",
        "SELECT task_id,op_id,op_hash "
        "FROM approvals "
        "WHERE org_id='org_dev' AND status='PENDING' "
        "ORDER BY created_at DESC "
        "LIMIT 1"
    ])

    line = out.strip()
    if not line:
        return None, None, None

    parts = line.split(",", 2)
    if len(parts) != 3:
        return None, None, None

    return parts[0], parts[1], parts[2]


def recent_action_exists(service: str, action_type: str, minutes: int) -> bool:
    rc, out = run_cmd([
        "psql", "-U", "observer", "-d", "observer", "-t", "-A",
        "-c",
        "SELECT count(*) "
        "FROM service_action_log "
        f"WHERE service='{service}' "
        f"AND action_type='{action_type}' "
        f"AND created_at > now() - interval '{minutes} minutes';"
    ])

    try:
        return int(out.strip()) > 0
    except Exception:
        return False


def log_action(service: str, action_type: str) -> None:
    run_cmd([
        "psql", "-U", "observer", "-d", "observer",
        "-c",
        f"INSERT INTO service_action_log(service, action_type) VALUES('{service}', '{action_type}');"
    ])


def main() -> None:
    rows = get_accepted_rows()

    for row_id, pattern_type, recommended_action in rows:
        service = extract_service(pattern_type)
        if not service:
            update_row(row_id, "failed", "service_not_found_in_pattern")
            continue

        if recommended_action != "restart_service":
            update_row(row_id, "review", f"unsupported_action:{recommended_action}")
            continue

        if recent_action_exists(service, "restart", 10):
            update_row(row_id, "review", f"{service}:restart_cooldown_active")
            continue

        intent = f"restart {service}"
        rc, out = call_brain_intent(intent)

        if rc != 0:
            update_row(row_id, "failed", f"brain_intent_call_failed:rc={rc}")
            continue

        text = out.lower()

        if "approval not approved" in text or "status=pending" in text:
            task_id, op_id, op_hash = extract_approval_refs(out)
            log_action(service, "restart_requested")
            update_waiting_approval(
                row_id=row_id,
                note=f"{service}:approval_pending",
                task_id=task_id,
                op_id=op_id,
                op_hash=op_hash,
            )
            continue

        health, reason = verify_service(service)

        if health in ("healthy", "starting"):
            log_action(service, "restart")
            update_row(row_id, "executed", f"{service}:{health}:{reason}")
        else:
            update_row(row_id, "failed", f"{service}:{health}:{reason}")


if __name__ == "__main__":
    main()
