import subprocess
from psycopg import connect
from psycopg.rows import dict_row
from datetime import datetime, timezone

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def analyze_patterns(cur):

    cur.execute("""
    SELECT op_type,
           count(*) FILTER (WHERE status='FAILED') AS fail_count,
           max(created_at) FILTER (WHERE status='FAILED') AS last_fail,
           max(created_at) FILTER (WHERE status='EXECUTED') AS last_success
    FROM brain_ops
    WHERE created_at > now() - interval '6 hours'
    GROUP BY op_type
    ORDER BY fail_count DESC
    """)

    return cur.fetchall()


def classify_pattern(row):

    fail_count = row["fail_count"]
    last_fail = row["last_fail"]
    last_success = row["last_success"]

    if fail_count == 0:
        return None

    if last_success and last_success > last_fail:
        return "RESOLVED_PATTERN"

    if fail_count >= 3:
        return "ACTIVE_FAILURE_PATTERN"

    return "LOW_SIGNAL"


def analyze_verify_queue(cur):

    cur.execute("""
    SELECT count(*) AS n
    FROM brain_exec_log
    WHERE needs_verify=true
    """)

    return cur.fetchone()["n"]


def main():

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            cur.execute("""
            SELECT task_id,status,created_at
            FROM brain_tasks
            ORDER BY created_at DESC
            LIMIT 1
            """)

            last_task = cur.fetchone()

            patterns = analyze_patterns(cur)

            verify_pending = analyze_verify_queue(cur)

    print("\nSELF IMPROVEMENT ANALYSIS\n")

    if last_task:
        print("last_task:", last_task["status"], last_task["created_at"])

    print("\nPATTERN ANALYSIS\n")

    found = False

    for p in patterns:

        classification = classify_pattern(p)

        if not classification:
            continue

        found = True

        print({
            "op": p["op_type"],
            "fail_count": p["fail_count"],
            "last_fail": p["last_fail"],
            "last_success": p["last_success"],
            "classification": classification
        })

    if not found:
        print("no relevant failure patterns detected")

    print("\nVERIFY QUEUE\n")

    if verify_pending > 0:
        print("verification backlog:", verify_pending)
    else:
        print("verification queue healthy")


if __name__ == "__main__":
    main()
