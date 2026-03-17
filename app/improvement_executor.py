from psycopg import connect
from psycopg.rows import dict_row
import subprocess

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_executable_proposals(cur):

    cur.execute("""
    SELECT *
    FROM improvement_registry
    WHERE status = 'accepted'
    ORDER BY created_at
    LIMIT 5
    """)

    return cur.fetchall()


def mark_executed(cur, proposal_id):

    cur.execute("""
    UPDATE improvement_registry
    SET status='executed'
    WHERE id=%s
    """, (proposal_id,))


def mark_failed(cur, proposal_id):

    cur.execute("""
    UPDATE improvement_registry
    SET status='failed'
    WHERE id=%s
    """, (proposal_id,))


def execute_investigate_service(proposal):

    op = proposal["operation"]

    if not op.startswith("systemd.status:"):
        return False

    service = op.split(":",1)[1]

    try:

        result = subprocess.run(
            ["systemctl","status",service,"--no-pager"],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except Exception:
        return False


def execute_class_a(proposal):

    action = proposal["recommended_action"]

    if action.startswith("record_resolution"):
        return True

    if action.startswith("add_service_monitor"):
        return True

    if action.startswith("investigate_service_health"):
        return execute_investigate_service(proposal)

    return False


def main():

    executed = 0
    failed = 0
    skipped = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            proposals = fetch_executable_proposals(cur)

            print("\nIMPROVEMENT EXECUTOR\n")

            if not proposals:
                print("no accepted proposals")
                return

            for p in proposals:

                pid = p["id"]
                cls = p["improvement_class"]

                if cls != "A":
                    skipped += 1
                    continue

                ok = execute_class_a(p)

                if ok:

                    mark_executed(cur, pid)
                    executed += 1
                    print("executed proposal", pid)

                else:

                    mark_failed(cur, pid)
                    failed += 1
                    print("failed proposal", pid)

            conn.commit()

    print()
    print("executed:", executed)
    print("failed:", failed)
    print("skipped:", skipped)


if __name__ == "__main__":
    main()
