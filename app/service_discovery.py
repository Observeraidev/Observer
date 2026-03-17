import subprocess
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL


def list_systemd_services():

    cmd = [
        "systemctl",
        "list-units",
        "--type=service",
        "--all",
        "--no-pager",
        "--no-legend"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    services = []

    for line in result.stdout.splitlines():

        parts = line.split()

        if not parts:
            continue

        name = parts[0]

        if name.endswith(".service"):
            services.append(name)

    return services


def fetch_monitored_services(cur):

    cur.execute("""
    SELECT service_name
    FROM service_monitors
    """)

    rows = cur.fetchall()

    return {r["service_name"] for r in rows}


def filter_noise(service):

    ignore = (
        "systemd",
        "dbus",
        "apt",
        "snap",
        "cron",
        "rsyslog"
    )

    for word in ignore:
        if word in service:
            return False

    return True


def main():

    print("\nSERVICE DISCOVERY (DRY RUN)\n")

    system_services = list_systemd_services()

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:

            monitored = fetch_monitored_services(cur)

    discovered = []
    already_monitored = []

    for s in system_services:

        if not filter_noise(s):
            continue

        if s in monitored:
            already_monitored.append(s)
        else:
            discovered.append(s)

    print("already monitored:", len(already_monitored))
    for s in already_monitored:
        print("  ", s)

    print("\nnew candidates:", len(discovered))
    for s in discovered:
        print("  ", s)


if __name__ == "__main__":
    main()
