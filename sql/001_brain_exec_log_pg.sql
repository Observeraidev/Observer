BEGIN;

CREATE TABLE IF NOT EXISTS brain_exec_log (
  id            BIGSERIAL PRIMARY KEY,
  org_id        TEXT NOT NULL,
  task_id       TEXT NOT NULL,
  exec_id       TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at    TIMESTAMPTZ,
  finished_at   TIMESTAMPTZ,

  policy_version TEXT NOT NULL,
  plan_hash      TEXT NOT NULL,

  status        TEXT NOT NULL, -- running|success|failed
  error         TEXT,
  result_json   JSONB,
  evidence_json JSONB
);

-- Idempotencia dura:
CREATE UNIQUE INDEX IF NOT EXISTS ux_brain_exec_idempotency
ON brain_exec_log(org_id, task_id, plan_hash, policy_version);

CREATE INDEX IF NOT EXISTS ix_brain_exec_task
ON brain_exec_log(org_id, task_id, created_at DESC);

COMMIT;
