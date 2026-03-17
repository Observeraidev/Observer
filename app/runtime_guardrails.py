from psycopg import connect
from psycopg.rows import dict_row

import os
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://observer:observer@127.0.0.1:5432/observer")
TASK_STORM_THRESHOLD = 50
FAIL_STORM_THRESHOLD = 20


def ensure_runtime_flags_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS runtime_flags (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT now()
    )
    """)


def check_task_storm(cur):
    cur.execute("""
    SELECT count(*) AS n
    FROM brain_tasks
    WHERE created_at > now() - interval '5 minutes'
    """)
    return cur.fetchone()["n"]


def check_failure_storm(cur):
    cur.execute("""
    SELECT count(*) AS n
    FROM brain_tasks
    WHERE status='FAILED'
      AND created_at > now() - interval '5 minutes'
    """)
    return cur.fetchone()["n"]


def set_runtime_flag(cur, key: str, value: str):
    cur.execute("""
    INSERT INTO runtime_flags(key, value)
    VALUES (%s, %s)
    ON CONFLICT (key)
    DO UPDATE SET value = EXCLUDED.value, updated_at = now()
    """, (key, value))


def check_action_health(cur):
    cur.execute("""
        SELECT action_name, risk_class, success_rate_pct,
               total_executions, health_score
        FROM v_action_memory_full
        WHERE total_executions >= 10
    """)
    actions = cur.fetchall()
    adapted = []
    for action in actions:
        name = action["action_name"]
        current_risk = action["risk_class"]
        rate = float(action["success_rate_pct"] or 100)
        score = float(action["health_score"] or 100)
        if rate < 50:
            new_risk = "CRITICAL"
        elif rate < 80:
            new_risk = "HIGH"
        elif rate >= 95 and current_risk in ("CRITICAL", "HIGH") and score >= 90:
            new_risk = "MEDIUM" if current_risk == "HIGH" else "HIGH"
        else:
            continue
        if new_risk != current_risk:
            cur.execute(
                "UPDATE action_registry SET risk_class = %s, updated_at = now() WHERE action_name = %s",
                (new_risk, name)
            )
            adapted.append({
                "action": name,
                "from": current_risk,
                "to": new_risk,
                "rate": rate
            })
    return adapted


def main():
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            ensure_runtime_flags_table(cur)
            tasks = check_task_storm(cur)
            fails = check_failure_storm(cur)
            storm = tasks > TASK_STORM_THRESHOLD or fails > FAIL_STORM_THRESHOLD
            if storm:
                set_runtime_flag(cur, "safe_mode", "true")
                set_runtime_flag(cur, "storm_risk", "true")
                state = "SAFE_MODE_ACTIVATED"
            else:
                set_runtime_flag(cur, "safe_mode", "false")
                set_runtime_flag(cur, "storm_risk", "false")
                state = "NORMAL_OPERATION"
            adapted = check_action_health(cur)
            conn.commit()

    print("\nRUNTIME GUARDRAILS\n")
    print("tasks_last_5m:", tasks)
    print("failures_last_5m:", fails)
    print("system_state:", state)
    if adapted:
        for a in adapted:
            print("action_risk_adapted:", a)
    else:
        print("action_health: all actions within thresholds")


if __name__ == "__main__":
    main()
