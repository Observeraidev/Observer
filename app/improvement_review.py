import sys
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def list_improvements(cur):

    cur.execute("""
    SELECT id,pattern_type,operation,recommended_action,risk,status,created_at
    FROM improvement_registry
    ORDER BY created_at DESC
    LIMIT 20
    """)

    rows = cur.fetchall()

    print("\nIMPROVEMENT REVIEW\n")

    if not rows:
        print("no improvements registered")
        return

    for r in rows:
        print(
            f"{r['id']} | {r['status']} | {r['risk']} | "
            f"{r['operation']} | {r['recommended_action']}"
        )


def accept_improvement(cur, improvement_id):

    cur.execute("""
    UPDATE improvement_registry
    SET status='accepted'
    WHERE id=%s
    """, (improvement_id,))

    print(f"\naccepted improvement {improvement_id}")


def reject_improvement(cur, improvement_id):

    cur.execute("""
    UPDATE improvement_registry
    SET status='rejected'
    WHERE id=%s
    """, (improvement_id,))

    print(f"\nrejected improvement {improvement_id}")


def main():

    if len(sys.argv) < 2:
        print("\nusage:")
        print("  python3 improvement_review.py list")
        print("  python3 improvement_review.py accept <id>")
        print("  python3 improvement_review.py reject <id>")
        return

    command = sys.argv[1]

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            if command == "list":
                list_improvements(cur)

            elif command == "accept":
                if len(sys.argv) < 3:
                    print("missing id")
                    return
                accept_improvement(cur, sys.argv[2])

            elif command == "reject":
                if len(sys.argv) < 3:
                    print("missing id")
                    return
                reject_improvement(cur, sys.argv[2])

            else:
                print("unknown command")
                return

            conn.commit()


if __name__ == "__main__":
    main()
