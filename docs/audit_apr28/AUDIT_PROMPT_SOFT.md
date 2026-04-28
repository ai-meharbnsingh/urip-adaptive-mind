# Audit Prompt — URIP-Adverb v5

You are auditing **URIP-Adverb** at `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/`.

URIP is a multi-tenant Unified Risk Intelligence Platform. It is a vendor-neutral cockpit that aggregates security findings from existing tools — not a vertically-integrated security stack. The recent Wave 1 sprint added Celery+Redis async queue, Trust Center byte-streaming with Range support, Risk↔Control event bus, Auto-Remediation production wiring with vault-backed credentials, ticketing config validator, Word-Cloud Threat Map, Auditor activity heatmap, 8 new compliance framework seeders, 6 framework PDF report templates, 4 new connectors (KnowBe4, Hoxhunt, AuthBridge, OnGrid), and 5 new license modules at MVP-scaffold depth (DSPM, AI Security, ZTNA, Attack Path Prediction, FAIR Risk Quantification).

## Authoritative claims

Read `MASTER_BLUEPRINT.md` (root). It claims:
- 25 production connectors LIVE — every dir under `connectors/` has a `connector.py` with the 4-method `BaseConnector` contract
- 15 compliance frameworks pre-seeded (~895 controls — 7 audit-grade, 8 scaffold-grade)
- 16 license modules
- 1800+ tests
- 3 deployment modes
- §13 LIVE items wired end-to-end

## Your job

Walk the codebase and verify or correct every claim. For each finding, output:
- Severity (CRITICAL / HIGH / MEDIUM / LOW)
- Claim from blueprint
- Reality from code
- Evidence (file:line refs)
- Suggested fix

Specifically check:

1. Blueprint vs code delta — every IN-SCOPE claim implemented? any silent drops or stale labels?
2. Connector contract compliance — all `connectors/*/connector.py` expose 4 methods + 8 metadata fields?
3. Multi-tenant isolation — every domain table has `tenant_id`? every router applies `apply_tenant_filter`?
4. Auth + crypto — python-jose fully replaced by PyJWT? HMAC anti-replay on agent ingest? HKDF-derived keys?
5. Test honesty — pick 5 random test files; do they run cleanly? do assertions check real values? are mocks correctly used?
6. Migration chain — `alembic heads` for backend + compliance — linear? upgrade-from-empty works?
7. Wave 1 specific — for each new addition (Celery tasks, Trust Center streaming, event bus, executor_factory, ticketing preflight, word-cloud endpoint, heatmap, 8 framework seeders, 6 PDF templates, 4 new connectors, 5 new modules) — verify imports, tests, registration in main.py, dashboard wiring.
8. Honest scaffold caveats — the 5 new license modules and 8 new framework seeders are documented as MVP scaffold. Verify the blueprint says so without overselling.
9. Dead code — any router not registered? any service never called? any frontend page not linked?
10. Wave 1 security spot-checks — vault credential lookup tenant-scoped? Trust Center streaming validates time-bound access token? VAPT vendor JWTs single-use? File upload validates magic bytes vs Content-Type?

## Output format

Write a single Markdown report to `docs/audit_apr28/AUDIT_<YOUR_NAME>.md` with sections:
1. Verdict — top-line PASS / PASS-WITH-CAVEATS / NEEDS-FIXES + 1 paragraph
2. Important findings (must fix before customer demo)
3. Significant findings (fix in next sprint)
4. Cleanup findings (low-priority polish)
5. What you actually verified — list the commands you ran
6. Acknowledgements — what did you skip due to time?

Score 0–100 at the end. Be precise. If you don't verify a claim, say so. Do not approve unverified claims.

Time budget: ~30 minutes.
