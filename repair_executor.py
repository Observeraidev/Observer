#!/usr/bin/env python3

import subprocess
import sys

sys.path.insert(0, "/opt/observer_api")

from service_health_classifier import classify_systemd_output


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def get_waiting_repairs():

    rc, out = run([
        "psql","-U","observer","-d","observer",
        "-t","-A","-F",",",
        "-c",
        "SELECT id,pattern_type,approval_task_id,approval_op_id,approval_op_hash "
        "FROM improvement_registry "
        "WHERE status='waiting_approval' "
        "ORDER BY id LIMIT 5"
    ])

    rows = []

    for line in out.splitlines():

        line = line.strip()

        if not line:
            continue

        parts = line.split(",", 4)

        if len(parts) != 5:
            continue

        rows.append((parts[0], parts[1], parts[2], parts[3], parts[4]))

    return rows


def update_status(row_id, status, note):

    note = note.replace("'","''")

    sql = f"""
    UPDATE improvement_registry
    SET status='{status}',
    reason=COALESCE(reason,'') || ' | repair_executor:{note}'
    WHERE id={row_id};
    """

    run(["psql","-U","observer","-d","observer","-c",sql])


def extract_service(pattern):

    if ":" not in pattern:
        return None

    return pattern.split(":",1)[1].strip()


def approval_is_granted(task_id, op_id, op_hash):

    if not task_id or not op_id or not op_hash:
        return False

    rc, out = run([
        "psql","-U","observer","-d","observer",
        "-t","-A",
        "-c",
        "SELECT count(*) "
        "FROM approvals "
        f"WHERE org_id='org_dev' "
        f"AND task_id='{task_id}' "
        f"AND op_id='{op_id}' "
        f"AND op_hash='{op_hash}' "
        "AND status='APPROVED';"
    ])

    try:
        return int(out.strip()) > 0
    except:
        return False

def log_restart(service):

    run([
        "psql","-U","observer","-d","observer",
        "-c",
        f"INSERT INTO service_action_log(service,action_type) VALUES('{service}','restart');"
    ])

def restart_service(service):

    rc,out = run([
        "psql","-U","observer","-d","observer",
        "-t","-A",
        "-c",
        f"SELECT count(*) FROM service_restart_log WHERE service='{service}' AND restarted_at > now() - interval '10 minutes';"
    ])

    try:
        recent = int(out.strip())
    except:
        recent = 0

    if recent >= 3:
        return 99, "restart_guard_triggered"

    run([
        "psql","-U","observer","-d","observer",
        "-c",
        f"INSERT INTO service_restart_log(service) VALUES('{service}');"
    ])

    return run(["systemctl","restart",service])



def verify(service):

    rc, out = run(["systemctl","status",service,"--no-pager"])

    verdict = classify_systemd_output(out)

    return verdict.get("health","unknown"), verdict.get("reason","unknown")


def main():

    rows = get_waiting_repairs()

    for row_id, pattern, approval_task_id, approval_op_id, approval_op_hash in rows:

        service = extract_service(pattern)

        if not service:
            update_status(row_id, "failed", "service_parse_error")
            continue

        if not approval_is_granted(approval_task_id, approval_op_id, approval_op_hash):
            continue

        rc, out = restart_service(service)
        log_restart(service)

        if rc != 0:
            update_status(row_id, "failed", f"{service}:restart_failed")
            continue

        health, reason = verify(service)

        if health in ("healthy","starting"):
            update_status(row_id, "executed", f"{service}:{health}:{reason}")
        else:
            update_status(row_id, "failed", f"{service}:{health}:{reason}")


if __name__ == "__main__":
    main()
