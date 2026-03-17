#!/usr/bin/env python3

import os
import subprocess
import sys

sys.path.insert(0, "/opt/observer_api")

from service_health_classifier import classify_systemd_output


DB_HOST = "127.0.0.1"
DB_USER = "observer"
DB_NAME = "observer"
DB_PASSWORD = os.getenv("PGPASSWORD", "observer")


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def run_psql(sql: str, tuples_only: bool = False, field_sep: str = ",") -> tuple[int, str]:
    cmd = ["psql", "-h", DB_HOST, "-U", DB_USER, "-d", DB_NAME]
    if tuples_only:
        cmd.extend(["-t", "-A", "-F", field_sep])
    cmd.extend(["-c", sql])
    return run_cmd(cmd)


def get_dispatched_rows() -> list[tuple[str, str]]:
    rc, out = run_psql(
        "SELECT id,pattern_type "
        "FROM improvement_registry "
        "WHERE status='dispatched' "
        "AND recommended_action='investigate_service_state' "
        "ORDER BY id "
        "LIMIT 5",
        tuples_only=True,
        field_sep=",",
    )

    if rc != 0:
        print(f"ERROR:get_dispatched_rows:{out.strip()}")
        return []

    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            continue
        rows.append((parts[0], parts[1]))
    return rows


def update_row(row_id: str, status: str, note: str) -> None:
    safe_note = note.replace("'", "''")
    sql = (
        "UPDATE improvement_registry "
        f"SET status='{status}', "
        f"reason=COALESCE(reason,'') || ' | analyzer:{safe_note}' "
        f"WHERE id={row_id};"
    )
    rc, out = run_psql(sql)
    if rc != 0:
        print(f"ERROR:update_row:{row_id}:{out.strip()}")


def extract_service(pattern_type: str) -> str | None:
    if ":" not in pattern_type:
        return None
    return pattern_type.split(":", 1)[1].strip()


def main() -> None:
    rows = get_dispatched_rows()

    if not rows:
        print("NO_DISPATCHED_ROWS")
        return

    for row_id, pattern_type in rows:
        service = extract_service(pattern_type)
        if not service:
            update_row(row_id, "error", "service_not_found_in_pattern")
            continue

        rc, output = run_cmd(["systemctl", "status", service, "--no-pager"])
        verdict = classify_systemd_output(output)

        health = verdict.get("health", "unknown")
        reason = verdict.get("reason", "unknown")

        if health in ("healthy", "starting"):
            update_row(row_id, "resolved", f"{service}:{health}:{reason}")
            print(f"RESOLVED:{row_id}:{service}:{health}")
        elif health in ("unhealthy", "failed"):
            update_row(row_id, "accepted", f"{service}:{health}:{reason}")
            print(f"ACCEPTED:{row_id}:{service}:{health}")
        else:
            update_row(row_id, "review", f"{service}:{health}:{reason}")
            print(f"REVIEW:{row_id}:{service}:{health}")


if __name__ == "__main__":
    main()
