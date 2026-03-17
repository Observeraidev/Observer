--
-- PostgreSQL database dump
--

\restrict TNU5qATYnbMV1p7fBWMjh6mxCVzV2riMHKySfIYAMSFjZvWEqeghc4MOvlJXTuF

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

--
-- Data for Name: action_registry; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.action_registry (id, created_at, action_name, description, risk_class, requires_approval, status) FROM stdin;
1	2026-03-11 11:34:34.640695+01	systemd.status	Read status of a systemd unit.	A	f	ACTIVE
2	2026-03-11 11:34:34.640695+01	systemd.restart	Restart a systemd unit as a governed action.	B	t	ACTIVE
3	2026-03-11 11:34:34.640695+01	fs.read	Read a file from the filesystem.	A	f	ACTIVE
4	2026-03-11 11:34:34.640695+01	fs.write	Write to a file in the filesystem.	B	t	ACTIVE
5	2026-03-11 11:34:34.640695+01	db.query	Run a read/query operation against the database.	A	f	ACTIVE
\.


--
-- Data for Name: incident_classes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.incident_classes (id, created_at, incident_code, description, severity, status) FROM stdin;
1	2026-03-11 09:22:04.417461+01	SERVICE_DOWN	Service is inactive or not responding	HIGH	ACTIVE
2	2026-03-11 09:52:54.216306+01	POLICY_BLOCKED	Action blocked by policy engine	MEDIUM	ACTIVE
\.


--
-- Data for Name: intent_action_map; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.intent_action_map (id, created_at, intent_name, action_name, status) FROM stdin;
1	2026-03-11 11:38:10.159429+01	inspect_project_state	fs.read	ACTIVE
2	2026-03-11 11:38:10.159429+01	inspect_service_health	systemd.status	ACTIVE
3	2026-03-11 11:38:10.159429+01	inspect_logs	fs.read	ACTIVE
4	2026-03-11 11:38:10.159429+01	restart_service	systemd.restart	ACTIVE
5	2026-03-11 11:38:10.159429+01	inspect_runtime_flags	db.query	ACTIVE
6	2026-03-16 08:44:31.394011+01	inspect_postmortems	fs.read	ACTIVE
7	2026-03-16 09:35:51.685468+01	inspect_metrics	fs.read	ACTIVE
8	2026-03-16 09:49:59.528456+01	restart_observer_api	systemd.restart	ACTIVE
9	2026-03-16 09:49:59.528456+01	restart_nginx	systemd.restart	ACTIVE
10	2026-03-16 09:49:59.528456+01	restart_observer_bridge	systemd.restart	ACTIVE
11	2026-03-16 09:49:59.528456+01	restart_memory_api	systemd.restart	ACTIVE
\.


--
-- Data for Name: intent_registry; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.intent_registry (id, created_at, intent_name, description, risk_class, requires_approval, status, canonical_text) FROM stdin;
1	2026-03-11 11:30:37.852274+01	inspect_project_state	Read and inspect current project/system state.	A	f	ACTIVE	inspect project state
2	2026-03-11 11:30:37.852274+01	inspect_service_health	Inspect health/status of a monitored service.	A	f	ACTIVE	check service health
3	2026-03-11 11:30:37.852274+01	inspect_logs	Read service or system logs for investigation.	A	f	ACTIVE	inspect logs
4	2026-03-11 11:30:37.852274+01	restart_service	Restart a systemd service as a governed recovery action.	B	t	ACTIVE	restart service
5	2026-03-11 11:30:37.852274+01	inspect_runtime_flags	Inspect runtime flags such as safe_mode and storm_risk.	A	f	ACTIVE	inspect runtime flags
9	2026-03-16 08:41:24.888793+01	inspect_postmortems	Read postmortems history from POSTMORTEMS.md	LOW	f	ACTIVE	inspect postmortems
10	2026-03-16 09:35:51.685468+01	inspect_metrics	Read system KPIs and metrics from METRICS.md	LOW	f	ACTIVE	inspect metrics
11	2026-03-16 09:49:59.528456+01	restart_observer_api	Restart observer-api.service	HIGH	t	ACTIVE	restart observer-api.service
12	2026-03-16 09:49:59.528456+01	restart_nginx	Restart nginx.service	HIGH	t	ACTIVE	restart nginx.service
13	2026-03-16 09:49:59.528456+01	restart_observer_bridge	Restart observer-bridge.service	HIGH	t	ACTIVE	restart observer-bridge.service
14	2026-03-16 09:49:59.528456+01	restart_memory_api	Restart memory-api.service	HIGH	t	ACTIVE	restart memory-api.service
\.


--
-- Data for Name: orgs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.orgs (id, name, created_at) FROM stdin;
org_dev	Dev Org	2026-02-22 10:36:32.432623+01
org_3b5680ead024	Test Cliente	2026-03-16 14:10:13.348979+01
org_5f830e742973	Test Cliente	2026-03-16 14:10:39.740043+01
\.


--
-- Data for Name: runtime_flags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.runtime_flags (key, value, updated_at) FROM stdin;
safe_mode	false	2026-03-16 16:41:33.951228
storm_risk	false	2026-03-16 16:41:33.951228
\.


--
-- Name: action_registry_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.action_registry_id_seq', 5, true);


--
-- Name: incident_classes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.incident_classes_id_seq', 2, true);


--
-- Name: intent_action_map_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.intent_action_map_id_seq', 11, true);


--
-- Name: intent_registry_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.intent_registry_id_seq', 14, true);


--
-- PostgreSQL database dump complete
--

\unrestrict TNU5qATYnbMV1p7fBWMjh6mxCVzV2riMHKySfIYAMSFjZvWEqeghc4MOvlJXTuF

