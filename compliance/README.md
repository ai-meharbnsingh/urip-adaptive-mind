# Compliance & Audit-Readiness Module

**Sprinto-equivalent compliance automation, built natively as a standalone sub-project of URIP-Adverb.**

Lives in this `compliance/` folder. Has its own backend service (FastAPI, port 8001), its own database, its own frontend, and its own deployment story. Integrates cleanly with the URIP core service when both are deployed together.

---

## Why a Separate Sub-Project

This module has commercial value as a **standalone product** independent of URIP:

- Some prospects want only compliance automation (compliance officer / DPO buyer), not a vulnerability dashboard (CISO buyer).
- Standalone deployments are cheaper to operate (one service, one DB) — useful for SMB pricing tier.
- Keeping Compliance code isolated in its own folder enables this **dual go-to-market** without code duplication.

Same code. Two deployment modes.

---

## Two Deployment Modes

### Mode A — Standalone (Sprinto-replacement product)

Sells as a focused compliance automation SaaS. URIP not required.

```bash
cd compliance/
docker-compose -f docker-compose.standalone.yml up
```

What you get:
- Compliance Service on port 8001
- Compliance Postgres
- Compliance frontend on port 3001
- Auditor portal
- Framework engine, evidence automation, policy management, access reviews, vendor risk
- Standalone JWT auth (Compliance issues its own tokens)

What you do NOT get in standalone mode:
- URIP risk register
- EPSS / KEV / MITRE threat enrichment
- Vulnerability connectors (Tenable, SentinelOne, etc.)
- Risk → Control linkage (this is a URIP × Compliance feature)

### Mode B — Integrated with URIP (Adverb default)

Compliance ships as a module within the URIP-Adverb platform.

```bash
# from project_33a root
docker-compose up
```

What you get on top of standalone:
- Single sign-on across URIP + Compliance (URIP issues JWT, Compliance verifies)
- Unified dashboard combining risk + compliance KPIs
- **Risk → Control linkage** — failing controls automatically trace back to underlying CVEs / threats via URIP's enrichment layer (the unique-to-URIP capability that Sprinto cannot do)
- Cross-service event bus (`urip.risk.created` → re-evaluate linked controls)
- Unified audit log across both services

---

## Folder Structure

```
compliance/
├── README.md                        # This file
├── ARCHITECTURE.md                  # Detailed service architecture
├── docker-compose.standalone.yml    # Standalone deployment
├── backend/
│   ├── pyproject.toml
│   └── compliance_backend/
│       ├── main.py                  # FastAPI app entry
│       ├── middleware/              # Auth + tenant context middleware
│       ├── models/                  # SQLAlchemy models (frameworks, controls, evidence, policies, etc.)
│       ├── routers/                 # API endpoints (frameworks, controls, evidence, policies, vendors, auditor portal, etc.)
│       ├── services/                # Business logic (control engine, scoring, evidence collection)
│       ├── seeders/                 # Framework data (SOC 2, ISO 27001, GDPR, HIPAA, PCI DSS, India DPDP, NIST CSF)
│       ├── connectors/              # LMS (KnowBe4, Hoxhunt) + BGV (AuthBridge, OnGrid)
│       └── events/                  # Event bus subscribers (listens for URIP risk events when integrated)
├── frontend/                        # Compliance UI (Next.js app, can run standalone OR embed in URIP shell)
├── alembic/                         # Compliance DB migrations (separate from URIP migrations)
└── docs/                            # Compliance product docs, framework references, audit guides
```

---

## What This Module Provides (per ADVERB_BLUEPRINT.md Section 7)

| # | Capability | Status |
|---|---|---|
| C1 | Multi-framework data model + cross-framework control mapping | 🔴 To build |
| C2 | Control rule engine (scheduled execution, pass/fail/inconclusive) | 🔴 To build |
| C3 | Evidence automation (auto-collection from connectors, manual upload, S3 storage) | 🔴 To build |
| C4 | Policy management (templates, version control, e-sign, acknowledgments) | 🔴 To build |
| C5 | Access reviews (depends on URIP MS Entra connector) | 🔴 To build |
| C6 | Vendor / third-party risk management | 🔴 To build |
| C7 | Incident lifecycle module (extends URIP risks) | 🔴 To build |
| C8 | Asset inventory (extends URIP asset criticality service) | 🔴 To build |
| C9 | Auditor portal (read-only, time-bound, framework-scoped) | 🔴 To build |
| C10 | Real-time compliance scoring per framework | 🔴 To build |
| C11 | Framework-specific report templates (SOC 2, ISO 27001, HIPAA, GDPR, PCI DSS, India DPDP) | 🔴 To build |
| C12 | LMS integration (KnowBe4, Hoxhunt) — we integrate, do not build training content | 🔴 To build |
| C13 | BGV integration (AuthBridge, OnGrid) — we integrate, do not run BGV | 🔴 To build |
| C14 | Risk → Control linkage (only available in integrated mode with URIP) | 🔴 To build |

Frameworks shipped: **SOC 2 (2017 + 2022), ISO 27001:2022, GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0**.

---

## Out of Scope

These are explicitly NOT in this module. Route requests for them to a separate engagement.

- ❌ Training video / content authoring (we integrate with KnowBe4 / Hoxhunt — we don't author training)
- ❌ Background verification execution (we integrate with AuthBridge / OnGrid — we don't run BGV)
- ❌ Penetration testing services
- ❌ Legal advice on policies (templates only — tenant must have legal review)
- ❌ External auditor services (we make audits easy — we are not the auditor)

---

## Quick Links

- **Architecture details:** see `ARCHITECTURE.md`
- **Implementation plan:** see `../ADVERB_IMPLEMENTATION_PLAN.md` Section 5 (Phase 2B)
- **Engagement scope:** see `../ADVERB_BLUEPRINT.md` Section 7
