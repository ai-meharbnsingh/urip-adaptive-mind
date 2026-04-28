# URIP-Adverb — Delivery Architecture Options

**Status:** Decision pending. This document captures three viable models. The chosen model determines Phase 4 (Production Deployment) scope.

---

## TL;DR Comparison

| Aspect | Option 1: Pure SaaS | Option 2: On-Prem Licensed | **Option 3: Hybrid-SaaS** ⭐ |
|---|---|---|---|
| Cloud-side | Everything (UI + logic + data) | Nothing | **UI + logic + metadata only** |
| Client-side | Nothing | Everything | **Docker agent + local DB** |
| Sensitive data location | Our cloud | Their cloud | **Their network only** |
| IP protection | High (closed source) | Low (they have full source) | **High (only agent ships)** |
| CISO sales pitch | "We host" | "Your servers, your code" | **"Your data never leaves your network"** |
| Update model | Continuous, auto | Pull when ready | **Cloud auto + agent on demand** |
| Operational burden on us | High (24/7 ops) | Zero | **Medium (cloud only)** |
| Industry parallels | Sprinto, Drata | Some on-prem GRC | **CrowdStrike Falcon, Tenable Nessus, Splunk Forwarder** |
| Recommended for Adverb | Possible | Possible | **Best fit — see Section 4** |

---

## Option 1: Pure SaaS Managed

We host everything (URIP backend + Compliance backend + frontend + DBs) on our infrastructure (Vercel + Railway + Neon). Adverb logs into `adverb.urip.io`. All sensitive data sits in our cloud.

**Pros:**
- Fastest time-to-value (we run it, they consume it)
- Continuous updates with zero client involvement
- Standard SaaS commercial model

**Cons:**
- Client's vulnerability data, compliance evidence, audit logs all live in OUR infrastructure
- CISOs at regulated buyers (PepsiCo, J&J procurement) push back — "your cloud is in our threat model"
- We are in their audit boundary
- If our cloud is breached, attacker harvests every customer's risk register

**What we've built that supports this:** Everything. This is the default architecture our code targets.

**Additional work for Phase 4:** None beyond the existing deployment plan.

---

## Option 2: On-Premise Licensed Software

Adverb gets the full source + licensed binary. Deploys on their own servers. Operates it themselves. We provide on-demand customization.

**Pros:**
- Maximum data sovereignty
- Zero operational burden on us
- Client never worried about vendor cloud breach

**Cons:**
- Client has the source — IP protection minimal
- They control upgrade cadence (we lose ability to push fixes)
- Their ops team must run our software (not always realistic)
- Hard to monetize ongoing — they pay once, then minimal revenue

**What we've built that supports this:** Everything. Codebase is dockerizable as a single deployment.

**Additional work for Phase 4:**
- Production-grade docker-compose / Helm chart
- Installation runbook for Adverb's IT team
- Licensing key validation
- Update / patch distribution channel

---

## Option 3: Hybrid-SaaS (Cloud Portal + On-Premise Agent) ⭐ RECOMMENDED

This is the model used by **CrowdStrike (Falcon Sensor), Tenable (Nessus Agent), Splunk (Forwarder)**. Industry-proven for security products.

### Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SEMANTIC GRAVITY CLOUD (us)                        │
│                                                                       │
│   ┌─────────────────────┐      ┌──────────────────────────────────┐ │
│   │  Frontend Portal    │      │   Cloud Backend (URIP + Compl.)  │ │
│   │  - Dashboard UI     │◄────►│   - Master Intelligence Engine   │ │
│   │  - Login / RBAC     │      │   - EPSS / KEV / MITRE feeds     │ │
│   │  - Reports          │      │   - Compliance scoring engine    │ │
│   │                     │      │   - Tenant + license mgmt        │ │
│   └─────────────────────┘      │   - Aggregate metadata storage   │ │
│                                 └──────────┬───────────────────────┘ │
│                                            │                          │
│                                            │ HTTPS + signed payloads  │
│                                            │ (encrypted reporter)     │
└────────────────────────────────────────────┼──────────────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    ADVERB CUSTOMER NETWORK                              │
│                                                                         │
│   ┌────────────────────────────────────────────────────────────────┐  │
│   │             URIP Agent (Docker container)                       │  │
│   │                                                                 │  │
│   │   ┌──────────────────┐    ┌────────────────────────────────┐ │  │
│   │   │  API Connectors  │    │  Normalizer + Local DB Manager │ │  │
│   │   │  (Tenable,       │    │  (raw findings → URIP schema   │ │  │
│   │   │   SentinelOne,   │───►│   → write to local Postgres)   │ │  │
│   │   │   Entra, etc.)   │    │                                 │ │  │
│   │   └──────────────────┘    └─────────┬───────────────────────┘ │  │
│   │                                     │                            │  │
│   │   ┌─────────────────────────────────▼──────────────────────┐ │  │
│   │   │  Encrypted Reporter (sends ONLY scores + counts)        │ │  │
│   │   │  - Tenant-A has 8.2 risk score, 15 criticals            │ │  │
│   │   │  - SOC 2 compliance: 87%, 3 controls failing            │ │  │
│   │   │  - DOES NOT send: IP addresses, hostnames, usernames    │ │  │
│   │   └─────────────────────────────────────────────────────────┘ │  │
│   │                                                                 │  │
│   │   ┌─────────────────────────────────────────────────────────┐ │  │
│   │   │  Drill-Down Tunnel (on-demand, secure)                   │ │  │
│   │   │  - When user clicks "View Details" in cloud UI           │ │  │
│   │   │  - Cloud backend signs a request, agent fulfills locally │ │  │
│   │   │  - Raw data returned in browser session, never persisted │ │  │
│   │   │    in cloud                                               │ │  │
│   │   └─────────────────────────────────────────────────────────┘ │  │
│   └────────────────────────────────────────────────────────────────┘  │
│                                  │                                      │
│                                  ▼                                      │
│   ┌────────────────────────────────────────────────────────────────┐  │
│   │  Local Postgres (Adverb's DB or container-managed)              │  │
│   │  - Full risk records with IPs, hostnames, usernames             │  │
│   │  - Compliance evidence files                                    │  │
│   │  - Audit logs                                                   │  │
│   │  - Vendor docs                                                  │  │
│   │  STAYS ON ADVERB NETWORK FOREVER                                │  │
│   └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### What stays in the cloud

- **Frontend UI** (the polished dashboard)
- **Master intelligence engine** — EPSS/KEV/MITRE/OTX live feeds, CVE→APT mapping logic
- **Compliance framework data** — SOC 2/ISO/GDPR/etc. control libraries (these are public reference data anyway)
- **Scoring engine** — the formula that turns raw signals into risk scores
- **Tenant + license management** — who paid, what modules enabled
- **Aggregate metadata only** — "Adverb has 8.2 score, 15 criticals, 87% SOC 2 compliance"
- **Auditor portal** — auditor logs into our cloud, sees framework status; raw evidence streamed via drill-down tunnel

### What ships as the Docker agent

- **API connectors** (Tenable, SentinelOne, Zscaler, Netskope, MS Entra, ManageEngine, GTB, Burp, CloudSEK)
- **Normalizer** — maps each tool's raw output to URIP universal schema
- **Local DB manager** — writes detailed records to Adverb's Postgres
- **Encrypted reporter** — sends summary metadata to cloud over signed HTTPS
- **Drill-down responder** — fulfills authenticated cloud requests for raw data, returns to user's browser session only

### What stays on Adverb's network forever

- Every IP address, hostname, username, file path discovered by their tools
- All compliance evidence files (screenshots, logs, configs)
- Every audit log entry
- Vendor documents (DPAs, SOC 2 reports, etc.)
- Local Postgres with full records

### Pros (the sales pitch)

> *"Your sensitive vulnerability data — IP addresses, hostnames, usernames — never leaves your network. It stays in your local Postgres, controlled by your IT team. Our cloud only receives the summary scores you need to see on the dashboard. Even if our cloud is hacked, the attacker finds zero information about your internal infrastructure. The only thing they'd see is a number — '8.2'. That tells them nothing about your network."*

This **closes deals with regulated buyers**. PepsiCo / J&J / Reliance procurement security questionnaires usually have a question like *"does the vendor store our sensitive data in their cloud?"* — with this model the answer is **NO**.

### Pros (engineering)

- IP protection — agent ships with connectors but cloud-side intelligence (scoring formula, compliance logic) stays in our cloud
- Updates: cloud changes are immediate; agent only updates when we add new connectors
- Reduced cloud DB load — we don't store every vulnerability record from every customer
- Compliance audit boundary is smaller — our cloud only has metadata, not customer-sensitive data

### Cons / honest limits

- More complex architecture than pure SaaS — agent installer, version compatibility matrix, drill-down tunnel security
- "Drill-down tunnel" requires Adverb's network to allow inbound connections from our cloud (typically via reverse-tunnel — agent dials home, cloud requests data over the open tunnel)
- If agent goes offline, cloud dashboard becomes stale (can't refresh metadata or do drill-down)
- More moving parts to support

### What we've built that already supports this

| Component | Status | Where it lives in this model |
|---|---|---|
| Connector framework (`connectors/base/`) | ✅ Built (C3) | **Goes in Docker agent** |
| Normalize methods on each connector | ✅ Built (C3) | **Goes in Docker agent** |
| Per-connector implementations (Tenable, SentinelOne) | ✅ Built (Kimi-2) | **Goes in Docker agent** |
| Adverb simulator | ✅ Built (C3) | **Goes in Docker agent (for demo mode)** |
| Tenant credential vault (Fernet-encrypted) | ✅ Built (C3) | **Goes in Docker agent (encrypts API keys locally)** |
| URIP backend (risks, scoring, dashboard) | ✅ Built | **Stays in cloud** |
| EPSS/KEV/MITRE/OTX live feed integration | ✅ Built | **Stays in cloud** |
| Compliance backend (frameworks, controls, evidence, etc.) | ✅ Built | **Mostly cloud; evidence files stored on agent's local DB** |
| Auditor portal | ✅ Built (Opus-C) | **Stays in cloud** |
| Frontend admin UIs + theming | ✅ Built (Opus-B) | **Stays in cloud** |

**The hybrid split aligns naturally with our codebase.** Connectors are already a separate package. Backend is already split into URIP + Compliance services. Frontend is already separate.

### Additional work needed for Hybrid-SaaS (NEW)

| # | Task | Scope | Difficulty |
|---|---|---|---|
| H1 | Package `connectors/` + scheduler + local DB manager as Docker image | Dockerfile + entrypoint + config | Medium |
| H2 | Encrypted reporter — agent → cloud HTTPS POST with signed payloads (tenant licence key for auth) | New `connectors/reporter/` module | Medium |
| H3 | Cloud ingest endpoint — receives metadata reports, updates aggregate tables | New `backend/routers/agent_ingest.py` | Easy |
| H4 | Agent registration / license activation flow | Cloud admin UI + agent first-boot config | Easy-Medium |
| H5 | Drill-down tunnel — secure on-demand fetch of raw data from agent | Reverse-tunnel via WebSocket OR queued request | Medium-High |
| H6 | Aggregate metadata schema (separate from raw schema) — counts, scores, NOT raw records | New tables in cloud DB; raw tables stay in agent's local DB | Medium |
| H7 | Agent health / heartbeat — cloud knows which agents are online | Periodic heartbeat endpoint | Easy |
| H8 | Versioning + compatibility matrix between agent and cloud | Semver + API version negotiation | Easy |
| H9 | Agent upgrade path — push new connector version | Container registry + agent self-update OR manual re-deploy | Medium |
| H10 | Documentation: agent install runbook for Adverb's IT team | Markdown + screenshots | Easy |

**Estimated delta vs pure SaaS:** ~15-20% additional engineering. Most plumbing is sock-puppet wiring around existing code.

---

## 4. Why Hybrid-SaaS is the Best Fit for Adverb (Addverb Technologies)

Per market research:

1. **Addverb is Reliance-owned warehouse robotics** selling to PepsiCo, J&J, Reliance, Pharma — buyers who run formal vendor security questionnaires
2. **They are NOT a security SaaS vendor** — they are a customer with a security questionnaire treadmill
3. **PepsiCo / J&J procurement will ask:** *"Where does your security tooling vendor store your sensitive data?"*
4. **With Hybrid-SaaS the answer is:** *"Nowhere — it stays on our network. The vendor only sees summary scores."* — This is a procurement-clearing answer
5. **CISO comfort:** even if our cloud is breached, Addverb's actual vulnerability inventory is safe
6. **Operational reality:** Addverb has a 1000-person company with an existing IT team who can run a Docker container; they don't want to be a SOC outsourcer relationship

**Recommendation: pitch Hybrid-SaaS as the default. Have Pure SaaS as a fallback if Adverb wants zero infrastructure.**

---

## 5. Identity Risk Logic — Carry-Forward From Royal Enfield

This is one of the highest-value pieces of logic from the original RE engagement that Adverb directly inherits.

### The pattern

```
RE source (CyberArk PAM)  ─┐
                           │
                           ▼
                ┌──────────────────────────┐
                │   URIP Identity Module    │
                │   (Universal Logic)       │
                │                           │
                │   - Severity Mapping      │
                │   - Asset Tier Multiplier │
                │   - Auto-Assignment       │
                │   - SLA Timer             │
                │   - Remediation Workflow  │
                └──────────────┬───────────┘
                               │
Adverb source (MS Entra ID) ───┘
```

The **same risk-engine logic** applies regardless of which identity provider raised the alert. We swap the input adapter (CyberArk → Microsoft Entra Graph API), and the entire downstream workflow (severity → asset multiplier → assignment → SLA → remediation) is **identical**.

### What Adverb specifically gets from this carry-forward

| RE-derived capability | Adverb implementation |
|---|---|
| Suspicious login event handling | MS Entra `Risky Sign-Ins` API → URIP Identity Module |
| Credential stuffing / brute force detection | Entra reports 50 failed login attempts → URIP raises HIGH risk |
| Impossible travel detection | Entra `Atypical Travel` risk event → URIP correlates with asset criticality |
| MFA fatigue / bypass attack response | Entra `MFA Fatigue` signal → URIP creates ticket in ManageEngine SDP within SLA |
| Asset criticality multiplier | Same logic as RE — risky login on Tenant A's "Financial SharePoint" tier scores Critical 9.0+; same login on "Canteen Menu" stays Low |

### What's already built

- URIP Identity Module risk handling (existing — Track A multi-tenant version)
- Asset criticality service (Opus-A — now per-tenant configurable)
- Risk severity mapping (existing)
- SLA service (existing)
- Remediation tracking (existing — C1 wired multi-tenant)

### What needs to be built per this model

- **MS Entra connector** (planned: Phase 2A.7) — pulls Entra Risky Sign-Ins API
- **Entra-specific risk type mapping** — translates Entra `riskEventType` enum (atypicalTravel, anonymizedIPAddress, maliciousIPAddress, suspiciousAPITraffic, leakedCredentials, mfaFatigue, etc.) into URIP severity scores
- **Auto-ticket-to-ManageEngine flow** — when a Critical Entra risk lands, URIP auto-creates a ticket in ManageEngine SDP with the IAM team as owner

This is **a connector-level addition**, not a new architectural concept. The URIP Identity Module reuses the same engine RE got.

---

## 6. Decision Matrix Summary

| Decision | Default | Open question for client meeting |
|---|---|---|
| Delivery model | **Hybrid-SaaS** ⭐ | Confirm Adverb is comfortable running a Docker container in their network |
| If Adverb refuses Docker | Fall back to Pure SaaS | Acknowledge their data lives in our cloud |
| If Adverb wants source code | Open Option 2 (On-Prem License) — separate commercial | Different pricing model |
| Identity Risk source | **MS Entra ID** | Confirm Adverb uses Entra (most likely yes given Microsoft 365 stack from blueprint) |
| Identity ticket destination | **ManageEngine SDP** | Confirm SDP is operational and writeable via API |

---

## 7. Scaling & Operations (How We Host 50-100 Tenants Without Drowning)

The Hybrid-SaaS cloud portal must scale as we onboard more tenants. This section captures the operational architecture so it is explicit, not assumed.

### 7.1 Architecture for Scale

```
                ┌────────────────────────┐
                │  Tenant browsers        │
                │  (Adverb / RE / etc.)   │
                └──────────┬──────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  Load Balancer            │
              │  (AWS ALB / Cloud Run /   │
              │   Vercel edge)            │
              └──────────┬───────────────┘
                         │
              ┌──────────┴────────────┐
              │ Frontend Pool          │
              │ (static SPA on CDN)    │
              └──────────┬────────────┘
                         │
              ┌──────────┴────────────┐
              │ Backend API Pool        │
              │ (auto-scaling N         │
              │  containers)            │
              │  - URIP backend (8000)  │
              │  - Compliance (8001)    │
              └──────────┬────────────┘
                         │
                         │   ┌────────────────────────────────┐
                         ├──►│ Redis (event bus + task queue)│
                         │   └────────────────────────────────┘
                         │
                         │   ┌────────────────────────────────┐
                         ├──►│ Celery / RQ workers            │
                         │   │ (heavy connector pulls,        │
                         │   │  evidence captures, scoring    │
                         │   │  recalculation, scheduled jobs)│
                         │   └────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Postgres cluster      │
              │ (master + read replica│
              │  for analytics)       │
              └──────────────────────┘

              ┌──────────────────────┐
              │ Object storage (S3 / │
              │ R2) — evidence files,│
              │ exports, screenshots │
              └──────────────────────┘
```

### 7.2 Concrete Choices

| Concern | Choice | Why |
|---|---|---|
| **Load balancing** | Cloud Run / Vercel edge / AWS ALB | Built-in to managed platforms; we don't run our own LB |
| **Container orchestration** | Cloud Run (default) → ECS/Kubernetes (when scale demands) | Cloud Run handles auto-scale, health checks, zero-config; move to ECS/K8s only when we exceed Cloud Run's per-region limits |
| **Auto-scaling target** | 70% CPU on backend pool; queue depth on workers | Industry default; tunable per service |
| **Database** | Managed Postgres (Neon / RDS / Cloud SQL) | They handle backups, patches, failover, scaling disk |
| **Task queue** | Celery + Redis (or RQ + Redis for simpler ops) | Connector pulls are the heaviest workload; never run them on the API thread |
| **Event bus** | Redis pub/sub (already built — `shared/events/redis_client.py`) | Cross-service eventing (URIP risk → Compliance control re-eval) |
| **Object storage** | S3 / R2 / GCS | Evidence files, audit exports, screenshots — never on container disk |
| **Stateless backend** | Enforced by code review | Every container is fungible; restart = no data loss |
| **Secrets** | Provider secret manager (AWS Secrets Manager / GCP Secret Manager) | NOT in env vars in production |

### 7.3 Multi-Tenant Database Isolation Strategy

We chose **Option 1: Shared DB with `tenant_id` column** for the initial deployment.

| Strategy | Pros | Cons | Used for |
|---|---|---|---|
| **Option 1 — Shared DB, tenant_id column** ⭐ | Cheap, fast to provision new tenants, queries are simple, one schema migration covers all tenants | Coding mistake = cross-tenant leak (we mitigate with `apply_tenant_filter` helper + tests) | **Default for all tenants** |
| **Option 2 — DB per tenant** | Maximum isolation, easier per-tenant backup/restore, easier per-tenant data deletion (GDPR DSR) | Expensive at scale, schema migrations multiply, harder to query across tenants for analytics | **Available as enterprise tier** for clients who require it (regulated banking, government) |

**Implementation status:**
- Option 1 — ✅ Built. Track A added `tenant_id` to every domain table; `apply_tenant_filter` helper enforces filtering; integration tests prove zero cross-tenant leakage. Backend-Gaps worker fixed 3 critical leakage bugs found by Security Review.
- Option 2 — Not yet. Would require a tenant routing layer that maps `tenant_id` from JWT to a DB connection pool. Future work for enterprise contracts.

### 7.4 Aggregated Scoring History — What the Cloud DB Holds

When the on-prem Docker agent is online, it pushes raw findings to its **local DB**. When it goes offline, the cloud dashboard would be useless if the cloud held nothing. So the cloud DB always holds:

| Data category | Where | Why |
|---|---|---|
| **Tenant profile** (name, slug, branding, modules, settings) | Cloud | Frontend needs this every page load |
| **Users + roles + auth state** | Cloud | Login flow |
| **License / module subscription state** | Cloud | Module gate |
| **Aggregate metadata sent by agent** | Cloud | Dashboard KPIs (total risks, criticals, trend) |
| **Compliance score history** (`ComplianceScoreSnapshot`) | Cloud | 90-day trend visible even when agent offline |
| **Risk score history** (planned: `RiskScoreSnapshot` per tenant per day) | Cloud | Dashboard chart still works during agent downtime |
| **Audit log of cloud-side actions** | Cloud | Login attempts, role changes, license actions |
| **Connector health snapshots** | Cloud | Admin sees agent status even if agent is dead |
| **Threat intel reference data** (EPSS, KEV, MITRE, OTX) | Cloud | Pulled live from public APIs by cloud, distributed to agents |
| **Compliance framework reference data** (SOC 2, ISO 27001, etc. control libraries) | Cloud | These are public reference data; agents don't need to host them |
| **Raw vulnerability records** (with IPs, hostnames, usernames) | **On-prem agent's local DB** | Sensitive — never leaves Adverb's network |
| **Evidence files** (screenshots, configs, logs) | **On-prem agent's local DB / file storage** | Sensitive — accessed via drill-down tunnel only |
| **Policy content + acknowledgments** | **On-prem agent's local DB** | May contain employee names + signatures |

**The contract:** if the agent dies, the dashboard still loads — it just shows the last-known scores + a banner saying "agent offline since X". Drill-down is unavailable until agent reconnects, but the high-level posture remains visible.

### 7.5 Newbie-Friendly Hosting Path (Recommended Start)

Don't try to build global infra on day one. Use managed services:

| Layer | Provider option (pick one) |
|---|---|
| Backend API hosting | **Cloud Run (GCP)** OR Vercel (frontend) + Railway/Render (backend) OR AWS App Runner |
| Database | **Neon Postgres** (already in use for original URIP) OR AWS RDS OR Supabase |
| Redis | **Upstash Redis** (serverless, scales to zero) OR Redis Cloud OR Memorystore |
| Object storage | **Cloudflare R2** (no egress fees) OR AWS S3 OR GCS |
| CDN / static frontend | **Vercel** (already in use) OR Cloudflare Pages OR Netlify |
| Background workers | **Cloud Run jobs** OR Render background workers OR ECS scheduled tasks |
| Container registry | GHCR (free with GitHub) OR ECR OR GCR |
| Monitoring | **Sentry** (errors) + **Better Stack** / Grafana Cloud (metrics + logs) |
| Secrets | **Doppler** OR AWS Secrets Manager OR Google Secret Manager |

**Estimated minimum viable cost** (10 tenants, modest traffic): ~$200-400/month total. Scales linearly with tenant count and connector activity.

### 7.6 What's Built vs What Phase 4 Adds

| Requirement | Status | Notes |
|---|---|---|
| Stateless backend | ✅ | Backend reads/writes only DB and object storage; no container-local files |
| Containerization | ✅ | docker-compose.yml exists; Dockerfile ships per service |
| Multi-tenant code (Option 1) | ✅ | tenant_id everywhere + apply_tenant_filter |
| Redis event bus | ✅ | shared/events/redis_client.py |
| Object storage abstraction | ✅ | EvidenceService uses pluggable storage backend |
| Cloud-side aggregate snapshots | 🟡 | ComplianceScoreSnapshot built; RiskScoreSnapshot pattern needed for Hybrid-SaaS dashboard fidelity |
| Async task queue (Celery / RQ workers) | 🔴 | Phase 4 deliverable — pulls from Redis, runs heavy connector jobs |
| Auto-scaling configuration | 🔴 | Phase 4 — Cloud Run / ECS YAML / Helm chart |
| Production secret management | 🔴 | Phase 4 — Doppler / Secrets Manager integration |
| Multi-region failover | 🔴 | Future — only when client base demands |
| DB-per-tenant tier (Option 2) | 🔴 | Future — enterprise contracts only |

### 7.7 Operational Realism Check

For the first 5–10 tenants you can run this on:
- 1 Cloud Run service for URIP backend (auto-scales 1-3 instances)
- 1 Cloud Run service for Compliance backend (auto-scales 1-3 instances)
- 1 Cloud Run job pool for Celery workers (scales by queue depth)
- 1 Neon Postgres (free tier covers it)
- 1 Upstash Redis (free tier covers it)
- 1 Cloudflare R2 bucket (basically free at this scale)
- Vercel for frontend (free tier covers it)

**You do not need a DevOps team to start.** You need ~6 hours to wire up the managed services and a CI pipeline. Everything beyond that is "scale problems we'll solve when we have those scale problems."

---

## 8. Implementation Plan Impact

This document does NOT modify the existing implementation plan; it captures architecture options that affect Phase 4 (Production Deployment).

**If Hybrid-SaaS is chosen:** Add tasks H1–H10 (Section 3 above) + the Phase 4 items in Section 7.6 to Phase 4. Estimated 15-20% additional engineering effort vs pure SaaS deployment. Phases 1, 2A, 2B, and 3 are unchanged — they ship the same code regardless of delivery model.

**Decision needed in client review meeting (Section 11 of ADVERB_BLUEPRINT.md).**

---

## 9. Status — Phase 4 Implementation

| Component | Status | Location |
|---|---|---|
| Docker agent (Dockerfile + entrypoint + scheduler + reporter + heartbeat + drilldown responder) | ✅ Implemented | `agent/` |
| Cloud ingest API (`/api/agent-ingest/*`) | ✅ Implemented | `backend/routers/agent_ingest.py` |
| Cloud-side models (AgentRegistration, ConnectorHealthSummary, DrilldownRequest) | ✅ Implemented | `backend/models/agent_ingest.py` |
| Risk score summary cache (existing — re-used for agent metadata) | ✅ Re-used | `backend/models/risk_snapshot.py` |
| Tenant.license_key column | ✅ Added | `backend/models/tenant.py` + migration `0006_agent_ingest_hybrid_saas` |
| HMAC + anti-replay over `{ts}.{path}.{body}` | ✅ Both sides | `backend/routers/agent_ingest.py` + `agent/reporter.py` |
| Defence-in-depth: agent refuses to send payloads with raw-finding keys | ✅ Implemented | `agent/reporter.py::_assert_no_raw_findings` |
| Defence-in-depth: cloud rejects metadata payloads with raw-finding keys | ✅ Implemented | `backend/routers/agent_ingest.py::_contains_raw_finding_keys` |
| One-time drill-down tokens (60 s TTL, invalidated after fulfilment, response wiped after SSE forward) | ✅ Implemented | `backend/routers/agent_ingest.py` |
| docker-compose for client IT team + install README | ✅ Implemented | `agent/docker-compose.agent.yml` + `agent/README.md` |
| Tests | ✅ 51 passing | `tests/test_agent/` + `tests/test_agent_ingest/` |

**Outstanding for Phase 4 close-out** (out of scope for this work unit):
- Per-tenant license-key UI in the cloud admin portal (today: SQL-issued)
- Container registry publish + agent self-update path
- Multi-region cloud failover
