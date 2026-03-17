BEGIN;

ALTER TABLE policies RENAME TO policies_old;

CREATE TABLE policies (
  id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  policy_version TEXT NOT NULL,
  policy_hash TEXT NOT NULL,
  policy_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, id, policy_version)
);

INSERT INTO policies(id, org_id, policy_version, policy_hash, policy_json, created_at)
SELECT id, org_id, policy_version, policy_hash, policy_json, created_at
FROM policies_old;

COMMIT;
