# Compliance Module — Architecture

This document explains how the Compliance Service is structured internally, how it talks to URIP when integrated, and how it operates standalone.

---

## Service Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                     Compliance Service (port 8001)               │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                      Routers                              │  │
│   │   /frameworks   /controls   /evidence   /policies        │  │
│   │   /access-reviews   /vendors   /incidents   /assets      │  │
│   │   /auditor (read-only)   /score   /reports               │  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                      Services                             │  │
│   │   ControlEngine    EvidenceCollector    PolicyManager    │  │
│   │   AccessReviewer   VendorRiskScorer    ScoringEngine     │  │
│   │   ReportGenerator  AuditorPortal       LinkageEngine     │  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Models    │  Connectors    │  Events    │  Middleware   │  │
│   │  (SQLAlchemy) │ (LMS, BGV)  │ (Pub/Sub) │ (Auth, Tenant)│  │
│   └─────────────────────────────────────────────────────────┘  │
│                              │                                   │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
        ┌─────────────┐  ┌──────────┐  ┌──────────────┐
        │ Compliance  │  │ Object   │  │ Redis        │
        │ Postgres    │  │ Storage  │  │ (event bus,  │
        │             │  │ (S3)     │  │  if integrated)│
        └─────────────┘  └──────────┘  └──────────────┘
```

---

## Data Model (High-Level)

```
frameworks                  framework_versions          controls
  id                          id                          id
  name (SOC 2, ISO 27001…)    framework_id                framework_id
  type                        version (e.g. 2017, 2022)   category
                              effective_date              control_code (e.g. CC7.1)
                                                          description
                                                          rule_function (plugin name)

framework_control_mapping (cross-framework)
  source_control_id
  target_control_id
  mapping_type (equivalent / partial / prerequisite)

control_check_runs
  id, control_id, tenant_id, run_at, status (pass/fail/inconclusive),
  evidence_ids[], failure_reason

control_evidence
  id, control_id, tenant_id, type (screenshot/config/log/ticket),
  storage_uri, audit_period, captured_at, captured_by

policies
  id, tenant_id, name, current_version_id, owner, expires_at

policy_versions
  id, policy_id, version_number, content, published_at, published_by

policy_acknowledgments
  id, policy_version_id, user_id, acknowledged_at, signature

access_reviews
  id, tenant_id, scope, reviewer_id, due_date, status

access_review_decisions
  id, access_review_id, user_id, role, decision (keep/revoke), reviewer_at

vendors
  id, tenant_id, name, criticality, contact, status

vendor_questionnaires + vendor_responses + vendor_documents

incidents (extends URIP risks)
  id, risk_id (FK to URIP risk if integrated), detection_at,
  containment_at, eradication_at, recovery_at, rca, lessons_learned

assets
  id, tenant_id, name, type, owner, classification, location,
  lifecycle_state, business_criticality

risk_control_linkage (only used in integrated mode)
  risk_id (URIP), control_id (Compliance), linkage_type (auto/manual),
  linked_at
```

---

## Auth Model

### Standalone Mode

- Compliance Service issues its own JWTs
- Own user table (`users`)
- Own roles (`admin`, `manager`, `analyst`, `auditor`)

### Integrated Mode

- URIP issues JWTs
- Compliance verifies tokens using shared signing key (loaded from `shared/auth/`)
- No own user table — user identity comes from token claims
- Tenant context comes from `tenant_id` claim in token
- Compliance maintains its own role table mapping URIP user ID → compliance role

Auth middleware is implemented once and configured at boot:

```python
# pseudocode
if STANDALONE_MODE:
    auth = StandaloneAuth(jwt_secret=COMPLIANCE_JWT_SECRET)
else:
    auth = IntegratedAuth(jwt_verifier=shared.auth.URIPVerifier())
