from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_recent_observations(cur):
    cur.execute("""
    SELECT
        id,
        created_at,
        service_name,
        result_status,
        notes
    FROM service_monitor_log
    ORDER BY created_at DESC
    LIMIT 50
    """)
    return cur.fetchall()


def interpret(row):

    status = row["result_status"]
    notes = (row["notes"] or "").lower()

    if status == "success":
        return "OK"

    if status == "skipped_recent":
        return "OK_RECENT"

    if status == "failed":
        if "allowlist" in notes or "not allowlisted" in notes:
            return "POLICY_BLOCKED"
        return "EXECUTION_FAILED"

    return "UNKNOWN"


def main():

    counts = {}

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            rows = fetch_recent_observations(cur)

            print("\nSERVICE MONITOR INTERPRETATION\n")

            for r in rows:

                state = interpret(r)

                counts[state] = counts.get(state, 0) + 1

                print(
                    r["service_name"],
                    "|",
                    r["result_status"],
                    "→",
                    state
                )

    print("\nSUMMARY\n")

    for k, v in counts.items():
        print(k, ":", v)


if __name__ == "__main__":
    main()
