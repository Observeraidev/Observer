from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_candidate_rows(cur):
    cur.execute("""
    SELECT
        id,
        service_name,
        task_id,
        result_status,
        notes,
        created_at
    FROM service_monitor_log
    WHERE task_id IS NOT NULL
      AND task_id <> ''
      AND created_at > now() - interval '2 days'
    ORDER BY created_at ASC
    LIMIT 500
    """)
    return cur.fetchall()


def fetch_brain_exec_result(cur, task_id: str):
    cur.execute("""
    SELECT
        id,
        task_id,
        status,
        error,
        finished_at
    FROM brain_exec_log
    WHERE task_id = %s
    ORDER BY created_at DESC
    LIMIT 1
    """, (task_id,))
    return cur.fetchone()


def map_exec_status_to_monitor_status(exec_status: str) -> str:
    if exec_status == "success":
        return "success"
    if exec_status in ("failed", "error"):
        return "failed"
    return "planned"


def build_notes(exec_row):
    exec_status = exec_row["status"] or "unknown"
    error = exec_row["error"] or ""
    finished_at = exec_row["finished_at"]

    parts = [f"reconciled_from_brain_exec_log status={exec_status}"]

    if finished_at is not None:
        parts.append(f"finished_at={finished_at}")

    if error:
        parts.append(f"error={error}")

    return " | ".join(parts)


def needs_update(log_row, target_status, target_notes):
    current_status = log_row["result_status"] or ""
    current_notes = log_row["notes"] or ""

    if current_status != target_status:
        return True

    if current_notes != target_notes:
        return True

    return False


def update_row(cur, row_id: int, target_status: str, target_notes: str):
    cur.execute("""
    UPDATE service_monitor_log
    SET result_status = %s,
        notes = %s
    WHERE id = %s
    """, (target_status, target_notes, row_id))


def main():
    scanned = 0
    updated = 0
    pending = 0
    no_exec_row = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows = fetch_candidate_rows(cur)

            for row in rows:
                scanned += 1

                exec_row = fetch_brain_exec_result(cur, row["task_id"])
                if not exec_row:
                    no_exec_row += 1
                    continue

                target_status = map_exec_status_to_monitor_status(exec_row["status"])
                target_notes = build_notes(exec_row)

                if target_status == "planned":
                    pending += 1
                    continue

                if needs_update(row, target_status, target_notes):
                    update_row(cur, row["id"], target_status, target_notes)
                    updated += 1

            conn.commit()

    print("\nSERVICE MONITOR RECONCILE\n")
    print("scanned:", scanned)
    print("updated:", updated)
    print("pending:", pending)
    print("no_exec_row:", no_exec_row)


if __name__ == "__main__":
    main()