```

---

## Event Bus Contracts

When integrated with URIP, both services publish/subscribe to a shared Redis pub/sub channel.

### URIP → Compliance

| Topic | Payload | Action |
|---|---|---|
| `urip.risk.created` | `{risk_id, tenant_id, severity, source, cve_id, asset_id}` | Compliance re-evaluates linked controls; emits `compliance.control.failed` if a control's rule now fails |
| `urip.risk.resolved` | `{risk_id, tenant_id, resolved_at}` | Compliance re-evaluates; control may now pass |
| `urip.connector.synced` | `{connector_name, tenant_id, synced_at}` | Compliance triggers evidence capture for any controls bound to this connector |

### Compliance → URIP

| Topic | Payload | Action |
|---|---|---|
| `compliance.control.failed` | `{control_id, tenant_id, framework_id, severity}` | URIP optionally creates a risk record for tracking remediation through normal workflow |
| `compliance.policy.expiring` | `{policy_id, tenant_id, days_until_expiry}` | URIP shows alert in unified dashboard |

Topics are versioned — breaking changes require new topic name (`urip.risk.created.v2`).

---

## Connectors (Compliance-Specific)

These are **separate from URIP connectors**. Compliance only ships connectors for tools URIP doesn't already integrate with — primarily LMS and BGV providers.

| Connector | Purpose | Notes |
|---|---|---|
| KnowBe4 | Security training completion + phishing simulation results | API key auth; pulls per-user training status |
| Hoxhunt | Phishing simulation + behavior change tracking | API key auth |
| AuthBridge | Background verification status | Token auth; checks each employee's BGV completion |
| OnGrid | Alternative BGV provider | Token auth |

For all other data sources (cloud configs, identity logs, endpoint state, etc.), Compliance reuses URIP's connector data via the event bus or via a thin internal API call to URIP.

---

## Control Rule Engine

Every control has a `rule_function` field pointing to a plugin in `services/control_rules/`. Each plugin implements:

```python
def check(tenant_id: str, context: ControlContext) -> ControlCheckResult:
    """
    Returns:
        ControlCheckResult(
            status: Literal["pass", "fail", "inconclusive"],
            evidence: list[EvidenceItem],
            failure_reason: Optional[str],
        )
    """
```

The scheduler (cron-like) runs all enabled controls per tenant on a schedule defined per control (default: daily). Results write to `control_check_runs` table.

---

## Frontend Integration Model

Compliance frontend (`compliance/frontend/`) is a separate Next.js app. Two ways it can render:

### Standalone

Compliance frontend serves its own pages on `compliance.adverb.com` (or similar). Self-contained — login, dashboard, all routes.

### Embedded in URIP shell

URIP frontend lazy-loads Compliance routes at `/compliance/*`. Achieved via:

- **Module Federation** (Webpack) or **Next.js middleware proxy** — Compliance frontend bundle exposed via `urip.adverb.com/compliance/_next/...`
- Top-nav extension in URIP shell adds "Compliance" tab when tenant has subscription
- Shared design system tokens so Compliance UI matches URIP look

User experience is seamless — they see one product, even though two frontends are stitched together.

---

## Deployment Targets

| Mode | Services | DBs | Object Storage | Event Bus |
|---|---|---|---|---|
| Standalone | Compliance backend + frontend | Compliance Postgres | S3 / R2 | Not required |
| Integrated | URIP backend + URIP frontend + Compliance backend + Compliance frontend | URIP Postgres + Compliance Postgres | S3 / R2 (shared) | Redis (shared) |

Both modes are dockerized. Standalone mode uses `compliance/docker-compose.standalone.yml`. Integrated mode uses the root `docker-compose.yml` which orchestrates all services.

---

## Why This Architecture (Decisions Log)

| Decision | Why |
|---|---|
| Separate service (not URIP router) | Standalone deployability; commercial product flexibility; team independence |
| Separate database | True data isolation; standalone deployments don't need URIP's DB; can scale independently |
| JWT verification (not own auth in integrated mode) | Avoid double-login UX disaster; centralize tenant identity in URIP |
| Event bus for cross-service triggers | Loose coupling — URIP doesn't need to know Compliance is running |
| Separate frontend with embedding option | Allows standalone product UX OR seamless integrated UX; no compromise |
| Compliance has own connectors only for LMS / BGV | Reuse URIP's existing 12 connectors via event bus rather than duplicating |

---

## What Lives Where

| Code goes in | When |
|---|---|
| `compliance/backend/` | Anything compliance-specific (controls, evidence, policies, reports) |
| `backend/` (URIP core) | Anything risk / vulnerability / connector related |
| `shared/` | Shared contracts (auth, tenant, events) — **breaking change here requires both services to bump simultaneously** |
| `connectors/` | URIP source connectors (Tenable, SentinelOne, etc.) — Compliance doesn't touch these |
| `compliance/backend/compliance_backend/connectors/` | Compliance-only connectors (LMS, BGV) |
