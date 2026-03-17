from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_services(cur):
    cur.execute("""
    SELECT DISTINCT service_name
    FROM service_monitor_log
    ORDER BY service_name
    """)
    return cur.fetchall()


def fetch_last_real_result(cur, service_name):
    cur.execute("""
    SELECT result_status, notes
    FROM service_monitor_log
    WHERE service_name = %s
      AND result_status IN ('success','failed')
    ORDER BY created_at DESC
    LIMIT 1
    """, (service_name,))
    return cur.fetchone()


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


def interpret_health(result_status, notes):
    notes = (notes or "").lower()

    if result_status == "success":
        return "OK"

    if result_status == "failed":
        if "allowlist" in notes or "not allowlisted" in notes:
            return "POLICY_BLOCKED"
        return "EXECUTION_FAILED"

    return "UNKNOWN"


def governance_state(criticality, health):

    if health == "OK":
        return f"{criticality.upper()}_OK"

    if health == "EXECUTION_FAILED":
        return f"{criticality.upper()}_EXECUTION_FAILED"

    if health == "POLICY_BLOCKED":
        return f"{criticality.upper()}_POLICY_BLOCKED"

    return f"{criticality.upper()}_UNKNOWN"


def compute_severity(gov_state):

    if gov_state.startswith("CORE_OK"):
        return "INFO"

    if gov_state.startswith("SUPPORTING_OK"):
        return "INFO"

    if gov_state.startswith("TEST_OK"):
        return "INFO"

    if gov_state.startswith("CORE_EXECUTION_FAILED"):
        return "CRITICAL"

    if gov_state.startswith("SUPPORTING_EXECUTION_FAILED"):
        return "HIGH"

    if gov_state.startswith("CORE_POLICY_BLOCKED"):
        return "HIGH"

    if gov_state.startswith("SUPPORTING_POLICY_BLOCKED"):
        return "WARN"

    if gov_state.startswith("TEST_POLICY_BLOCKED"):
        return "INFO"

    return "UNKNOWN"


def main():

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            services = fetch_services(cur)

            print("\nSERVICE SEVERITY\n")

            for s in services:

                name = s["service_name"]

                last = fetch_last_real_result(cur, name)

                if not last:
                    continue

                criticality = fetch_criticality(cur, name)

                health = interpret_health(
                    last["result_status"],
                    last["notes"]
                )

                gov = governance_state(
                    criticality,
                    health
                )

                severity = compute_severity(gov)

                print(
                    name,
                    "| criticality:", criticality,
                    "| health:", health,
                    "| governance:", gov,
                    "| severity:", severity
                )


if __name__ == "__main__":
    main()
