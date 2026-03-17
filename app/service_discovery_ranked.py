import subprocess
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


PRIORITY_EXACT = {
    "observer-control.service",
    "observer-state-engine.service",
    "observer-state-update.service",
    "observer-bridge.service",
    "observer-brain-intent-feeder.service",
    "observer-brain-verify.service",
    "observer-verify.service",
    "observer-runtime-guardrails.service",
    "llm-orchestrator.service",
    "memory-api.service",
    "postgresql.service",
    "postgresql@14-main.service",
    "nginx.service",
}

IGNORE_EXACT = {
    "emergency.service",
    "rescue.service",
    "finalrd.service",
    "getty-static.service",
    "getty@tty1.service",
    "plymouth-quit-wait.service",
    "plymouth-quit.service",
    "plymouth-read-write.service",
    "plymouth-start.service",
    "service-monitor-reconcile.service",
    "service-monitor-runner.service",
    "service-monitor-trigger-writer.service",
}

IGNORE_PREFIXES = (
    "apport",
    "cloud-",
    "modprobe@",
    "motd-",
    "update-notifier",
    "ua-",
    "user-runtime-dir@",
    "user@",
    "plymouth-",
)

IGNORE_CONTAINS = (
    "getty",
    "rescue",
    "emergency",
    "modprobe",
    "plymouth",
)


def run_systemctl_list_units():
    cmd = [
        "systemctl",
        "list-units",
        "--type=service",
        "--all",
        "--no-pager",
        "--no-legend",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    services = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue

        unit = parts[0]
        load = parts[1]
        active = parts[2]
        sub = parts[3]
        description = parts[4] if len(parts) > 4 else ""

        if unit.endswith(".service"):
            services.append({
                "service_name": unit,
                "load": load,
                "active": active,
                "sub": sub,
                "description": description,
            })

    return services


def fetch_monitored_services(cur):
    cur.execute("""
    SELECT service_name
    FROM service_monitors
    """)
    return {r["service_name"] for r in cur.fetchall()}


def should_ignore(service_name: str) -> bool:
    if service_name in IGNORE_EXACT:
        return True

    for prefix in IGNORE_PREFIXES:
        if service_name.startswith(prefix):
            return True

    for token in IGNORE_CONTAINS:
        if token in service_name:
            return True

    return False


def classify_service(service):
    name = service["service_name"]
    active = service["active"]
    load = service["load"]

    if should_ignore(name):
        return "ignore"

    if name in PRIORITY_EXACT:
        return "priority"

    if load != "loaded":
        return "ignore"

    if active == "active":
        return "secondary"

    return "ignore"


def main():
    print("\nSERVICE DISCOVERY RANKED (DRY RUN)\n")

    all_services = run_systemctl_list_units()

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            monitored = fetch_monitored_services(cur)

    already_monitored = []
    priority_candidates = []
    secondary_candidates = []
    ignored_count = 0

    for svc in all_services:
        name = svc["service_name"]

        if name in monitored:
            already_monitored.append(svc)
            continue

        classification = classify_service(svc)

        if classification == "priority":
            priority_candidates.append(svc)
        elif classification == "secondary":
            secondary_candidates.append(svc)
        else:
            ignored_count += 1

    print("already monitored:", len(already_monitored))
    for svc in sorted(already_monitored, key=lambda x: x["service_name"]):
        print(f"  {svc['service_name']} | active={svc['active']} | sub={svc['sub']}")

    print("\npriority candidates:", len(priority_candidates))
    for svc in sorted(priority_candidates, key=lambda x: x["service_name"]):
        print(f"  {svc['service_name']} | active={svc['active']} | sub={svc['sub']}")

    print("\nsecondary candidates:", len(secondary_candidates))
    for svc in sorted(secondary_candidates, key=lambda x: x["service_name"]):
        print(f"  {svc['service_name']} | active={svc['active']} | sub={svc['sub']}")

    print("\nignored:", ignored_count)


if __name__ == "__main__":
    main()
