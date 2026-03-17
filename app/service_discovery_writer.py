import subprocess
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


PRIORITY_EXACT = {
    "observer-control.service",
    "observer-bridge.service",
    "memory-api.service",
    "nginx.service",
    "postgresql.service",
    "postgresql@14-main.service",
}


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


def fetch_existing_monitors(cur):
    cur.execute("""
    SELECT service_name
    FROM service_monitors
    """)
    return {r["service_name"] for r in cur.fetchall()}


def is_safe_priority_candidate(service):
    name = service["service_name"]
    load = service["load"]
    active = service["active"]

    if name not in PRIORITY_EXACT:
        return False

    if load != "loaded":
        return False

    if active != "active":
        return False

    return True


def insert_monitor(cur, service_name):
    cur.execute("""
    INSERT INTO service_monitors
    (
        service_name,
        status
    )
    VALUES (%s, %s)
    """, (service_name, "active"))


def main():
    created = 0
    suppressed = 0

    print("\nSERVICE DISCOVERY WRITER\n")

    all_services = run_systemctl_list_units()

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            existing = fetch_existing_monitors(cur)

            for svc in all_services:
                name = svc["service_name"]

                if not is_safe_priority_candidate(svc):
                    continue

                if name in existing:
                    suppressed += 1
                    print(name, "| already monitored")
                    continue

                insert_monitor(cur, name)
                existing.add(name)
                created += 1
                print(name, "| monitor created")

            conn.commit()

    print("\ncreated:", created)
    print("suppressed:", suppressed)


if __name__ == "__main__":
    main()
