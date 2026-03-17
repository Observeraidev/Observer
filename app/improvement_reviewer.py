from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def fetch_new_proposals(cur):

    cur.execute("""
    SELECT id, pattern_type, operation, recommended_action, reason, risk
    FROM improvement_registry
    WHERE status='new'
    ORDER BY created_at ASC
    LIMIT 50
    """)

    return cur.fetchall()


def decide_action(proposal):

    ptype = proposal["pattern_type"]

    if ptype == "OBSERVABILITY_GAP":
        return "accept"

    if ptype == "SERVICE_EXECUTION_FAILURE":
        return "escalate"

    if ptype == "MONITOR_POLICY_GAP":
        return "review"

    return "review"


def apply_decision(cur, proposal_id, decision):

    if decision == "accept":

        cur.execute("""
        UPDATE improvement_registry
        SET status='accepted'
        WHERE id=%s
        """, (proposal_id,))

    elif decision == "escalate":

        cur.execute("""
        UPDATE improvement_registry
        SET status='priority'
        WHERE id=%s
        """, (proposal_id,))

    else:

        cur.execute("""
        UPDATE improvement_registry
        SET status='review'
        WHERE id=%s
        """, (proposal_id,))


def main():

    accepted = 0
    escalated = 0
    review = 0

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            proposals = fetch_new_proposals(cur)

            print("\nIMPROVEMENT REVIEWER\n")

            if not proposals:
                print("no proposals")
                return

            for p in proposals:

                decision = decide_action(p)

                apply_decision(cur, p["id"], decision)

                if decision == "accept":
                    accepted += 1

                elif decision == "escalate":
                    escalated += 1

                else:
                    review += 1

                print(
                    p["id"],
                    "|",
                    p["pattern_type"],
                    "| decision:",
                    decision
                )

            conn.commit()

    print("\naccepted:", accepted)
    print("escalated:", escalated)
    print("review:", review)


if __name__ == "__main__":
    main()
