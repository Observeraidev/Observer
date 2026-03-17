BEGIN;

CREATE TABLE IF NOT EXISTS policy_versions (
  policy_version TEXT PRIMARY KEY,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  policy_json    JSONB NOT NULL,
  notes          TEXT NOT NULL DEFAULT ''
);

COMMIT;
