from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_services(cur):
    cur.execute("""
    SELECT DISTINCT service_name
    FROM service_monitor_log
    ORDER BY service_name ASC
    """)
    return cur.fetchall()


def fetch_last_event(cur, service_name: str):
    cur.execute("""
    SELECT
        id,
        created_at,
        service_name,
        result_status,
        task_id,
        notes
    FROM service_monitor_log
    WHERE service_name = %s
    ORDER BY created_at DESC
    LIMIT 1
    """, (service_name,))
    return cur.fetchone()


def fetch_last_real_result(cur, service_name: str):
    cur.execute("""
    SELECT
        id,
        created_at,
        service_name,
        result_status,
        task_id,
        notes
    FROM service_monitor_log
    WHERE service_name = %s
      AND result_status IN ('success', 'failed')
    ORDER BY created_at DESC
    LIMIT 1
    """, (service_name,))
    return cur.fetchone()


def fetch_criticality(cur, service_name: str):
    cur.execute("""
    SELECT criticality
    FROM service_criticality
    WHERE service_name = %s
    LIMIT 1
    """, (service_name,))
    row = cur.fetchone()
    if not row:
        return "unknown"
    return row["criticality"]


def interpret_real_result(result_status: str, notes: str):
    notes = (notes or "").lower()

    if result_status == "success":
        return "OK"

    if result_status == "failed":
        if "allowlist" in notes or "not allowlisted" in notes:
            return "POLICY_BLOCKED"
        return "EXECUTION_FAILED"

    return "UNKNOWN"


def build_health_state(last_event, last_real_result):
    if last_real_result is None:
        return "UNKNOWN"

    base_state = interpret_real_result(
        last_real_result["result_status"],
        last_real_result["notes"],
    )

    if last_event and last_event["result_status"] == "skipped_recent":
        if base_state == "OK":
            return "OK_RECENT"
        return base_state

    return base_state


def build_governance_state(criticality: str, health_state: str):
    crit = (criticality or "unknown").upper()

    if health_state in ("OK", "OK_RECENT"):
        return f"{crit}_OK"

    if health_state == "POLICY_BLOCKED":
        return f"{crit}_POLICY_BLOCKED"

    if health_state == "EXECUTION_FAILED":
        return f"{crit}_EXECUTION_FAILED"

    return f"{crit}_UNKNOWN"


def main():
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            services = fetch_services(cur)

            print("\nSERVICE HEALTH STATE\n")

            for s in services:
                service_name = s["service_name"]
                last_event = fetch_last_event(cur, service_name)
                last_real_result = fetch_last_real_result(cur, service_name)
                criticality = fetch_criticality(cur, service_name)

                health_state = build_health_state(last_event, last_real_result)
                governance_state = build_governance_state(criticality, health_state)

                if last_event is not None:
                    last_seen = last_event["created_at"]
                    last_event_status = last_event["result_status"]
                else:
                    last_seen = None
                    last_event_status = "none"

                if last_real_result is not None:
                    last_real_status = last_real_result["result_status"]
                else:
                    last_real_status = "none"

                print(
                    service_name,
                    "| criticality:",
                    criticality,
                    "| health:",
                    health_state,
                    "| governance:",
                    governance_state,
                    "| last_seen:",
                    last_seen,
                    "| last_event:",
                    last_event_status,
                    "| last_real_result:",
                    last_real_status,
                )


if __name__ == "__main__":
    main()
