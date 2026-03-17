from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS improvement_registry (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT now(),
            pattern_type TEXT,
            operation TEXT,
            recommended_action TEXT,
            reason TEXT,
            risk TEXT,
            status TEXT DEFAULT 'new',
            improvement_class TEXT
        )
        """)

        cur.execute("""
        ALTER TABLE improvement_registry
        ADD COLUMN IF NOT EXISTS improvement_class TEXT
        """)

        conn.commit()


def improvement_exists(cur, operation, action):
    cur.execute("""
    SELECT 1
    FROM improvement_registry
    WHERE operation=%s
      AND recommended_action=%s
      AND status IN ('new','reviewed','accepted')
    LIMIT 1
    """, (operation, action))
    return cur.fetchone() is not None


def register_improvement(cur, plan):
    if improvement_exists(cur, plan["operation"], plan["recommended_action"]):
        return False

    cur.execute("""
    INSERT INTO improvement_registry
    (
        pattern_type,
        operation,
        recommended_action,
        reason,
        risk,
        improvement_class
    )
    VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        plan["pattern_type"],
        plan["operation"],
        plan["recommended_action"],
        plan["reason"],
        plan["risk"],
        plan.get("improvement_class"),
    ))
    return True


def load_plans():
    """
    Load all plans from the current planner logic, including:
      - failure-based plans
      - observability gap plans
      - deduplication
    """
    from self_improvement_planner import (
        analyze_patterns,
        classify_pattern,
        build_plan,
        build_service_monitor_plans,
        dedupe_plans,
    )

    plans = []

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            patterns = analyze_patterns(cur)

            for p in patterns:
                classification = classify_pattern(p)
                if not classification:
                    continue

                plan = build_plan(p, classification)
                if plan:
                    plans.append(plan)

            plans.extend(build_service_monitor_plans(cur))

    return dedupe_plans(plans)


def main():
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        ensure_table(conn)

        plans = load_plans()
        inserted = 0

        with conn.cursor() as cur:
            for p in plans:
                if register_improvement(cur, p):
                    inserted += 1

            conn.commit()

    print("\nIMPROVEMENT REGISTRY\n")

    if inserted == 0:
        print("no new improvements registered")
    else:
        print("new improvements added:", inserted)


if __name__ == "__main__":
    main()
