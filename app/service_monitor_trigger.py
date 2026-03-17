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
    SELECT created_at, result_status, notes
    FROM service_monitor_log
    WHERE service_name = %s
    ORDER BY created_at DESC
    LIMIT 1
    """, (service_name,))
    return cur.fetchone()


def fetch_last_real(cur, service_name: str):
    cur.execute("""
    SELECT created_at, result_status, notes
    FROM service_monitor_log
    WHERE service_name = %s
      AND result_status IN ('success','failed')
    ORDER BY created_at DESC
    LIMIT 1
    """, (service_name,))
    return cur.fetchone()


def interpret_health(last_event, last_real):

    if last_real is None:
        return "UNKNOWN"

    status = last_real["result_status"]
    notes = (last_real["notes"] or "").lower()

    if status == "success":
        if last_event and last_event["result_status"] == "skipped_recent":
            return "OK_RECENT"
        return "OK"

    if status == "failed":
        if "allowlist" in notes or "not allowlisted" in notes:
            return "POLICY_BLOCKED"
        return "EXECUTION_FAILED"

    return "UNKNOWN"


def health_to_severity(health):

    if health in ("OK", "OK_RECENT"):
        return "INFO"

    if health == "POLICY_BLOCKED":
        return "WARN"

    if health == "EXECUTION_FAILED":
        return "HIGH"

    return "WARN"


def build_proposal(service_name, health, severity):

    if severity == "INFO":
        return None

    if health == "POLICY_BLOCKED":
        return {
            "type": "MONITOR_POLICY_GAP",
            "service": service_name,
            "severity": severity,
            "suggestion": "review allowlist or disable monitor"
        }

    if health == "EXECUTION_FAILED":
        return {
            "type": "SERVICE_EXECUTION_FAILURE",
            "service": service_name,
            "severity": severity,
            "suggestion": "investigate service health or runtime"
        }

    return {
        "type": "UNKNOWN_MONITOR_STATE",
        "service": service_name,
        "severity": severity,
        "suggestion": "manual inspection recommended"
    }


def main():

    proposals = []

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            services = fetch_services(cur)

            print("\nSERVICE MONITOR TRIGGERS (DRY RUN)\n")

            for s in services:

                name = s["service_name"]

                last_event = fetch_last_event(cur, name)
                last_real = fetch_last_real(cur, name)

                health = interpret_health(last_event, last_real)
                severity = health_to_severity(health)

                proposal = build_proposal(name, health, severity)

                if proposal:
                    proposals.append(proposal)

                    print(
                        proposal["service"],
                        "| severity:", proposal["severity"],
                        "| type:", proposal["type"],
                        "| suggestion:", proposal["suggestion"]
                    )

    if not proposals:
        print("no proposals generated")


if __name__ == "__main__":
    main()
