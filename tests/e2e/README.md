# End-to-End Tests for URIP + Compliance

This directory and its sibling `tests/e2e_cross_service/` hold the end-to-end
test suite that exercises full user workflows across the URIP service
(`backend/`) and the Compliance service
(`compliance/backend/compliance_backend/`).

## Layout

```
tests/
├── e2e/                                # URIP-only workflows
│   ├── conftest.py                     # shared fixtures (super-admin, tenant_factory, …)
│   ├── test_workflow_01_tenant_to_first_risk.py
│   ├── test_workflow_02_multi_tenant_isolation.py
│   ├── test_workflow_08_connector_lifecycle.py
│   ├── test_workflow_09_module_subscription.py
│   └── test_workflow_10_white_label_theming.py
│
└── e2e_cross_service/                  # Compliance + cross-service workflows
    ├── conftest.py                     # spins up BOTH apps + an in-process event bus
    ├── test_workflow_03_control_failure_to_risk.py
    ├── test_workflow_04_risk_resolved_to_compliance.py
    ├── test_workflow_05_policy_lifecycle.py
    ├── test_workflow_06_vendor_risk_lifecycle.py
    ├── test_workflow_07_auditor_portal.py
    ├── test_workflow_11_compliance_scoring_trend.py
    └── test_workflow_12_evidence_bundle.py
```

## Running

```bash
# from the project root
source .venv/bin/activate

# whole suite
pytest tests/e2e tests/e2e_cross_service -v

# just the URIP-side workflows
pytest tests/e2e -v

# just the cross-service workflows
pytest tests/e2e_cross_service -v

# with coverage focused on integration paths
pytest tests/e2e tests/e2e_cross_service \
       --cov=backend --cov=compliance/backend/compliance_backend \
       --cov=connectors --cov=shared \
       --cov-report=term-missing
```

There are no external prerequisites — both apps run in-process against
in-memory SQLite (the URIP `pg_dialect.UUID` / `JSON` types are monkey-patched
to SQLite-compatible substitutes inside the conftests).  The cross-service
tests use a `DummyEventBus` (asyncio.Queue) in place of Redis, so the suite
runs with zero infrastructure.

## Workflow Inventory

| #  | Workflow                                         | File                                                   |
|----|--------------------------------------------------|--------------------------------------------------------|
| 1  | Tenant onboarding to first risk                  | e2e/test_workflow_01_tenant_to_first_risk.py           |
| 2  | Multi-tenant strict isolation (URIP surface)     | e2e/test_workflow_02_multi_tenant_isolation.py         |
| 3  | Compliance control failure → URIP risk           | e2e_cross_service/test_workflow_03_control_failure_to_risk.py |
| 4  | URIP risk resolved → compliance re-evaluation    | e2e_cross_service/test_workflow_04_risk_resolved_to_compliance.py |
| 5  | Policy lifecycle (create / version / acknowledge)| e2e_cross_service/test_workflow_05_policy_lifecycle.py |
| 6  | Vendor risk lifecycle                            | e2e_cross_service/test_workflow_06_vendor_risk_lifecycle.py |
| 7  | Auditor portal full audit cycle                  | e2e_cross_service/test_workflow_07_auditor_portal.py   |
| 8  | Connector lifecycle (simulator + scheduler tick) | e2e/test_workflow_08_connector_lifecycle.py            |
| 9  | Module subscription enforcement                  | e2e/test_workflow_09_module_subscription.py            |
| 10 | White-label theming end-to-end                   | e2e/test_workflow_10_white_label_theming.py            |
| 11 | Compliance scoring trend (snapshots + drop warn) | e2e_cross_service/test_workflow_11_compliance_scoring_trend.py |
| 12 | Evidence bundle export (ZIP + manifest)          | e2e_cross_service/test_workflow_12_evidence_bundle.py  |

## Cross-service contract — current behavior

`shared/events/topics.py` defines the schema constants for the Redis-pub/sub
contract between URIP and Compliance, but as of this codebase NEITHER service
wires a publisher (compliance) or subscriber (URIP) into its router /
scheduler.  See:

