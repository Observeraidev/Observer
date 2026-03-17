from psycopg import connect
from psycopg.rows import dict_row
import json

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL

CRITICAL_SERVICES = {
    "observer-api.service",
    "brain-worker.service",
}


def analyze_patterns(cur):
    cur.execute("""
    SELECT op_type,
           count(*) FILTER (WHERE status='FAILED') AS fail_count,
           max(created_at) FILTER (WHERE status='FAILED') AS last_fail,
           max(created_at) FILTER (WHERE status='EXECUTED') AS last_success
    FROM brain_ops
    WHERE created_at > now() - interval '6 hours'
    GROUP BY op_type
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


def classify_improvement_class(recommended_action: str, risk: str) -> str:
    action = str(recommended_action or "").strip()
    risk_u = str(risk or "").strip().upper()

    if action in {
        "record_resolution",
        "observe",
        "add_diagnostic_signal",
        "add_service_monitor",
        "improve_monitoring",
        "improve_health_check",
    } and risk_u == "LOW":
        return "A"

    if action in {
        "investigate_runtime_failure",
        "adjust_threshold",
        "tune_timer",
        "update_non_critical_script",
        "expand_allowlist",
    } and risk_u in {"MEDIUM", "LOW"}:
        return "B"

    return "C"


def build_plan(row, classification):
    op = row["op_type"]
    fail_count = row["fail_count"]

    if classification == "ACTIVE_FAILURE_PATTERN":
        if op.startswith("systemd.status:"):
            recommended_action = "add_diagnostic_signal"
            risk = "LOW"
            reason = "repeated failures suggest more diagnostic visibility is needed"
        else:
            recommended_action = "investigate_runtime_failure"
            risk = "MEDIUM"
            reason = "repeated failures without recent success"

        plan = {
            "pattern_type": classification,
            "operation": op,
            "recommended_action": recommended_action,
            "reason": reason,
            "risk": risk,
        }
        plan["improvement_class"] = classify_improvement_class(recommended_action, risk)
        return plan

    if classification == "RESOLVED_PATTERN":
        recommended_action = "record_resolution"
        risk = "LOW"
        plan = {
            "pattern_type": classification,
            "operation": op,
            "recommended_action": recommended_action,
            "reason": "recent success after previous failures",
            "risk": risk,
        }
        plan["improvement_class"] = classify_improvement_class(recommended_action, risk)
        return plan

    if classification == "LOW_SIGNAL":
        recommended_action = "observe"
        risk = "LOW"
        plan = {
            "pattern_type": classification,
            "operation": op,
            "recommended_action": recommended_action,
            "reason": "isolated failure signal",
            "risk": risk,
        }
        plan["improvement_class"] = classify_improvement_class(recommended_action, risk)
        return plan

    return None


def build_service_monitor_plans(cur):
    """
    Evolutive planner:
    if a critical service has no recent systemd.status observation,
    propose adding/strengthening service monitoring.
    """
    plans = []

    for unit in sorted(CRITICAL_SERVICES):
        op_type = f"systemd.status:{unit}"

        cur.execute("""
        SELECT count(*) AS n
        FROM brain_ops
        WHERE op_type = %s
          AND created_at > now() - interval '6 hours'
        """, (op_type,))
        row = cur.fetchone()
        seen_recently = int(row["n"] or 0) > 0

        if not seen_recently:
            recommended_action = "add_service_monitor"
            risk = "LOW"
            plan = {
                "pattern_type": "OBSERVABILITY_GAP",
                "operation": op_type,
                "recommended_action": recommended_action,
                "reason": "critical service lacks recent monitoring signal",
                "risk": risk,
                "improvement_class": classify_improvement_class(recommended_action, risk),
            }
            plans.append(plan)

    return plans


def dedupe_plans(plans):
    out = []
    seen = set()

    for p in plans:
        key = (
            p.get("pattern_type"),
            p.get("operation"),
            p.get("recommended_action"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(p)

    return out


def main():
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

    plans = dedupe_plans(plans)

    print("\nSELF IMPROVEMENT PLANNER\n")

    if not plans:
        print("no improvement plans generated")
        return

    for p in plans:
        print(json.dumps(p, indent=2, default=str))


if __name__ == "__main__":
    main()
