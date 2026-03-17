import json
import os
import time
import hashlib
import subprocess
import requests
from psycopg import connect
from psycopg.rows import dict_row

BASE = "http://127.0.0.1:8088"
from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL

HEADERS = {
    "Authorization": f"Bearer {os.getenv('OBSERVER_API_KEY', 'devkey_1')}",
    "X-Org-Id": "org_dev"
}

STATE_FILE = "/opt/observer_api/.strategic_bridge_last.json"

MODEL_URL = os.getenv("STRATEGIC_MODEL_URL", "").strip()
MODEL_API_KEY = os.getenv("STRATEGIC_MODEL_API_KEY", "").strip()
MODEL_NAME = os.getenv("STRATEGIC_MODEL_NAME", "gpt-4o-mini").strip()
POLL_SECONDS = int(os.getenv("STRATEGIC_BRIDGE_POLL_SECONDS", "30"))

ALLOWED_INTENTS = {
    "inspect_project_state",
    "inspect_service_health",
    "inspect_logs",
    "inspect_runtime_flags",
    "inspect_postmortems",
    "inspect_metrics",
}


def get_json(path: str):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def post_json(path: str, payload: dict):
    r = requests.post(
        f"{BASE}{path}",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def get_state():
    return get_json("/system/state")


def get_improvements():
    return get_json("/improvements")


def get_approvals():
    return get_json("/approvals/pending")


def approve(task_id: str, op_id: str):
    payload = {
        "task_id": task_id,
        "op_id": op_id,
    }
    return post_json("/approvals/approve", payload)


def send_intent(intent: str):
    result = subprocess.run(
        ["python3", "/root/observer/intent_gateway.py", intent],
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        return {
            "status": "rejected",
            "reason": "intent_gateway_failed",
            "intent": intent,
            "stdout": stdout,
            "stderr": stderr,
        }

    return {
        "status": "submitted_via_intent_gateway",
        "intent": intent,
        "output": stdout,
    }


def load_bridge_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_bridge_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def stable_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_incidents_and_proposals() -> dict:
    try:
        with connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT incident_class, entity_name, severity, occurrence_count
                    FROM incident_registry
                    WHERE status IN ('OPEN','MONITORING')
                    ORDER BY severity DESC, occurrence_count DESC
                    LIMIT 5
                """)
                incidents = [dict(r) for r in cur.fetchall()]
                cur.execute("""
                    SELECT proposal_type, title, risk_class, requires_approval
                    FROM structural_proposals
                    WHERE status = 'NEW'
                    ORDER BY id ASC
                    LIMIT 5
                """)
                proposals = [dict(r) for r in cur.fetchall()]
        return {"open_incidents": incidents, "pending_proposals": proposals}
    except Exception as e:
        return {"open_incidents": [], "pending_proposals": [], "error": str(e)}

def build_compact_snapshot(state: dict, improvements: dict, approvals: dict) -> dict:
    runtime = state.get("runtime", {})
    pending_approvals = approvals.get("pending", [])
    improvement_rows = improvements.get("improvements", [])

    low_risk_pending = 0
    high_risk_pending = 0

    for item in pending_approvals:
        if item.get("risk_level") == "LOW":
            low_risk_pending += 1
        else:
            high_risk_pending += 1

    new_improvements = 0
    waiting_approval_improvements = 0
    accepted_improvements = 0

    for item in improvement_rows:
        status = str(item.get("status", "")).strip().lower()

        if status == "new":
            new_improvements += 1
        elif status == "waiting_approval":
            waiting_approval_improvements += 1
        elif status == "accepted":
            accepted_improvements += 1

    return {
        "runtime": {
            "safe_mode": runtime.get("safe_mode", False),
            "storm_risk": runtime.get("storm_risk", False),
        },
        "improvements": {
            "new": new_improvements,
            "waiting_approval": waiting_approval_improvements,
            "accepted": accepted_improvements,
        },
        "approvals": {
            "pending_count": approvals.get("count", 0),
            "low_risk_pending_count": low_risk_pending,
            "non_low_risk_pending_count": high_risk_pending,
        },
        "timers": state.get("timers", {}),
        "incidents": state.get("incidents", {}).get("open_incidents", []),
        "pending_proposals": state.get("pending_proposals", []),
    }


def relevant_change(prev_snapshot: dict | None, cur_snapshot: dict) -> tuple[bool, list[str]]:
    reasons = []

    cur_runtime = cur_snapshot.get("runtime", {})
    cur_improvements = cur_snapshot.get("improvements", {})
    cur_approvals = cur_snapshot.get("approvals", {})
    cur_timers = cur_snapshot.get("timers", {})

    if prev_snapshot is None:
        reasons.append("first_snapshot")

        if cur_runtime.get("safe_mode") is True:
            reasons.append("safe_mode_true")

        if cur_runtime.get("storm_risk") is True:
            reasons.append("storm_risk_true")

        if cur_approvals.get("pending_count", 0) > 0:
            reasons.append("pending_approvals")

        if cur_improvements.get("new", 0) > 0:
            reasons.append("new_improvements")

        if cur_improvements.get("waiting_approval", 0) > 0:
            reasons.append("waiting_approval_improvements")

        unique_reasons = sorted(set(reasons))
        return (len(unique_reasons) > 0, unique_reasons)

    prev_runtime = prev_snapshot.get("runtime", {})
    prev_improvements = prev_snapshot.get("improvements", {})
    prev_approvals = prev_snapshot.get("approvals", {})
    prev_timers = prev_snapshot.get("timers", {})

    if prev_runtime.get("safe_mode") != cur_runtime.get("safe_mode"):
        reasons.append("safe_mode_changed")
        if cur_runtime.get("safe_mode") is True:
            reasons.append("safe_mode_true")

    if prev_runtime.get("storm_risk") != cur_runtime.get("storm_risk"):
        reasons.append("storm_risk_changed")
        if cur_runtime.get("storm_risk") is True:
            reasons.append("storm_risk_true")

    if prev_improvements != cur_improvements:
        reasons.append("improvements_changed")
        if cur_improvements.get("new", 0) > 0:
            reasons.append("new_improvements")
        if cur_improvements.get("waiting_approval", 0) > 0:
            reasons.append("waiting_approval_improvements")

    if prev_approvals != cur_approvals:
        reasons.append("approvals_changed")
        if cur_approvals.get("pending_count", 0) > 0:
            reasons.append("pending_approvals")

    for timer_name, timer_state in cur_timers.items():
        prev_state = prev_timers.get(timer_name)
        if prev_state != timer_state and timer_state != "active":
            reasons.append(f"timer_changed:{timer_name}:{prev_state}->{timer_state}")

    unique_reasons = sorted(set(reasons))
    return (len(unique_reasons) > 0, unique_reasons)


def build_prompt(snapshot: dict, reasons: list[str], bridge_state: dict | None) -> str:
    allowed_intents_sorted = sorted(ALLOWED_INTENTS)

    last_decision = None
    last_execution_reason = None
    last_updated_at = None

    if bridge_state and isinstance(bridge_state, dict):
        last_decision = bridge_state.get("last_decision")
        last_execution_reason = bridge_state.get("last_execution_reason")
        last_updated_at = bridge_state.get("updated_at")

    return f"""
You are a strict JSON decision engine for OBSERVER Strategic Bridge.

You must return exactly one JSON object with one action only.

Allowed actions:
- "approve"
- "intent"
- "noop"

Rules:
- Be conservative.
- If storm_risk is true, prefer noop.
- If safe_mode is true, never approve. Prefer noop.
- Only approve pending approvals when they are clearly low risk and explicitly present in pending approvals.
- If you choose "intent", the intent MUST be exactly one of the allowed intents below.
- Never invent a new intent.
- If improvements.new > 0 and safe_mode is false and storm_risk is false and pending approvals are 0, prefer an inspection intent instead of noop.
- If the system is stable and no relevant action is needed, return noop.
- Do not produce explanations outside JSON.
- Do not include markdown fences.

Current system context includes: open_incidents (active incidents), pending_proposals (structural proposals awaiting processing).
- If open_incidents is non-empty and safe_mode is false, prefer inspect_service_health or inspect_logs.
- If pending_proposals is non-empty, consider inspect_project_state to understand context before acting.

Intent guidance (use these to decide which intent fits best):
- inspect_project_state: when improvements are pending or project state is unknown
- inspect_service_health: when a service may be degraded or after a restart
- inspect_logs: when there are anomalies, errors, or unexplained behavior worth investigating
- inspect_runtime_flags: when safe_mode or storm_risk status needs to be verified

Allowed intents:
{json.dumps(allowed_intents_sorted, ensure_ascii=False)}

JSON schema:
{{
  "action": "approve|intent|noop",
  "reason": "string",
  "task_id": "string or null",
  "op_id": "string or null",
  "intent": "string or null"
}}

Relevant change reasons:
{json.dumps(reasons, ensure_ascii=False)}

Last bridge decision:
{json.dumps(last_decision, ensure_ascii=False)}

Last execution reason:
{json.dumps(last_execution_reason, ensure_ascii=False)}

Last bridge updated_at:
{json.dumps(last_updated_at, ensure_ascii=False)}

Snapshot:
{json.dumps(snapshot, ensure_ascii=False, indent=2)}
""".strip()


def extract_model_text(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        pass

    if isinstance(data, dict) and "output_text" in data:
        return str(data["output_text"])

    raise ValueError("unsupported_model_response")


def call_model(prompt: str) -> str:
    if not MODEL_URL:
        return json.dumps({
            "action": "noop",
            "reason": "model_not_configured",
            "task_id": None,
            "op_id": None,
            "intent": None,
        })

    headers = {
        "Content-Type": "application/json",
    }
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"

    payload = {
        "model": MODEL_NAME,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict JSON decision engine."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    r = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return extract_model_text(data)


def validate_decision(decision: dict, approvals: dict):
    action = decision.get("action")
    if action not in {"approve", "intent", "noop"}:
        raise ValueError("invalid_action")

    reason = decision.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("invalid_reason")

    if action == "approve":
        task_id = decision.get("task_id")
        op_id = decision.get("op_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("missing_task_id")
        if not isinstance(op_id, str) or not op_id.strip():
            raise ValueError("missing_op_id")

        found = False
        for item in approvals.get("pending", []):
            if item.get("task_id") == task_id and item.get("op_id") == op_id:
                found = True
                break

        if not found:
            raise ValueError("approve_target_not_pending")

    if action == "intent":
        intent = decision.get("intent")
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError("missing_intent")
        if intent not in ALLOWED_INTENTS:
            raise ValueError("intent_not_allowed")

    if action == "noop":
        decision["task_id"] = None
        decision["op_id"] = None
        decision["intent"] = None

    return decision


def ask_model(snapshot: dict, approvals: dict, reasons: list[str], bridge_state: dict | None) -> dict:
    prompt = build_prompt(snapshot, reasons, bridge_state)

    try:
        raw = call_model(prompt)
        decision = json.loads(raw)
        return validate_decision(decision, approvals)
    except Exception as e:
        return {
            "action": "noop",
            "reason": f"model_error:{str(e)}",
            "task_id": None,
            "op_id": None,
            "intent": None,
        }


def decide(snapshot: dict, approvals: dict, improvements: dict, reasons: list[str], bridge_state: dict | None) -> list[dict]:
    runtime = snapshot.get("runtime", {})
    improvements_summary = snapshot.get("improvements", {})
    approvals_summary = snapshot.get("approvals", {})

    if (
        improvements_summary.get("new", 0) > 0
        and not runtime.get("safe_mode", False)
        and not runtime.get("storm_risk", False)
        and approvals_summary.get("pending_count", 0) == 0
    ):
        return [{
            "action": "intent",
            "reason": "new improvements require inspection",
            "task_id": None,
            "op_id": None,
            "intent": "inspect_project_state",
        }]

    # Si hay aprobaciones HIGH risk pendientes, lanzar inspeccion activa
    if (
        approvals_summary.get("non_low_risk_pending_count", 0) > 0
        and not runtime.get("safe_mode", False)
        and not runtime.get("storm_risk", False)
    ):
        return [{
            "action": "intent",
            "reason": "high risk approvals pending - inspecting service health",
            "task_id": None,
            "op_id": None,
            "intent": "inspect_service_health",
        }]

    decision = ask_model(snapshot, approvals, reasons, bridge_state)
    return [decision]


def decision_fingerprint(decision: dict) -> str:
    payload = {
        "action": decision.get("action"),
        "task_id": decision.get("task_id"),
        "op_id": decision.get("op_id"),
        "intent": decision.get("intent"),
        "reason": decision.get("reason"),
    }
    return stable_hash(payload)


def should_execute_decision(last_state: dict | None, snapshot_hash: str, decision: dict) -> tuple[bool, str]:
    if decision.get("action") == "noop":
        return True, "noop_allowed"

    if last_state is None:
        return True, "first_execution"

    last_snapshot_hash = last_state.get("snapshot_hash")
    last_decision_hash = last_state.get("last_decision_hash")
    cur_decision_hash = decision_fingerprint(decision)

    if last_snapshot_hash == snapshot_hash and last_decision_hash == cur_decision_hash:
        return False, "duplicate_decision_same_snapshot"

    return True, "new_decision_or_new_snapshot"


def execute_decisions(decisions: list[dict]):
    for d in decisions:
        try:
            if d.get("action") == "approve":
                print("APPROVING:", d["task_id"], d["op_id"], d.get("reason"))
                out = approve(d["task_id"], d["op_id"])
                print("APPROVE_OK:", out)

            elif d.get("action") == "intent":
                print("SENDING_INTENT:", d["intent"], d.get("reason"))
                out = send_intent(d["intent"])
                print("INTENT_OK:", out)

            elif d.get("action") == "noop":
                print("NOOP:", d.get("reason", "no_reason"))

        except Exception as e:
            print("DECISION_EXECUTION_ERROR:", d, str(e))


def main_loop():
    while True:
        bridge_state = load_bridge_state()

        try:
            state = get_state()
            improvements = get_improvements()
            approvals = get_approvals()
            incidents_and_proposals = get_incidents_and_proposals()
            state["incidents"] = incidents_and_proposals
            state["pending_proposals"] = incidents_and_proposals.get("pending_proposals", [])

            snapshot = build_compact_snapshot(state, improvements, approvals)
            prev_snapshot = None
            if bridge_state and isinstance(bridge_state, dict):
                prev_snapshot = bridge_state.get("snapshot")

            changed, reasons = relevant_change(prev_snapshot, snapshot)
            snapshot_hash = stable_hash(snapshot)

            print("---- Strategic Bridge Tick ----")
            print("SNAPSHOT:", snapshot)

            last_decision = None
            executed = False
            execution_reason = "not_evaluated"

            if changed:
                print("RELEVANT_CHANGE:", reasons)
                decisions = decide(snapshot, approvals, improvements, reasons, bridge_state)
                print("DECISIONS:", decisions)

                if decisions:
                    last_decision = decisions[0]
                    can_execute, execution_reason = should_execute_decision(
                        bridge_state,
                        snapshot_hash,
                        last_decision,
                    )
                    print("EXECUTION_GATE:", can_execute, execution_reason)

                    if can_execute:
                        execute_decisions(decisions)
                        executed = True
                else:
                    print("NO_DECISIONS")
            else:
                print("NO_RELEVANT_CHANGE")
                execution_reason = "no_relevant_change"

            new_bridge_state = {
                "snapshot": snapshot,
                "snapshot_hash": snapshot_hash,
                "last_reasons": reasons if changed else [],
                "last_decision": last_decision,
                "last_decision_hash": decision_fingerprint(last_decision) if last_decision else None,
                "last_executed": executed,
                "last_execution_reason": execution_reason,
                "updated_at": int(time.time()),
            }
            save_bridge_state(new_bridge_state)

        except Exception as e:
            print("bridge_error:", str(e))

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main_loop()
