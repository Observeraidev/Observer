import subprocess
from psycopg import connect
from psycopg.rows import dict_row
from datetime import datetime, timezone

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def check_timer() -> bool:
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", "observer-brain-intent-feeder.timer"],
            text=True,
        ).strip()
        return out == "active"
    except Exception:
        return False


def main() -> None:

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            SELECT task_id,status,created_at
            FROM brain_tasks
            ORDER BY created_at DESC
            LIMIT 1
            """)
            last_task = cur.fetchone()

            cur.execute("""
            SELECT count(*) AS n
            FROM brain_tasks
            WHERE created_at > now() - interval '1 hour'
            """)
            tasks_last_hour = int(cur.fetchone()["n"])

            cur.execute("""
            SELECT count(*) AS n
            FROM brain_tasks
            WHERE status='FAILED'
            AND created_at > now() - interval '1 hour'
            """)
            failed_last_hour = int(cur.fetchone()["n"])

            cur.execute("""
            SELECT count(*) AS n
            FROM brain_exec_log
            WHERE needs_verify=true
            """)
            verify_pending = int(cur.fetchone()["n"])

            cur.execute("""
            SELECT created_at,status
            FROM brain_ops
            WHERE op_type='systemd.status:observer-api.service'
            ORDER BY created_at DESC
            LIMIT 1
            """)
            observer_api_last = cur.fetchone()

            cur.execute("""
            SELECT created_at,status
            FROM brain_ops
            WHERE op_type='systemd.status:brain-worker.service'
            ORDER BY created_at DESC
            LIMIT 1
            """)
            brain_worker_last = cur.fetchone()

            cur.execute("""
            SELECT task_id,status,created_at
            FROM brain_tasks
            ORDER BY created_at DESC
            LIMIT 5
            """)
            recent = cur.fetchall()

    timer_ok = check_timer()

    now = datetime.now(timezone.utc)

    observer_api_ok = observer_api_last and observer_api_last["status"] == "EXECUTED"
    brain_worker_ok = brain_worker_last and brain_worker_last["status"] == "EXECUTED"

    # ------------------------------------------------
    # HEALTH EVALUATION
    # ------------------------------------------------

    if not timer_ok:
        state = "BROKEN"

    elif verify_pending > 0:
        state = "DEGRADED"

    elif not observer_api_ok or not brain_worker_ok:
        state = "DEGRADED"

    elif failed_last_hour > 0:
        state = "HEALTHY_WITH_OLD_FAILURES"

    else:
        state = "HEALTHY"

    # ------------------------------------------------

    print("\nOBSERVER BRAIN HEALTH\n")

    print("CURRENT_STATE:", state)
    print()

    print("feeder_timer_active:", "yes" if timer_ok else "NO")

    if last_task:
        print("last_task_created:", last_task["created_at"])
        print("last_task_status:", last_task["status"])
        print("last_task_id:", last_task["task_id"])
    else:
        print("last_task: none")

    print()

    print("tasks_last_hour:", tasks_last_hour)
    print("tasks_failed_last_hour:", failed_last_hour)
    print("verify_pending:", verify_pending)

    print()

    if observer_api_last:
        print("observer_api_last_check:", observer_api_last["status"], observer_api_last["created_at"])

    if brain_worker_last:
        print("brain_worker_last_check:", brain_worker_last["status"], brain_worker_last["created_at"])

    print("\nRECENT TASKS")

    for r in recent:
        print(f'{r["created_at"]}  {r["status"]}  {r["task_id"]}')


if __name__ == "__main__":
    main()
