# URIP-Adverb — Implementation Plan

**Companion to:** `ADVERB_BLUEPRINT.md` (scope) — this document covers **execution sequence**.
**Scope of this plan:** Everything in the blueprint **except CloudSEK build**. CloudSEK ships only as an API connector (Option A); native CloudSEK feature replication is explicitly out of scope.
**Compliance Module (Sprinto-equivalent):** built natively as a **standalone sub-project** inside `compliance/`, integrated cleanly with URIP core. See Section 5 + Section 8 + folder scaffold in `compliance/`.

> **Note on time:** No timelines, week estimates, or effort numbers in this document (per project rule). Order, dependencies, and gating criteria are captured. Commercials handled separately.

---

## 0. Reading Guide

| Label | Meaning |
|---|---|
| ✅ **LIVE** | Already exists in current URIP code |
| 🟡 **SIMULATED / PARTIAL** | Stub or partial implementation exists |
| 🔴 **TO BUILD** | New build in this phase |

Phases are ordered by dependency. A phase cannot start until its **gate criteria** (listed at the end of each phase) are met.

---

## 1. Architecture Overview

URIP-Adverb is a **two-service architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Tenant Frontend                          │
│         (URIP UI + lazy-loaded Compliance UI routes)             │
└────────────────────┬───────────────────────┬────────────────────┘
                     │                       │
                     │ REST + JWT            │ REST + JWT
                     ▼                       ▼
        ┌────────────────────┐    ┌──────────────────────┐
        │  URIP Core         │    │  Compliance Service  │
        │  (port 8000)       │◄──►│  (port 8001)         │
        │                    │    │                      │
        │  Risk register     │    │  Frameworks          │
        │  Scoring engine    │    │  Controls            │
        │  Connectors        │    │  Evidence            │
        │  Workflow          │    │  Policies            │
        │  Audit log         │    │  Access reviews      │
        │  Tenant mgmt       │    │  Vendor risk         │
        └─────────┬──────────┘    │  Auditor portal      │
                  │               │  Compliance scoring  │
                  │               └──────────┬───────────┘
                  │                          │
                  ▼                          ▼
         ┌──────────────────┐     ┌──────────────────┐
         │  URIP DB         │     │  Compliance DB   │
         │  (Postgres)      │     │  (Postgres)      │
         └──────────────────┘     └──────────────────┘

         ┌────────────────────────────────────────────┐
         │  Shared services                            │
         │  - JWT issuer (URIP)                       │
         │  - Object storage (S3-compatible)          │
         │  - Event bus (Redis pub/sub)               │
         │  - Tenant registry (URIP, source of truth) │
         └────────────────────────────────────────────┘
