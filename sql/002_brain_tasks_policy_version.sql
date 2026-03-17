BEGIN;

ALTER TABLE brain_tasks
  ADD COLUMN IF NOT EXISTS policy_version TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS ix_brain_tasks_policy_version
  ON brain_tasks(org_id, policy_version);

COMMIT;
