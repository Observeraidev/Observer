BEGIN;

CREATE TABLE IF NOT EXISTS orgs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
  key_hash TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  label TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policies (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  policy_version TEXT NOT NULL,
  policy_hash TEXT NOT NULL,
  policy_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(org_id, id, policy_version)
);

CREATE TABLE IF NOT EXISTS agent_state (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  agent_id TEXT NOT NULL REFERENCES agents(id),
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  frozen_reason TEXT,
  window_seconds INTEGER NOT NULL DEFAULT 3600,
  v_high INTEGER NOT NULL DEFAULT 0,
  v_critical INTEGER NOT NULL DEFAULT 0,
  window_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, agent_id)
);

CREATE TABLE IF NOT EXISTS idempotency (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(org_id, key)
);

CREATE TABLE IF NOT EXISTS log_chain (
  id BIGSERIAL PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  agent_id TEXT NOT NULL,
  record_json JSONB NOT NULL,
  prev_hash TEXT,
  hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_log_chain_org_agent ON log_chain(org_id, agent_id);

CREATE TABLE IF NOT EXISTS approvals (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  task_id TEXT NOT NULL,
  op_id TEXT NOT NULL,
  op_hash TEXT NOT NULL,
  user_id TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  approved_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'PENDING',
  PRIMARY KEY (org_id, task_id, op_id)
);

COMMIT;