* `compliance_backend/services/control_engine.py` — `TODO P2B.3.4` notes the
  unfinished publish step.
* `backend/main.py` — no subscriber registration.

The cross-service tests therefore validate the **schema contract** (the
Pydantic payloads round-trip through the in-process event bus and the
receiver-side handler accepts the data) and the **end-to-end integration of
the two HTTP surfaces** (the URIP risk-creation API accepts the data the
subscriber would hand it; Compliance score recalculates after a control
re-run).  When the production wiring lands, the only change is to swap the
`event_bus` fixture from `DummyEventBus` to `RedisEventClient` — the test
bodies will continue to pass.

## Test-only adapters in the cross-service conftest

Two adapters are applied in `tests/e2e_cross_service/conftest.py` to keep the
suite hermetic without touching production source:

1. **`vendors` router registration.**  `compliance_backend/routers/vendors.py`
   exists with the full vendor CRUD + scoring surface, but
   `compliance_backend/main.py` does not `include_router` it.  The conftest
   attaches it to the live app instance for the test process only.  This is a
   real source-code gap that should be fixed in production for workflow 6 to
   work outside tests.
2. **`APIRoute.__init__` patch for status 204 / 304 routes.**  Under Python
   3.14 + `from __future__ import annotations` (used in
   `compliance/backend/compliance_backend/routers/auditor_invitations.py`),
   FastAPI's response-model inference resolves a `-> None` annotation to
   `NoneType` (truthy) instead of `None`, which trips
   `assert is_body_allowed_for_status_code(...)` on no-body status codes.
   The conftest forces `response_model=None` for those status codes.
3. **`pydantic-settings` `env_file` strip.**  The repo's `.env` file uses
   comma-separated `CORS_ORIGINS=...` for URIP, which the compliance Settings
   model (declares `CORS_ORIGINS: list[str]`) tries to JSON-parse and crashes.
   The conftest disables `env_file` on every BaseSettings subclass so each
   service reads only environment variables the conftest has set.

## Honest limitations

* **EPSS / KEV / MITRE enrichment** (workflow 8) is NOT exercised because
  `backend/services/exploitability_service.enrich_risk` calls the real
  EPSS / KEV APIs over the network.  E2E tests pre-populate
  `composite_score` so the API short-circuits enrichment.  Real enrichment
  is covered by unit tests that mock httpx (out of scope for this suite).
* **Redis-backed pub/sub** (workflows 3 + 4) is replaced with an in-process
  bus.  The schema contract is validated; the network layer is not.
* **`AuditLog.tenant_id`** is set by `backend/routers/risks.py:create_risk`
  but NOT by `backend/routers/acceptance.py` or the update-risk path
  (see code).  Workflow 1 + workflow 2 only assert audit-log scoping for
  `risk_created` rows.  Other actions are filtered out by
  `apply_tenant_filter` because their `tenant_id` is NULL — a real
  shortcoming we document rather than paper over.
* **Seeders / simulators in `compliance_backend/seeders/simulators/`** are
  not exercised — workflows that mention "compliance_score_simulator" or
  "vendor_response_simulator" use direct DB seeding or the explicit
  `respond` endpoint instead, because those simulator modules are CLI
  utilities not service-layer functions.
* **Auditor JWT expiry contains a real bug** in
  `compliance_backend/services/auditor_service.py:_mint_auditor_jwt` —
  it does `int(access.expires_at.timestamp())` on a naive `utcnow()`-derived
  datetime, which on non-UTC hosts produces an `exp` claim offset by the
  local timezone.  Workflow 7 sets the audit period 2 days in the future
  to absorb the worst-case TZ offset; the bug should be fixed by switching
  to `datetime.now(timezone.utc)`.

## What runs against external infra

Nothing.  The whole suite is hermetic.  If a future test needs Redis or
Postgres, mark it `@pytest.mark.integration` (already declared in
`pytest.ini`) and provide a skip-when-unavailable check.
