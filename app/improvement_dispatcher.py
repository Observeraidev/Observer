from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_accepted_proposals(cur):

    cur.execute("""
    SELECT id, pattern_type, operation, recommended_action, reason
    FROM improvement_registry
    WHERE status='accepted'
    ORDER BY created_at ASC
    LIMIT 20
    """)

    return cur.fetchall()


def execute_proposal(proposal):

    operation = proposal["operation"]
    action = proposal["recommended_action"]

    print(
        "EXECUTING:",
        proposal["id"],
        "|",
        operation,
        "| action:",
        action
    )

    # v1: solo simulación segura
    # aquí en el futuro se conectará con observer-control

    return True


def update_status(cur, proposal_id, success):

    if success:

        cur.execute("""
        UPDATE improvement_registry
        SET status='executed'
        WHERE id=%s
        """, (proposal_id,))

    else:

        cur.execute("""
        UPDATE improvement_registry
        SET status='failed'
        WHERE id=%s
        """, (proposal_id,))


def main():

    executed = 0
    failed = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            proposals = fetch_accepted_proposals(cur)

            print("\nIMPROVEMENT DISPATCHER\n")

            if not proposals:
                print("no accepted proposals")
                return

            for p in proposals:

                success = execute_proposal(p)

                update_status(cur, p["id"], success)

                if success:
                    executed += 1
                else:
                    failed += 1

            conn.commit()

    print("\nexecuted:", executed)
    print("failed:", failed)


if __name__ == "__main__":
    main()
