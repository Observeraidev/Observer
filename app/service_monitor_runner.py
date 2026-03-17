import os
from psycopg import connect
from psycopg.rows import dict_row
import requests

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL
BRAIN_PLAN_URL = "http://127.0.0.1:8088/v1/brain/plan"
AUTH_TOKEN = os.getenv("OBSERVER_API_KEY", "devkey_1")
ORG_ID = "org_dev"


def fetch_active_monitors(cur):
    cur.execute("""
    SELECT id, service_name, status
    FROM service_monitors
    WHERE status = 'active'
    ORDER BY created_at ASC
    LIMIT 50
    """)
    return cur.fetchall()


def monitor_recently_observed(cur, service_name: str) -> bool:
    cur.execute("""
    SELECT 1
    FROM service_monitor_log
    WHERE service_name = %s
      AND result_status IN ('planned', 'success', 'failed')
      AND created_at > now() - interval '10 minutes'
    LIMIT 1
    """, (service_name,))
    return cur.fetchone() is not None


def create_brain_task_for_monitor(service_name: str):
    payload = {
        "intent": f"systemd.status:{service_name}"
    }

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "X-Org-Id": ORG_ID,
        "Content-Type": "application/json",
    }

    r = requests.post(BRAIN_PLAN_URL, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def log_monitor_result(cur, service_name: str, source_monitor_id: int, result_status: str, task_id: str = None, notes: str = None):
    cur.execute("""
    INSERT INTO service_monitor_log
    (
        service_name,
        source_monitor_id,
        observed_via,
        result_status,
        task_id,
        notes
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        service_name,
        source_monitor_id,
        "brain_plan",
        result_status,
        task_id,
        notes,
    ))


def main():
    created = 0
    skipped = 0
    failed = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            monitors = fetch_active_monitors(cur)

            if not monitors:
                print("\nSERVICE MONITOR RUNNER\n")
                print("no active monitors")
                return

            for m in monitors:
                monitor_id = m["id"]
                service_name = m["service_name"]

                if monitor_recently_observed(cur, service_name):
                    skipped += 1
                    log_monitor_result(
                        cur,
                        service_name=service_name,
                        source_monitor_id=monitor_id,
                        result_status="skipped_recent",
                        notes="recent real observation already exists",
                    )
                    continue

                try:
                    result = create_brain_task_for_monitor(service_name)
                    task_id = result.get("task_id")

                    created += 1
                    log_monitor_result(
                        cur,
                        service_name=service_name,
                        source_monitor_id=monitor_id,
                        result_status="planned",
                        task_id=task_id,
                        notes="brain task created for service observation",
                    )

                except Exception as e:
                    failed += 1
                    log_monitor_result(
                        cur,
                        service_name=service_name,
                        source_monitor_id=monitor_id,
                        result_status="failed",
                        notes=f"{type(e).__name__}: {e}",
                    )

            conn.commit()

    print("\nSERVICE MONITOR RUNNER\n")
    print("planned:", created)
    print("skipped:", skipped)
    print("failed:", failed)


if __name__ == "__main__":
    main()
