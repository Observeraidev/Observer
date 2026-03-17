--
-- PostgreSQL database dump
--

\restrict pgKa3xZV8kQsKyg5hJQ8hWelefhmTkdFynoG4nF660ITDPbkkU6Cj41u724xIQn

-- Dumped from database version 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: action_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_registry (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    action_name text NOT NULL,
    description text NOT NULL,
    risk_class text NOT NULL,
    requires_approval boolean DEFAULT false NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL
);


--
-- Name: action_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.action_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: action_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.action_registry_id_seq OWNED BY public.action_registry.id;


--
-- Name: agent_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_state (
    org_id text NOT NULL,
    agent_id text NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL,
    frozen_reason text,
    window_seconds integer DEFAULT 3600 NOT NULL,
    v_high integer DEFAULT 0 NOT NULL,
    v_critical integer DEFAULT 0 NOT NULL,
    window_started_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agents (
    id text NOT NULL,
    org_id text NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_keys (
    key_hash text NOT NULL,
    org_id text NOT NULL,
    label text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: approvals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approvals (
    org_id text NOT NULL,
    task_id text NOT NULL,
    op_id text NOT NULL,
    op_hash text NOT NULL,
    user_id text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    approved_at timestamp with time zone,
    status text DEFAULT 'PENDING'::text NOT NULL,
    risk_level text,
    approved_by text,
    created_at timestamp with time zone DEFAULT now(),
    used_at timestamp with time zone,
    used_by text,
    consumed_by text,
    consumed_at timestamp with time zone,
    rejected_at timestamp with time zone,
    rejected_by text
);


--
-- Name: brain_exec_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brain_exec_log (
    id bigint NOT NULL,
    org_id text NOT NULL,
    task_id text NOT NULL,
    exec_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    policy_version text NOT NULL,
    plan_hash text NOT NULL,
    status text NOT NULL,
    error text,
    result_json jsonb,
    evidence_json jsonb,
    needs_verify boolean DEFAULT false,
    verified_at timestamp without time zone,
    verification_evidence jsonb
);


--
-- Name: brain_exec_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.brain_exec_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: brain_exec_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.brain_exec_log_id_seq OWNED BY public.brain_exec_log.id;


--
-- Name: brain_ops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brain_ops (
    org_id text NOT NULL,
    task_id text NOT NULL,
    op_id text NOT NULL,
    op_type text NOT NULL,
    op_hash text NOT NULL,
    risk_level text NOT NULL,
    requires_approval boolean NOT NULL,
    status text DEFAULT 'PLANNED'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: brain_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brain_tasks (
    org_id text NOT NULL,
    task_id text NOT NULL,
    created_by text NOT NULL,
    status text DEFAULT 'PLANNED'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    policy_version text DEFAULT ''::text NOT NULL,
    plan_hash text DEFAULT ''::text NOT NULL
);


--
-- Name: idempotency; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.idempotency (
    org_id text NOT NULL,
    key text NOT NULL,
    request_hash text NOT NULL,
    response_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: improvement_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.improvement_registry (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    pattern_type text,
    operation text,
    recommended_action text,
    reason text,
    risk text,
    status text DEFAULT 'new'::text,
    improvement_class text,
    approval_task_id text,
    approval_op_id text,
    approval_op_hash text
);


--
-- Name: improvement_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.improvement_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: improvement_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.improvement_registry_id_seq OWNED BY public.improvement_registry.id;


--
-- Name: incident_classes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_classes (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    incident_code text NOT NULL,
    description text NOT NULL,
    severity text NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL
);


--
-- Name: incident_classes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incident_classes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incident_classes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incident_classes_id_seq OWNED BY public.incident_classes.id;


--
-- Name: incident_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_evidence (
    incident_evidence_id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_id uuid NOT NULL,
    evidence_type text NOT NULL,
    evidence_ref text NOT NULL,
    summary text,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: incident_improvements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_improvements (
    relation_id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_id uuid NOT NULL,
    improvement_id integer NOT NULL,
    relation_type text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: incident_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_registry (
    incident_id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_key text NOT NULL,
    incident_class text NOT NULL,
    title text NOT NULL,
    description text,
    source_type text NOT NULL,
    source_ref text,
    entity_type text NOT NULL,
    entity_name text NOT NULL,
    severity text NOT NULL,
    status text DEFAULT 'OPEN'::text NOT NULL,
    first_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp without time zone DEFAULT now() NOT NULL,
    occurrence_count integer DEFAULT 1 NOT NULL,
    last_evidence_type text,
    last_evidence_ref text,
    resolution_type text,
    resolution_notes text,
    resolved_at timestamp without time zone,
    linked_improvement_count integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: incident_registry_v0_backup_20260311; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_registry_v0_backup_20260311 (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    incident_code text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    severity text NOT NULL,
    status text DEFAULT 'OPEN'::text NOT NULL,
    opened_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    reason text,
    resolution text
);


--
-- Name: incident_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incident_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incident_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incident_registry_id_seq OWNED BY public.incident_registry_v0_backup_20260311.id;


--
-- Name: intent_action_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intent_action_map (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    intent_name text NOT NULL,
    action_name text NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL
);


--
-- Name: intent_action_map_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.intent_action_map_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: intent_action_map_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.intent_action_map_id_seq OWNED BY public.intent_action_map.id;


--
-- Name: intent_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intent_registry (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    intent_name text NOT NULL,
    description text NOT NULL,
    risk_class text NOT NULL,
    requires_approval boolean DEFAULT false NOT NULL,
    status text DEFAULT 'ACTIVE'::text NOT NULL,
    canonical_text text
);


--
-- Name: intent_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.intent_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: intent_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.intent_registry_id_seq OWNED BY public.intent_registry.id;


--
-- Name: log_chain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_chain (
    id bigint NOT NULL,
    org_id text NOT NULL,
    agent_id text NOT NULL,
    record_json jsonb NOT NULL,
    prev_hash text,
    hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: log_chain_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_chain_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_chain_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_chain_id_seq OWNED BY public.log_chain.id;


--
-- Name: orgs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orgs (
    id text NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policies (
    id text NOT NULL,
    org_id text NOT NULL,
    policy_version text NOT NULL,
    policy_hash text NOT NULL,
    policy_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: policies_old; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policies_old (
    id text NOT NULL,
    org_id text NOT NULL,
    policy_version text NOT NULL,
    policy_hash text NOT NULL,
    policy_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: policy_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policy_versions (
    policy_version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    policy_json jsonb NOT NULL,
    notes text DEFAULT ''::text NOT NULL
);


--
-- Name: runtime_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.runtime_flags (
    key text NOT NULL,
    value text,
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: service_action_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_action_log (
    id integer NOT NULL,
    service text,
    action_type text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: service_action_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_action_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_action_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_action_log_id_seq OWNED BY public.service_action_log.id;


--
-- Name: service_criticality; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_criticality (
    service_name text NOT NULL,
    criticality text NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: service_monitor_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_monitor_log (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    service_name text,
    source_monitor_id integer,
    observed_via text,
    result_status text,
    task_id text,
    notes text
);


--
-- Name: service_monitor_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_monitor_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_monitor_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_monitor_log_id_seq OWNED BY public.service_monitor_log.id;


--
-- Name: service_monitors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_monitors (
    id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    service_name text,
    source_improvement_id integer,
    status text DEFAULT 'active'::text
);


--
-- Name: service_monitors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_monitors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_monitors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_monitors_id_seq OWNED BY public.service_monitors.id;


--
-- Name: service_restart_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_restart_log (
    id integer NOT NULL,
    service text,
    restarted_at timestamp without time zone DEFAULT now()
);


--
-- Name: service_restart_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_restart_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_restart_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_restart_log_id_seq OWNED BY public.service_restart_log.id;


--
-- Name: structural_proposals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.structural_proposals (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    proposal_id text NOT NULL,
    proposal_type text NOT NULL,
    title text NOT NULL,
    reason text,
    payload jsonb NOT NULL,
    risk_class text NOT NULL,
    status text DEFAULT 'NEW'::text NOT NULL,
    proposed_by text NOT NULL,
    source text NOT NULL,
    requires_approval boolean DEFAULT false NOT NULL,
    approval_task_id text,
    approval_op_id text,
    approval_op_hash text,
    applied_task_id text,
    applied_op_id text,
    reviewed_at timestamp with time zone,
    applied_at timestamp with time zone,
    result text,
    last_error text
);


--
-- Name: structural_proposals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.structural_proposals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: structural_proposals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.structural_proposals_id_seq OWNED BY public.structural_proposals.id;


--
-- Name: action_registry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_registry ALTER COLUMN id SET DEFAULT nextval('public.action_registry_id_seq'::regclass);


--
-- Name: brain_exec_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_exec_log ALTER COLUMN id SET DEFAULT nextval('public.brain_exec_log_id_seq'::regclass);


--
-- Name: improvement_registry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.improvement_registry ALTER COLUMN id SET DEFAULT nextval('public.improvement_registry_id_seq'::regclass);


--
-- Name: incident_classes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_classes ALTER COLUMN id SET DEFAULT nextval('public.incident_classes_id_seq'::regclass);


--
-- Name: incident_registry_v0_backup_20260311 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_registry_v0_backup_20260311 ALTER COLUMN id SET DEFAULT nextval('public.incident_registry_id_seq'::regclass);


--
-- Name: intent_action_map id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intent_action_map ALTER COLUMN id SET DEFAULT nextval('public.intent_action_map_id_seq'::regclass);


--
-- Name: intent_registry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intent_registry ALTER COLUMN id SET DEFAULT nextval('public.intent_registry_id_seq'::regclass);


--
-- Name: log_chain id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_chain ALTER COLUMN id SET DEFAULT nextval('public.log_chain_id_seq'::regclass);


--
-- Name: service_action_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_action_log ALTER COLUMN id SET DEFAULT nextval('public.service_action_log_id_seq'::regclass);


--
-- Name: service_monitor_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_monitor_log ALTER COLUMN id SET DEFAULT nextval('public.service_monitor_log_id_seq'::regclass);


--
-- Name: service_monitors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_monitors ALTER COLUMN id SET DEFAULT nextval('public.service_monitors_id_seq'::regclass);


--
-- Name: service_restart_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_restart_log ALTER COLUMN id SET DEFAULT nextval('public.service_restart_log_id_seq'::regclass);


--
-- Name: structural_proposals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.structural_proposals ALTER COLUMN id SET DEFAULT nextval('public.structural_proposals_id_seq'::regclass);


--
-- Name: action_registry action_registry_action_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_registry
    ADD CONSTRAINT action_registry_action_name_key UNIQUE (action_name);


--
-- Name: action_registry action_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_registry
    ADD CONSTRAINT action_registry_pkey PRIMARY KEY (id);


--
-- Name: agent_state agent_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_state
    ADD CONSTRAINT agent_state_pkey PRIMARY KEY (org_id, agent_id);


--
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (id);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (key_hash);


--
-- Name: approvals approvals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_pkey PRIMARY KEY (org_id, task_id, op_id);


--
-- Name: brain_exec_log brain_exec_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_exec_log
    ADD CONSTRAINT brain_exec_log_pkey PRIMARY KEY (id);


--
-- Name: brain_ops brain_ops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_ops
    ADD CONSTRAINT brain_ops_pkey PRIMARY KEY (org_id, task_id, op_id);


--
-- Name: brain_tasks brain_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_tasks
    ADD CONSTRAINT brain_tasks_pkey PRIMARY KEY (org_id, task_id);


--
-- Name: idempotency idempotency_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.idempotency
    ADD CONSTRAINT idempotency_pkey PRIMARY KEY (org_id, key);


--
-- Name: improvement_registry improvement_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.improvement_registry
    ADD CONSTRAINT improvement_registry_pkey PRIMARY KEY (id);


--
-- Name: incident_classes incident_classes_incident_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_classes
    ADD CONSTRAINT incident_classes_incident_code_key UNIQUE (incident_code);


--
-- Name: incident_classes incident_classes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_classes
    ADD CONSTRAINT incident_classes_pkey PRIMARY KEY (id);


--
-- Name: incident_evidence incident_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_evidence
    ADD CONSTRAINT incident_evidence_pkey PRIMARY KEY (incident_evidence_id);


--
-- Name: incident_improvements incident_improvements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_improvements
    ADD CONSTRAINT incident_improvements_pkey PRIMARY KEY (relation_id);


--
-- Name: incident_registry_v0_backup_20260311 incident_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_registry_v0_backup_20260311
    ADD CONSTRAINT incident_registry_pkey PRIMARY KEY (id);


--
-- Name: incident_registry incident_registry_pkey1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_registry
    ADD CONSTRAINT incident_registry_pkey1 PRIMARY KEY (incident_id);


--
-- Name: intent_action_map intent_action_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intent_action_map
    ADD CONSTRAINT intent_action_map_pkey PRIMARY KEY (id);


--
-- Name: intent_registry intent_registry_intent_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intent_registry
    ADD CONSTRAINT intent_registry_intent_name_key UNIQUE (intent_name);


--
-- Name: intent_registry intent_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intent_registry
    ADD CONSTRAINT intent_registry_pkey PRIMARY KEY (id);


--
-- Name: log_chain log_chain_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_chain
    ADD CONSTRAINT log_chain_pkey PRIMARY KEY (id);


--
-- Name: orgs orgs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orgs
    ADD CONSTRAINT orgs_pkey PRIMARY KEY (id);


--
-- Name: policies_old policies_org_id_id_policy_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies_old
    ADD CONSTRAINT policies_org_id_id_policy_version_key UNIQUE (org_id, id, policy_version);


--
-- Name: policies_old policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies_old
    ADD CONSTRAINT policies_pkey PRIMARY KEY (id);


--
-- Name: policies policies_pkey1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_pkey1 PRIMARY KEY (org_id, id, policy_version);


--
-- Name: policy_versions policy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_pkey PRIMARY KEY (policy_version);


--
-- Name: runtime_flags runtime_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.runtime_flags
    ADD CONSTRAINT runtime_flags_pkey PRIMARY KEY (key);


--
-- Name: service_action_log service_action_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_action_log
    ADD CONSTRAINT service_action_log_pkey PRIMARY KEY (id);


--
-- Name: service_criticality service_criticality_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_criticality
    ADD CONSTRAINT service_criticality_pkey PRIMARY KEY (service_name);


--
-- Name: service_monitor_log service_monitor_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_monitor_log
    ADD CONSTRAINT service_monitor_log_pkey PRIMARY KEY (id);


--
-- Name: service_monitors service_monitors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_monitors
    ADD CONSTRAINT service_monitors_pkey PRIMARY KEY (id);


--
-- Name: service_restart_log service_restart_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_restart_log
    ADD CONSTRAINT service_restart_log_pkey PRIMARY KEY (id);


--
-- Name: structural_proposals structural_proposals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.structural_proposals
    ADD CONSTRAINT structural_proposals_pkey PRIMARY KEY (id);


--
-- Name: structural_proposals structural_proposals_proposal_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.structural_proposals
    ADD CONSTRAINT structural_proposals_proposal_id_key UNIQUE (proposal_id);


--
-- Name: brain_ops_task_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX brain_ops_task_idx ON public.brain_ops USING btree (org_id, task_id);


--
-- Name: idx_incident_evidence_v1_incident; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_evidence_v1_incident ON public.incident_evidence USING btree (incident_id);


--
-- Name: idx_incident_evidence_v1_type_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_evidence_v1_type_ref ON public.incident_evidence USING btree (evidence_type, evidence_ref);


--
-- Name: idx_incident_improvements_v1_improvement; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_improvements_v1_improvement ON public.incident_improvements USING btree (improvement_id);


--
-- Name: idx_incident_improvements_v1_incident; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_improvements_v1_incident ON public.incident_improvements USING btree (incident_id);


--
-- Name: idx_incident_registry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_registry_status ON public.incident_registry_v0_backup_20260311 USING btree (status);


--
-- Name: idx_incident_registry_v1_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_registry_v1_class ON public.incident_registry USING btree (incident_class);


--
-- Name: idx_incident_registry_v1_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_registry_v1_entity ON public.incident_registry USING btree (entity_type, entity_name);


--
-- Name: idx_incident_registry_v1_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_registry_v1_key ON public.incident_registry USING btree (incident_key);


--
-- Name: idx_incident_registry_v1_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incident_registry_v1_status ON public.incident_registry USING btree (status);


--
-- Name: idx_log_chain_org_agent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_log_chain_org_agent ON public.log_chain USING btree (org_id, agent_id);


--
-- Name: ix_action_registry_risk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_registry_risk ON public.action_registry USING btree (risk_class);


--
-- Name: ix_action_registry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_action_registry_status ON public.action_registry USING btree (status);


--
-- Name: ix_brain_exec_task; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_brain_exec_task ON public.brain_exec_log USING btree (org_id, task_id, created_at DESC);


--
-- Name: ix_brain_tasks_planhash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_brain_tasks_planhash ON public.brain_tasks USING btree (org_id, task_id, plan_hash);


--
-- Name: ix_brain_tasks_policy_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_brain_tasks_policy_version ON public.brain_tasks USING btree (org_id, policy_version);


--
-- Name: ix_incident_classes_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incident_classes_severity ON public.incident_classes USING btree (severity);


--
-- Name: ix_incident_classes_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incident_classes_status ON public.incident_classes USING btree (status);


--
-- Name: ix_incident_registry_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incident_registry_code ON public.incident_registry_v0_backup_20260311 USING btree (incident_code);


--
-- Name: ix_incident_registry_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incident_registry_resource ON public.incident_registry_v0_backup_20260311 USING btree (resource_type, resource_id);


--
-- Name: ix_incident_registry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incident_registry_status ON public.incident_registry_v0_backup_20260311 USING btree (status);


--
-- Name: ix_intent_action_map_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_intent_action_map_action ON public.intent_action_map USING btree (action_name);


--
-- Name: ix_intent_action_map_intent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_intent_action_map_intent ON public.intent_action_map USING btree (intent_name);


--
-- Name: ix_intent_registry_risk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_intent_registry_risk ON public.intent_registry USING btree (risk_class);


--
-- Name: ix_intent_registry_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_intent_registry_status ON public.intent_registry USING btree (status);


--
-- Name: ix_structural_proposals_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_structural_proposals_created_at ON public.structural_proposals USING btree (created_at);


--
-- Name: ix_structural_proposals_risk_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_structural_proposals_risk_status ON public.structural_proposals USING btree (risk_class, status);


--
-- Name: ix_structural_proposals_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_structural_proposals_status ON public.structural_proposals USING btree (status);


--
-- Name: ix_structural_proposals_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_structural_proposals_type ON public.structural_proposals USING btree (proposal_type);


--
-- Name: ux_brain_exec_idempotency; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_brain_exec_idempotency ON public.brain_exec_log USING btree (org_id, task_id, plan_hash, policy_version);


--
-- Name: ux_incident_registry_v1_active_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_incident_registry_v1_active_key ON public.incident_registry USING btree (incident_key) WHERE (status = ANY (ARRAY['OPEN'::text, 'MONITORING'::text]));


--
-- Name: ux_service_monitors_service_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_service_monitors_service_name ON public.service_monitors USING btree (service_name);


--
-- Name: agent_state agent_state_agent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_state
    ADD CONSTRAINT agent_state_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES public.agents(id);


--
-- Name: agent_state agent_state_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_state
    ADD CONSTRAINT agent_state_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: agents agents_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agents
    ADD CONSTRAINT agents_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: api_keys api_keys_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: approvals approvals_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approvals
    ADD CONSTRAINT approvals_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: brain_ops brain_ops_org_id_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_ops
    ADD CONSTRAINT brain_ops_org_id_task_id_fkey FOREIGN KEY (org_id, task_id) REFERENCES public.brain_tasks(org_id, task_id);


--
-- Name: brain_tasks brain_tasks_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brain_tasks
    ADD CONSTRAINT brain_tasks_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: idempotency idempotency_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.idempotency
    ADD CONSTRAINT idempotency_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: incident_evidence incident_evidence_incident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_evidence
    ADD CONSTRAINT incident_evidence_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incident_registry(incident_id) ON DELETE CASCADE;


--
-- Name: incident_improvements incident_improvements_incident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_improvements
    ADD CONSTRAINT incident_improvements_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incident_registry(incident_id) ON DELETE CASCADE;


--
-- Name: log_chain log_chain_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_chain
    ADD CONSTRAINT log_chain_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: policies_old policies_org_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies_old
    ADD CONSTRAINT policies_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- Name: policies policies_org_id_fkey1; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_org_id_fkey1 FOREIGN KEY (org_id) REFERENCES public.orgs(id);


--
-- PostgreSQL database dump complete
--

\unrestrict pgKa3xZV8kQsKyg5hJQ8hWelefhmTkdFynoG4nF660ITDPbkkU6Cj41u724xIQn