```

**Key architecture decisions:**

| Decision | Rationale |
|---|---|
| Compliance is a **separate FastAPI service**, not a router inside URIP | Standalone deployability — Compliance can be sold and deployed alone as a Sprinto-replacement product without URIP |
| Compliance has **its own database** | True isolation; can run on its own Postgres instance for standalone deployments |
| **Shared JWT** issued by URIP (or by a shared auth service when standalone) | Single sign-on across both services. Compliance verifies tokens; doesn't issue them when integrated |
| **Event bus (Redis pub/sub)** between services | URIP risk events trigger Compliance control re-evaluation asynchronously without tight coupling |
| **Frontend integration** via lazy-loaded routes (micro-frontend pattern) | Compliance UI can be embedded in URIP shell OR served standalone |
| **Tenant context** propagated via JWT claims | Both services know which tenant the request belongs to from the token; no separate tenant lookup |

---

## 2. Target Folder Structure (End State)

```
project_33a/
├── backend/                          # URIP core (existing, refactored in Phase 1)
├── frontend/                         # URIP shell + tenant-themed UI
├── compliance/                       # NEW — Sprinto-equivalent standalone sub-project
│   ├── README.md                     # Standalone vs integrated, quick start
│   ├── ARCHITECTURE.md               # Service architecture details
│   ├── backend/                      # Compliance FastAPI service
│   │   ├── pyproject.toml
│   │   ├── compliance_backend/
│   │   │   ├── main.py
│   │   │   ├── models/
│   │   │   ├── routers/
│   │   │   ├── services/
│   │   │   ├── seeders/              # Framework data (SOC 2, ISO 27001, etc.)
│   │   │   └── connectors/           # Compliance-specific connectors (LMS, BGV)
│   │   └── tests/
│   ├── frontend/                     # Compliance UI (standalone Next.js app)
│   ├── alembic/                      # Compliance DB migrations
│   ├── docker-compose.standalone.yml # Run compliance alone (Sprinto-replacement mode)
│   └── docs/                         # Compliance product docs, framework refs
├── shared/                           # NEW — shared between URIP + Compliance
│   ├── auth/                         # JWT verification helpers
│   ├── tenant/                       # Tenant context propagation
│   └── events/                       # Event bus contracts (URIP ↔ Compliance)
├── connectors/                       # NEW — Phase 1.6 connector framework + Phase 2A connectors
│   ├── base/                         # Connector interface
│   ├── tenable/
│   ├── sentinelone/
│   ├── zscaler/
│   ├── netskope/
│   ├── manageengine_sdp/
│   ├── manageengine_ec/
│   ├── manageengine_mdm/
│   ├── ms_entra/
│   ├── ms_collab/                    # SharePoint + OneDrive + Teams
│   ├── burpsuite/
│   ├── gtb/
│   └── cloudsek/                     # API connector only (Option A)
├── alembic/                          # URIP core DB migrations (existing)
├── docker-compose.yml                # Orchestrates URIP + Compliance + Postgres + Redis
├── ADVERB_BLUEPRINT.md               # Scope (existing)
├── ADVERB_IMPLEMENTATION_PLAN.md     # This document
└── BLUEPRINT.md                      # Original URIP/RE blueprint (kept for reference)
```

---

## 3. Phase 1 — URIP Core Productization

**Goal:** Refactor existing URIP from single-tenant (Royal Enfield-hardcoded) to multi-tenant, module-pickable, white-labelable. Adverb tenant lands here with simulated data.

### 3.1 Tasks

| # | Task | Files / Areas | Status |
|---|---|---|---|
| P1.1 | Add `tenant_id` foreign key to every domain table; filter all queries by tenant | `backend/models/*.py`, every router | 🔴 |
| P1.2 | Tenant model + onboarding API (`POST /tenants`) + admin UI for provisioning | New `backend/models/tenant.py`, new `backend/routers/tenants.py` | 🔴 |
| P1.3 | Module subscription registry — per-tenant flags for which modules are enabled | New `backend/models/subscription.py`, frontend route guards | 🔴 |
| P1.4 | Tenant-configurable asset taxonomy — replace RE-hardcoded keywords with per-tenant config | `backend/services/asset_criticality_service.py`, `backend/config/tier_keywords.json` | 🔴 |
| P1.5 | White-label theming layer — logo, colors, app name per tenant | Frontend theming layer | 🔴 |
| P1.6 | Connector framework abstraction — extract connector interface, move from `simulator.py` dispatch to plugin registry | New `connectors/base/`, refactor `backend/simulator.py` | 🔴 |
| P1.7 | Module-level RBAC — roles scoped to specific modules | `backend/middleware/auth.py`, role definitions | 🔴 |
| P1.8 | Adverb-flavored simulator mode — synthetic data labeled with Adverb's source names | `backend/simulator.py` config | 🔴 |
| P1.9 | Per-tenant scoring weights UI — expose existing scoring config per-tenant | `backend/routers/settings.py`, frontend | 🔴 |
| P1.10 | Subscription pricing module — track paid vs trial features per tenant | New table + routes | 🔴 |
| P1.11 | **Compliance schema foundation** — create empty tables (`frameworks`, `controls`, `control_evidence`, `policies`, `policy_acknowledgments`, `access_reviews`, `vendors`, `incidents`, `assets`) so Phase 2B Compliance Service has a stable data layer to read from when integrated | New `backend/models/compliance.py`, new alembic migration | 🔴 |
| P1.12 | Shared auth helpers — extract JWT issue/verify into `shared/auth/` so Compliance Service can verify URIP tokens | New `shared/auth/` package | 🔴 |
| P1.13 | Tenant context propagation — JWT claims carry `tenant_id`; middleware extracts and binds to request context | `backend/middleware/auth.py`, new `shared/tenant/` package | 🔴 |
| P1.14 | Event bus scaffold — Redis pub/sub setup with topic conventions (`urip.risk.created`, `urip.risk.resolved`, etc.) | New `shared/events/` package, `docker-compose.yml` adds Redis | 🔴 |

### 3.2 Phase 1 Gate (must pass before Phase 2 starts)

- ✅ Adverb tenant can be provisioned via API
- ✅ Adverb-branded login + dashboard renders with Adverb logo/colors
- ✅ Adverb user sees only Adverb data (no RE data leakage)
- ✅ Module subscription UI works — disabling a module hides UI routes
- ✅ Adverb-flavored simulator generates synthetic data labeled as Adverb's tools
- ✅ EPSS + KEV + MITRE + OTX enrichment continues to work for Adverb tenant
- ✅ Compliance schema tables exist (empty, ready for Phase 2B)
- ✅ Shared auth + tenant context + event bus scaffold ready for Compliance Service to plug in

---

## 4. Phase 2A — URIP Adverb Live Connectors (11 sources + CloudSEK API)

**Goal:** Replace Adverb-flavored simulator data with real API integrations to Adverb's actual tool stack.

### 4.1 Connector Framework (built in P1.6, used here)

Each connector implements:
- `authenticate(tenant_credentials) -> session`
- `fetch_findings(since: timestamp) -> list[Finding]`
- `normalize(raw_finding) -> URIPRiskRecord`
- `health_check() -> ConnectorHealth`

### 4.2 Wave A — Highest Risk-Volume Connectors

| # | Connector | Purpose | Status |
|---|---|---|---|
| P2A.1 | Tenable Vulnerability Manager | CVE inventory + CVSS + exploit availability | 🔴 |
| P2A.2 | SentinelOne (Singularity) | Active threats, agent health, vulnerable endpoints | 🔴 |

**Wave A gate:** Adverb dashboard shows real Tenable + SentinelOne data; Adverb risk register populated from real sources for first time.

### 4.3 Wave B — Network / Cloud

| # | Connector | Purpose | Status |
|---|---|---|---|
| P2A.3 | Zscaler ZIA / ZTA / CASB | Web threats, shadow SaaS, blocked URLs | 🔴 |
| P2A.4 | Netskope | Cloud app risk, DLP violations | 🔴 |

**Wave B gate:** External attack surface visibility complete in URIP.

### 4.4 Wave C — ITSM / Remediation Loop

| # | Connector | Purpose | Status |
|---|---|---|---|
| P2A.5 | ManageEngine Service Desk Plus | Ticket creation + bidirectional sync | 🔴 |
| P2A.6 | ManageEngine Endpoint Central | Patch status + missing patches | 🔴 |

**Wave C gate:** Risk → ticket → resolution loop closes inside URIP.

### 4.5 Wave D — Identity + Collaboration

| # | Connector | Purpose | Status |
|---|---|---|---|
| P2A.7 | Microsoft Entra ID | Risky sign-ins, MFA bypass, conditional access violations | 🔴 |
| P2A.8 | SharePoint + OneDrive + Teams | Anonymous link sharing, external sharing audit, sensitive label violations | 🔴 |

**Wave D gate:** Identity + data exposure visibility complete. Also unblocks Compliance Module Access Review (P2B.6).

### 4.6 Wave E — Mobile + DLP + DAST + External

| # | Connector | Purpose | Status |
|---|---|---|---|
| P2A.9 | ManageEngine MDM | Jailbroken devices, non-compliant mobile | 🔴 |
| P2A.10 | GTB Endpoint Protector | DLP policy violations, USB block events | 🔴 |
| P2A.11 | Burpsuite (Enterprise API) | Web app scan findings | 🔴 (gated on Adverb confirming Burp Enterprise license) |
| P2A.12 | CloudSEK (Option A — API connector only) | Dark web alerts, brand abuse, leaked credentials | 🔴 |

**Wave E gate:** All 12 connectors live; simulator can be disabled for Adverb tenant.

### 4.7 Phase 2A Overall Gate

- ✅ All 12 connectors return real data on schedule
- ✅ Adverb credentials provisioning workflow (admin uploads keys, validates, encrypts at rest)
- ✅ Adverb dashboard fully populated with live data
- ✅ Simulator switched off for Adverb tenant (kept for demo / new-tenant onboarding flow)
- ✅ Connector health monitoring page (admin sees connector status, last successful pull, errors)

---

## 5. Phase 2B — Compliance Module (Standalone Sub-Project)

**Goal:** Build Sprinto-equivalent compliance + audit-readiness platform. **Lives in `compliance/` folder as a standalone service.** Can be deployed alone (Sprinto-replacement product) OR integrated with URIP (Compliance Module subscription).

**Runs in parallel with Phase 2A** — both depend only on Phase 1 productization.

### 5.1 Service Scaffold

| # | Task | Location | Status |
|---|---|---|---|
| P2B.1.1 | Create `compliance/` folder structure (per Section 2) | `compliance/` | 🔴 |
| P2B.1.2 | FastAPI app skeleton on port 8001 with health endpoint | `compliance/backend/compliance_backend/main.py` | 🔴 |
| P2B.1.3 | Compliance Postgres database setup (separate from URIP DB); alembic init | `compliance/alembic/`, `docker-compose.yml` | 🔴 |
| P2B.1.4 | JWT verification middleware using shared auth (`shared/auth/`) | `compliance/backend/compliance_backend/middleware/auth.py` | 🔴 |
| P2B.1.5 | Tenant context middleware (extracts tenant_id from JWT) | `compliance/backend/compliance_backend/middleware/tenant.py` | 🔴 |
| P2B.1.6 | Event bus subscriber — listen for `urip.risk.created` to re-evaluate controls | `compliance/backend/compliance_backend/events/risk_listener.py` | 🔴 |
| P2B.1.7 | Object storage client setup (S3-compatible) for evidence files | `compliance/backend/compliance_backend/services/storage.py` | 🔴 |
| P2B.1.8 | Standalone docker-compose for "Sprinto-replacement" deployment mode | `compliance/docker-compose.standalone.yml` | 🔴 |
| P2B.1.9 | Compliance frontend scaffold (Next.js standalone OR module within URIP shell) | `compliance/frontend/` | 🔴 |

**Scaffold gate:** Compliance Service starts standalone; health check returns OK; can verify a URIP-issued JWT.

### 5.2 Framework + Control Data Model

| # | Task | Status |
|---|---|---|
| P2B.2.1 | Tables: `frameworks`, `framework_versions`, `controls`, `control_categories`, `framework_control_mapping` | 🔴 |
| P2B.2.2 | Cross-framework control mapping logic (one control satisfies multiple frameworks) | 🔴 |
| P2B.2.3 | Framework seeder for **SOC 2** (Trust Services Criteria 2017 + 2022) | 🔴 |
| P2B.2.4 | Framework seeder for **ISO 27001:2022** (Annex A controls) | 🔴 |
| P2B.2.5 | Framework seeder for **GDPR** (Articles + recitals as control surface) | 🔴 |
| P2B.2.6 | Framework seeder for **HIPAA** (Security Rule safeguards) | 🔴 |
| P2B.2.7 | Framework seeder for **PCI DSS v4.0** | 🔴 |
| P2B.2.8 | Framework seeder for **India DPDP Act 2023** | 🔴 |
| P2B.2.9 | Framework seeder for **NIST CSF 2.0** | 🔴 |
| P2B.2.10 | Framework registry API — list available frameworks per tenant | 🔴 |
| P2B.2.11 | Framework selection per tenant (which frameworks they're targeting) | 🔴 |

### 5.3 Control Monitoring Engine

| # | Task | Status |
|---|---|---|
| P2B.3.1 | Control rule plugin architecture — each control has a `check()` function | 🔴 |
| P2B.3.2 | Scheduled execution scheduler (cron-like) for control checks | 🔴 |
| P2B.3.3 | Pass / fail / inconclusive state tracking per control per tenant per check run | 🔴 |
| P2B.3.4 | Control failure → event emit on shared bus (`compliance.control.failed`) | 🔴 |
| P2B.3.5 | Built-in control check library (initial set — covers ~50 most common controls across frameworks) | 🔴 |
| P2B.3.6 | Custom control authoring UI (tenant admin can add tenant-specific controls) | 🔴 |

### 5.4 Evidence Automation

| # | Task | Status |
|---|---|---|
| P2B.4.1 | Evidence model: `control_evidence` table with type (screenshot, config, log, ticket), URI to object storage, control_id, framework_id, audit_period | 🔴 |
| P2B.4.2 | Auto-collection from connectors — when a control check runs, capture relevant evidence from the underlying source tool | 🔴 |
| P2B.4.3 | Manual evidence upload UI (drag-drop, with metadata tagging) | 🔴 |
| P2B.4.4 | Evidence search + filter by control / framework / period / type | 🔴 |
| P2B.4.5 | Evidence retention policy (keep N audit periods, auto-archive older) | 🔴 |
| P2B.4.6 | Evidence export bundle (zip per framework per audit period for auditor handoff) | 🔴 |

### 5.5 Policy Management

| # | Task | Status |
|---|---|---|
| P2B.5.1 | Policy model: `policies` (versioned), `policy_versions`, `policy_acknowledgments` | 🔴 |
| P2B.5.2 | Policy template library (seeded): Information Security Policy, Acceptable Use, BCP/DR, Incident Response, Access Control, Change Management, Vendor Management, Data Classification, Privacy Policy | 🔴 |
| P2B.5.3 | Policy versioning + change-tracking UI | 🔴 |
| P2B.5.4 | E-sign acknowledgment workflow (employee logs in, reads policy, signs) | 🔴 |
| P2B.5.5 | Reminder workflow for unacknowledged policies | 🔴 |
| P2B.5.6 | Policy expiry alerts (annual review reminders) | 🔴 |
| P2B.5.7 | Acknowledgment status report (admin sees who has / hasn't signed) | 🔴 |

### 5.6 Access Reviews

**Depends on:** P2A.7 (MS Entra connector) and P2A.10 (any other identity provider connectors)

| # | Task | Status |
|---|---|---|
| P2B.6.1 | Pull current user-role assignments from MS Entra (via URIP connector) | 🔴 |
| P2B.6.2 | Access review campaign creator (define scope, reviewers, due date) | 🔴 |
| P2B.6.3 | Reviewer notification + UI to approve/revoke per user | 🔴 |
| P2B.6.4 | Decision capture + audit trail | 🔴 |
| P2B.6.5 | Auto-revocation workflow (push revoke decisions back to MS Entra via API) | 🔴 |
| P2B.6.6 | Quarterly / annual scheduling | 🔴 |
| P2B.6.7 | Auditor-ready access review report | 🔴 |

### 5.7 Vendor / Third-Party Risk

| # | Task | Status |
|---|---|---|
| P2B.7.1 | Vendor model: `vendors`, `vendor_questionnaires`, `vendor_responses`, `vendor_documents` | 🔴 |
| P2B.7.2 | Vendor inventory UI with criticality classification | 🔴 |
| P2B.7.3 | Questionnaire builder (templates: SOC 2 vendor, GDPR DPA, security baseline) | 🔴 |
| P2B.7.4 | Vendor self-service portal (vendor logs in, fills questionnaire, uploads docs) | 🔴 |
| P2B.7.5 | Document tracking (DPA, BAA, ISO certs) with expiry alerts | 🔴 |
| P2B.7.6 | Vendor risk score (derived from questionnaire + documents + criticality) | 🔴 |
| P2B.7.7 | Annual review reminders | 🔴 |

### 5.8 Incident Lifecycle Module

| # | Task | Status |
|---|---|---|
| P2B.8.1 | Incident model extending URIP's risks with: detection_time, containment_time, eradication_time, recovery_time, RCA, lessons_learned | 🔴 |
| P2B.8.2 | Incident lifecycle workflow (Detection → Triage → Containment → Eradication → Recovery → Lessons) | 🔴 |
| P2B.8.3 | SLA tracking per phase | 🔴 |
| P2B.8.4 | Post-incident review template + scheduling | 🔴 |
| P2B.8.5 | Incident metrics dashboard (MTTR, MTTD, incident volume by severity) | 🔴 |

### 5.9 Asset Inventory Module

**Extends URIP's existing asset criticality service.**

| # | Task | Status |
|---|---|---|
| P2B.9.1 | Asset model: `assets` with type, owner, classification, location, lifecycle_state, business_criticality | 🔴 |
| P2B.9.2 | Manual asset entry UI | 🔴 |
| P2B.9.3 | Auto-discovery import from MS Entra, ManageEngine Endpoint Central, cloud APIs (URIP connectors) | 🔴 |
| P2B.9.4 | Asset → control linkage (which controls apply to which asset types) | 🔴 |
| P2B.9.5 | Asset tagging + search | 🔴 |
| P2B.9.6 | Asset lifecycle tracking (procurement → in-use → decommissioning) | 🔴 |

### 5.10 Auditor Portal

| # | Task | Status |
|---|---|---|
| P2B.10.1 | Auditor role definition (read-only across compliance data, scoped to specific framework + audit period) | 🔴 |
| P2B.10.2 | Auditor invitation flow (tenant admin invites auditor by email) | 🔴 |
| P2B.10.3 | Auditor login + dashboard (filtered by framework + audit period) | 🔴 |
| P2B.10.4 | Control list view with evidence drill-down | 🔴 |
| P2B.10.5 | Policy + acknowledgment view | 🔴 |
| P2B.10.6 | Evidence request workflow (auditor requests additional evidence; tenant admin uploads) | 🔴 |
| P2B.10.7 | Auditor activity audit trail (every action logged) | 🔴 |
| P2B.10.8 | Time-bound auditor access (auto-expires after audit period) | 🔴 |

### 5.11 Compliance Scoring Engine

| # | Task | Status |
|---|---|---|
| P2B.11.1 | Per-framework % compliance calculation (passing controls / total applicable controls) | 🔴 |
| P2B.11.2 | Compliance trend over time (daily snapshot table) | 🔴 |
| P2B.11.3 | Drill-down: framework → category → control → failing checks → root cause risks (URIP linkage) | 🔴 |
| P2B.11.4 | Compliance score on tenant dashboard (top-level KPI per framework) | 🔴 |
| P2B.11.5 | Score change alerts (compliance dropped > X% in Y days) | 🔴 |

### 5.12 Framework-Specific Reports

| # | Task | Status |
|---|---|---|
| P2B.12.1 | SOC 2 Type 1 / Type 2 report inputs (control descriptions, evidence references, gap analysis) | 🔴 |
| P2B.12.2 | ISO 27001 Statement of Applicability (SoA) generator | 🔴 |
| P2B.12.3 | HIPAA risk analysis report | 🔴 |
| P2B.12.4 | GDPR Article 30 record of processing register | 🔴 |
| P2B.12.5 | PCI DSS AOC (Attestation of Compliance) inputs | 🔴 |
| P2B.12.6 | India DPDP DPIA (Data Protection Impact Assessment) template | 🔴 |
| P2B.12.7 | Generic management compliance report (board-level) | 🔴 |
| P2B.12.8 | Customer security questionnaire auto-fill (CAIQ, SIG) | 🔴 |

### 5.13 Third-Party Integrations (Bundled, Not Built)

| # | Task | Status |
|---|---|---|
| P2B.13.1 | LMS connector — KnowBe4 (training completion sync) | 🔴 |
| P2B.13.2 | LMS connector — Hoxhunt (phishing simulation results sync) | 🔴 |
| P2B.13.3 | BGV connector — AuthBridge (background verification status sync) | 🔴 |
| P2B.13.4 | BGV connector — OnGrid (alternative BGV provider) | 🔴 |

### 5.14 Risk → Control Linkage (URIP × Compliance Bridge)

This is the **unique-to-URIP** capability. Sprinto cannot do this.

| # | Task | Status |
|---|---|---|
| P2B.14.1 | Extend URIP `risks` table with optional `linked_controls[]` field | 🔴 |
| P2B.14.2 | Auto-linking logic — when CVE class matches control scope, suggest linkage (e.g., CVE in web app → SOC 2 CC7.1) | 🔴 |
| P2B.14.3 | UI to confirm / manually link risks to controls | 🔴 |
| P2B.14.4 | Failing controls show their root-cause risks (drill-down from compliance score → risk) | 🔴 |
| P2B.14.5 | Risk page shows which controls it threatens (drill-up from risk → compliance impact) | 🔴 |
| P2B.14.6 | Event flow: URIP risk created → event emit → Compliance re-evaluates linked controls → updates compliance score | 🔴 |

### 5.15 Phase 2B Overall Gate

- ✅ Compliance Service runs as standalone (verified by `docker-compose.standalone.yml`)
- ✅ Compliance Service runs integrated with URIP (verified by main `docker-compose.yml`)
- ✅ All 7 framework seeders populated (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, NIST CSF)
- ✅ Initial control library (~50 controls) executes on schedule
- ✅ Evidence collection works automatically for at least 5 control types
- ✅ Policy library + acknowledgment workflow live
- ✅ Access review workflow ships (depends on Wave D connectors)
- ✅ Vendor risk module live with at least one vendor onboarded
- ✅ Auditor portal accepts a test auditor login and serves filtered view
- ✅ Compliance score visible on tenant dashboard for at least 2 frameworks
- ✅ At least 3 framework-specific reports generate (SOC 2 + ISO 27001 + India DPDP)
- ✅ Risk → Control linkage works end-to-end for at least 5 control types

---

## 6. Phase 3 — URIP × Compliance Integration Layer

**Goal:** Tighten the cross-service experience so users see one unified product, even though it's two services under the hood.

| # | Task | Status |
|---|---|---|
| P3.1 | Unified login + session — single SSO session covers both services | 🔴 |
| P3.2 | Unified top-nav — Compliance routes appear in URIP shell when tenant has Compliance Module subscribed | 🔴 |
| P3.3 | Unified dashboard — top-level page shows risk KPIs (URIP) + compliance KPIs (Compliance) side-by-side | 🔴 |
| P3.4 | Cross-service search — search query hits both risk register and compliance evidence | 🔴 |
| P3.5 | Unified audit log — both services write to a single audit log surface (queryable across both) | 🔴 |
| P3.6 | Unified notifications — risk alerts + compliance alerts in one notification feed | 🔴 |
| P3.7 | Tenant settings unified — single settings page configures both services | 🔴 |
| P3.8 | Unified billing / subscription view — admin sees what they pay for across modules | 🔴 |

### 6.1 Phase 3 Gate

- ✅ User logs in once and accesses both services without re-authentication
- ✅ User sees compliance status without leaving URIP UI
- ✅ Single audit log shows actions from both services
- ✅ Cross-service search returns combined results

---

## 7. Phase 4 — Adverb Production Deployment

**Goal:** Lift everything from local dev to Adverb's production environment.

### 7.1 Infrastructure Provisioning

| # | Task | Status |
|---|---|---|
| P4.1.1 | Create new Vercel project for Adverb frontend (`adverb.urip.io` or similar) | 🔴 |
| P4.1.2 | Create new Railway / Fly / Render project for Adverb backend (URIP core) | 🔴 |
| P4.1.3 | Create new service for Adverb Compliance backend | 🔴 |
| P4.1.4 | Create new Neon (or other Postgres) for URIP DB | 🔴 |
| P4.1.5 | Create new Postgres for Compliance DB | 🔴 |
| P4.1.6 | Set up object storage (S3 bucket / Cloudflare R2) for evidence files | 🔴 |
| P4.1.7 | Set up Redis for event bus | 🔴 |
| P4.1.8 | Domain + SSL setup | 🔴 |

### 7.2 Adverb Tenant Provisioning

| # | Task | Status |
|---|---|---|
| P4.2.1 | Provision Adverb tenant via tenant API | 🔴 |
| P4.2.2 | Apply Adverb branding (logo, colors, app name) | 🔴 |
| P4.2.3 | Configure Adverb's compliance frameworks (which to target) | 🔴 |
| P4.2.4 | Configure Adverb's asset taxonomy | 🔴 |
| P4.2.5 | Provision Adverb admin user(s) | 🔴 |

### 7.3 Connector Credential Ingestion

| # | Task | Status |
|---|---|---|
| P4.3.1 | Adverb security team provides API credentials for all 12 connectors | 🔴 (Adverb dependency) |
| P4.3.2 | Network allowlist set up for URIP backend IP at each tool | 🔴 (Adverb dependency) |
| P4.3.3 | MS Entra app registration + admin consent | 🔴 (Adverb dependency) |
| P4.3.4 | Burp Enterprise license confirmed | 🔴 (Adverb dependency) |
| P4.3.5 | All credentials encrypted at rest in URIP credential vault | 🔴 |
| P4.3.6 | Connector health checks pass for all 12 sources | 🔴 |

### 7.4 UAT + Go-Live

| # | Task | Status |
|---|---|---|
| P4.4.1 | UAT script — Adverb security team validates all flows | 🔴 |
| P4.4.2 | Compliance UAT — Adverb compliance team validates audit-readiness flows | 🔴 |
| P4.4.3 | Auditor portal UAT — invite a test auditor | 🔴 |
| P4.4.4 | Performance test — verify dashboard loads acceptably under Adverb's data volume | 🔴 |
| P4.4.5 | Backup / DR setup verified | 🔴 |
| P4.4.6 | Monitoring + alerting set up | 🔴 |
| P4.4.7 | Go-live sign-off | 🔴 |

### 7.5 Phase 4 Gate

- ✅ Adverb users use URIP-Adverb in production for 30 days without P0/P1 incidents
- ✅ All connectors run healthy
- ✅ At least one auditor session conducted via auditor portal
- ✅ At least one compliance report generated and accepted by Adverb's compliance officer

---

## 8. Compliance Module — Standalone vs Integrated Architecture

This section explains **why** Compliance is in its own folder + service, and **how** it works in both deployment modes.

### 8.1 Why Standalone

The Compliance Module has commercial value as a **standalone Sprinto-replacement product** independent of URIP:

- Some prospects want only compliance automation — they don't have or need a vulnerability dashboard
- Selling Compliance alone opens a different buyer (compliance officer / DPO) than URIP (CISO)
- Standalone deployments are cheaper to operate (one service, one DB) — useful for SMB tier pricing

Keeping Compliance in its own folder + own service makes this dual go-to-market possible **without code duplication**. Same code, two deployment modes.

### 8.2 Standalone Deployment Mode

```bash
cd compliance/
docker-compose -f docker-compose.standalone.yml up
```

In standalone mode:
- Compliance Service runs alone (no URIP backend)
- Compliance has its own auth (issues its own JWT)
- No event bus needed (no cross-service events)
- No risk-control linkage (URIP-only feature)
- Sells as "Audit-Ready" or similar SKU

### 8.3 Integrated Deployment Mode (default for Adverb)

```bash
docker-compose up   # from project_33a root
```

In integrated mode:
- URIP core + Compliance Service + shared Postgres + Redis + object storage
- URIP issues JWT; Compliance verifies it (shared auth)
- Tenant context flows via JWT claims
- Event bus connects them (`urip.risk.created` → `compliance.control.reevaluate`)
- Risk → Control linkage active
- Single tenant subscription covers both modules

### 8.4 Communication Patterns

| Pattern | When | Mechanism |
|---|---|---|
| Synchronous read | URIP UI needs compliance score for dashboard widget | Compliance REST API (`GET /compliance/score?tenant=X`) |
| Synchronous write | Tenant admin updates compliance settings from URIP UI | Compliance REST API (`POST /compliance/settings`) |
| Asynchronous event | URIP risk created → Compliance re-evaluates linked controls | Redis pub/sub (`urip.risk.created` topic) |
| Asynchronous event | Compliance control failed → URIP creates a risk | Redis pub/sub (`compliance.control.failed` topic) |
| Shared resource | Both services read tenant config | Shared `shared/tenant/` module + tenant registry in URIP DB |

### 8.5 Folder Boundaries

**Compliance Service code stays inside `compliance/`. URIP code stays in `backend/`.** They communicate only via:

1. Shared modules in `shared/` (auth, tenant, events) — these are stable contracts
2. REST APIs (versioned)
3. Event bus topics (versioned)

This means either service can be developed, tested, and deployed independently. A change to URIP doesn't break Compliance unless it changes a shared contract. A change to Compliance never breaks URIP.

---

## 9. Phase Dependency Graph

```
Phase 1 (URIP Core Productization)
    │
    ├──► Phase 2A (URIP Adverb Live Connectors)
    │       │
    │       └──► Phase 4 (Production Deployment)
    │
    ├──► Phase 2B (Compliance Module — Standalone Sub-Project)
    │       │
    │       └──► Phase 4 (Production Deployment)
    │
    ├──► Phase 3 (URIP × Compliance Integration Layer)
    │       │  (depends on both 2A + 2B partially complete)
    │       │
    │       └──► Phase 4 (Production Deployment)
    │
    └──► Phase 4 (final gate — all of 2A + 2B + 3 must be production-ready)

Phase 2A Wave D (MS Entra + Collab) BLOCKS Phase 2B.6 (Access Reviews)
Phase 2A all waves COMPLETE before Phase 2B.14 (Risk-Control auto-linkage) can be fully tested
```

**Parallelism opportunity:** Phase 2A and Phase 2B run **in parallel** after Phase 1 gate passes. Different engineers can work on connectors and Compliance simultaneously without stepping on each other (different folders, different services).

---

## 10. Cross-Cutting Concerns (apply to all phases)

| Concern | How handled |
|---|---|
| **Tests** | Every task has unit tests; phase gate requires integration tests for the full phase scope |
| **Migrations** | Every schema change ships with an alembic migration; never edit existing migrations |
| **Secrets** | Tenant credentials encrypted at rest with Fernet; key rotation plan documented |
| **Observability** | Every service exposes `/health` + `/metrics` endpoints; structured JSON logging |
| **Audit log** | Every state-changing action writes to audit log (URIP for URIP actions, Compliance for compliance actions; unified view in Phase 3) |
| **Multi-tenant safety** | Every database query filters by `tenant_id`; integration tests verify zero cross-tenant data leakage |
| **Documentation** | Every phase ends with updated README in affected folders |

---

## 11. Out of Scope (Reaffirmed from Blueprint)

These are NOT in any phase. If asked, route to a separate engagement.

- ❌ CloudSEK feature replication (only API connector — Option A — is in Phase 2A)
- ❌ Training video content authoring (LMS integration only — Phase 2B.13)
- ❌ Background verification execution (BGV connector only — Phase 2B.13)
- ❌ Penetration testing services (Burp connector ingests pen test outputs only)
- ❌ Legal advice on policies (templates only — tenant must have legal review)
- ❌ External auditor services (we make audits easy; we are not the auditor)
- ❌ SOC services / incident response execution (URIP surfaces; tenant or 3rd party SOC responds)

---

## 12. What Ships First (Recommended Sequencing)

If forced to pick a single starting task: **Phase 1.1 (multi-tenant data isolation)**. Every other change in Phase 1 is easier once tenant isolation is the baseline. Without it, the codebase keeps assuming Royal Enfield, and every Phase 1+ task carries that assumption forward.

After Phase 1 gate passes, **fork the team**:
- Track A: Phase 2A (connectors) — works in `connectors/` folder
- Track B: Phase 2B (Compliance) — works in `compliance/` folder

Track A and Track B never edit each other's files. Phase 3 work begins when both tracks are at least 70% complete.

---

**End of plan.**
