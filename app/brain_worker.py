import os
import time
from datetime import datetime, timezone

from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
from app.core.brain_execute import execute_task, Conflict

DATABASE_URL = settings.DATABASE_URL
POLL_SECONDS = float(os.environ.get("BRAIN_WORKER_POLL", "2.0"))
METRICS_SECONDS = float(os.environ.get("BRAIN_WORKER_METRICS", "30.0"))


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[brain-worker] {ts} {msg}", flush=True)


def get_metrics():
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) AS pending_total
                FROM brain_tasks
                WHERE status IN ('PLANNED','PARTIAL')
                """
            )
            pending_total = int(cur.fetchone()["pending_total"])

            cur.execute(
                """
                SELECT count(DISTINCT t.task_id) AS blocked_total
                FROM brain_tasks t
                JOIN brain_ops o
                  ON o.org_id=t.org_id AND o.task_id=t.task_id
                WHERE t.status IN ('PLANNED','PARTIAL')
                  AND o.requires_approval = true
                  AND o.status IN ('PLANNED','EXECUTING')
                """
            )
            blocked_total = int(cur.fetchone()["blocked_total"])

            cur.execute(
                """
                SELECT extract(epoch FROM (now() - min(created_at)))::bigint AS oldest_age
                FROM brain_tasks
                WHERE status IN ('PLANNED','PARTIAL')
                """
            )
            row = cur.fetchone()
            oldest_age = row["oldest_age"]
            oldest_age = int(oldest_age) if oldest_age is not None else 0

            return pending_total, blocked_total, oldest_age


def pick_next_locked():
    """
    Claim at most 1 task atomically:
      - lock row with FOR UPDATE SKIP LOCKED
      - set status='EXECUTING' while holding lock
    This prevents double execution under concurrency.
    """
    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")

            cur.execute(
                """
                SELECT t.org_id, t.task_id
                FROM brain_tasks t
                WHERE t.status IN ('PLANNED','PARTIAL')
                  AND NOT EXISTS (
                    SELECT 1
                    FROM brain_ops o
                    WHERE o.org_id=t.org_id
                      AND o.task_id=t.task_id
                      AND o.requires_approval = true
                      AND o.status IN ('PLANNED','EXECUTING')
                  )
                ORDER BY t.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                cur.execute("ROLLBACK")
                return None

            org_id, task_id = row["org_id"], row["task_id"]

            cur.execute(
                """
                UPDATE brain_tasks
                SET status='EXECUTING'
                WHERE org_id=%s AND task_id=%s
                """,
                (org_id, task_id),
            )

            cur.execute("COMMIT")
            return org_id, task_id


def main():
    log("started")
    last_metrics = 0.0

    while True:
        now = time.time()

        if now - last_metrics >= METRICS_SECONDS:
            try:
                pending_total, blocked_total, oldest_age = get_metrics()
                log(f"metrics pending_total={pending_total} blocked_total={blocked_total} oldest_pending_age_sec={oldest_age}")
            except Exception as e:
                log(f"metrics_error {type(e).__name__}: {e}")
            last_metrics = now

        try:
            nxt = pick_next_locked()
            if not nxt:
                time.sleep(POLL_SECONDS)
                continue

            org_id, task_id = nxt
            try:
                log(f"execute org_id={org_id} task_id={task_id}")
                res = execute_task(org_id, task_id)
                log(f"done task_id={task_id} ok={res.get('ok')} status={res.get('status')}")
            except Conflict:
                pass
            except Exception as e:
                log(f"error task_id={task_id} {type(e).__name__}: {e}")
                try:
                    with connect(DATABASE_URL) as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE brain_tasks SET status='FAILED' WHERE org_id=%s AND task_id=%s",
                                (org_id, task_id),
                            )
                        conn.commit()
                except Exception:
                    pass
                time.sleep(1.0)

        except Exception as e:
            log(f"loop_error {type(e).__name__}: {e}")
            time.sleep(2.0)


if __name__ == "__main__":
    main()
