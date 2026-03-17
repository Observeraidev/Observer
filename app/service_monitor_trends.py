from psycopg import connect
from psycopg.rows import dict_row
from datetime import timedelta

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_recent_failures(cur):

    cur.execute("""
    SELECT
        service_name,
        COUNT(*) AS failures
    FROM service_monitor_log
    WHERE result_status = 'failed'
      AND created_at > now() - interval '30 minutes'
    GROUP BY service_name
    """)
    return cur.fetchall()


def fetch_recent_history(cur, service_name):

    cur.execute("""
    SELECT result_status
    FROM service_monitor_log
    WHERE service_name = %s
      AND created_at > now() - interval '30 minutes'
    ORDER BY created_at DESC
    LIMIT 10
    """, (service_name,))
    return cur.fetchall()


def fetch_criticality(cur, service_name):

    cur.execute("""
    SELECT criticality
    FROM service_criticality
    WHERE service_name = %s
    """, (service_name,))

    row = cur.fetchone()

    if not row:
        return "unknown"

    return row["criticality"]


def detect_flapping(history):

    states = [h["result_status"] for h in history]

    if len(states) < 4:
        return False

    changes = 0

    for i in range(1, len(states)):
        if states[i] != states[i-1]:
            changes += 1

    return changes >= 3


def create_proposal(cur, service, failures, criticality):

    if criticality == "core":
        pattern = "CORE_SERVICE_INSTABILITY"
        risk = "HIGH"
        improvement_class = "B"

    elif criticality == "supporting":
        pattern = "SUPPORTING_SERVICE_INSTABILITY"
        risk = "WARN"
        improvement_class = "B"

    else:
        return False

    cur.execute("""
    INSERT INTO improvement_registry
    (
        pattern_type,
        operation,
        recommended_action,
        risk,
        improvement_class,
        status
    )
    VALUES (%s,%s,%s,%s,%s,'new')
    """,
    (
        pattern,
        service,
        f"service_failure_pattern_detected failures={failures}",
        risk,
        improvement_class
    ))

    return True


def main():

    created = 0
    skipped = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            failures = fetch_recent_failures(cur)

            print("\nSERVICE MONITOR TRENDS\n")

            for f in failures:

                service = f["service_name"]
                count = f["failures"]

                criticality = fetch_criticality(cur, service)

                history = fetch_recent_history(cur, service)

                flapping = detect_flapping(history)

                if count >= 3 or flapping:

                    created_proposal = create_proposal(
                        cur,
                        service,
                        count,
                        criticality
                    )

                    if created_proposal:
                        created += 1
                        print(service, "| failures:", count, "| flapping:", flapping, "| proposal created")

                    else:
                        skipped += 1

                else:
                    skipped += 1

            conn.commit()

    print()
    print("created:", created)
    print("skipped:", skipped)


if __name__ == "__main__":
    main()
