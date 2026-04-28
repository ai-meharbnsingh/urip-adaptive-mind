# Final Audit Prompt — URIP-Adverb v5

You are auditing **URIP-Adverb** — a multi-tenant Unified Risk Intelligence Platform — at `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/`.

The project is a vendor-neutral *cockpit* that aggregates security findings from 25+ existing tools. NOT a vertically-integrated security stack. The recent Wave 1 sprint added: Celery+Redis async queue, Trust Center byte-streaming with Range support, Risk↔Control event bus, Auto-Remediation production wiring with vault-backed credentials, Ticketing config validator + preflight, Word-Cloud Threat Map, Auditor activity heatmap, 8 new compliance framework seeders (ISO 42001, EU AI Act, DORA, NIS2, ISO 27017/18/701, CIS v8), 6 framework PDF report templates, 4 new connectors (KnowBe4, Hoxhunt, AuthBridge, OnGrid), 5 new license modules (DSPM, AI Security, ZTNA, Attack Path Prediction, FAIR Risk Quantification — MVP scaffold depth).

## Authoritative claims

Read `MASTER_BLUEPRINT.md` (root). It claims:
- **25 production connectors LIVE** — every dir under `connectors/` has a `connector.py` with the 4-method `BaseConnector` contract (authenticate / fetch_findings / normalize / health_check)
- **15 compliance frameworks pre-seeded** (~895 controls — 7 audit-grade, 8 scaffold-grade with honest caveat)
- **16 license modules** — CORE + 15 capability modules (Compliance, CSPM, VM, EDR, Email, Mobile, Network, OT, External Threat, Workflow, DSPM, AI Security, ZTNA, Attack Path Prediction, Risk Quant FAIR)
- **1800+ tests** across services
- **3 deployment modes** — Pure SaaS, On-Premise, Hybrid-SaaS Docker agent
- All §13 LIVE items are wired end-to-end (Trust Center, VAPT Vendor Portal, Jira/ServiceNow ticketing, Auto-Remediation framework, Intelligence Engine 5 services, Risk Index Service)

## Your job — honest verdict

Walk the actual codebase and verify or refute every claim.

For EACH finding, output:
- **Severity** — CRITICAL / HIGH / MEDIUM / LOW
- **Claim** — exact line in blueprint or implied promise
- **Reality** — what the code actually does
- **Evidence** — file:line refs, test command output if relevant
- **Fix** — concrete next step

Specifically check:

1. **Blueprint vs code delta** — every IN-SCOPE claim implemented? any silent drops? any stale labels (Roadmap when code is actually LIVE, or vice versa)?

2. **Connector contract compliance** — all 30 connector dirs (`connectors/{name}/connector.py`) actually expose 4 methods + 8 metadata fields (DISPLAY_NAME, CATEGORY, SHORT_DESCRIPTION, STATUS, VENDOR_DOCS_URL, SUPPORTED_PRODUCTS, MODULE_CODE, CREDENTIAL_FIELDS)? Any dead code (registered connector never called)?

3. **Multi-tenant isolation** — every domain table has `tenant_id` column? every router applies `apply_tenant_filter`? any cross-tenant data-leak vectors in routes / services?

4. **Auth + crypto** — is python-jose fully gone (CVE-2024-33663/33664)? PyJWT used everywhere? HMAC signing on agent ingest (anti-replay nonce + timestamp window)? HKDF-derived keys not raw secrets?

5. **Test honesty (INV-4)** — pick 5 random test files; do they actually run pytest cleanly? do their assertions check real values, or `assert response is not None`? are mocks faking the thing being tested (fraud)? any tests that import-but-never-call the system under test?

6. **Migration chain** — `alembic heads` for both URIP backend and compliance — is it linear? does upgrade-from-empty actually work? any dangling siblings?

7. **Wave 1 specific** — for each new addition (Celery tasks, Trust Center streaming, event bus, executor_factory, ticketing preflight, word-cloud endpoint, auditor heatmap, 8 new framework seeders, 6 PDF report templates, 4 LMS/BGV connectors, 5 new license modules) — verify the module: imports cleanly, has tests, tests pass, is registered in main.py, is wired into the dashboard.

8. **Honest scaffold caveats** — the 5 new license modules and 8 new framework seeders are documented as MVP scaffold / scaffold-grade. Verify the blueprint honestly says so AND verify there's no overselling in §16 one-page summary or §2 story-in-numbers.

9. **Dead code / orphans** — any router not registered in main.py? any service defined but never called? any frontend page not linked from sidebar?

10. **Security holes specific to this audit** —
    - Auto-Remediation: does the vault credential lookup leak across tenants?
    - Trust Center: does the streaming endpoint check the time-bound access token?
    - VAPT: are vendor JWTs single-use as claimed?
    - File upload: does evidence/Trust-Center upload validate magic bytes vs Content-Type?
    - CrowdStrike RTR: the worker noted Basic-auth instead of OAuth2 token exchange — is that actually a deployment-time concern or a runtime bug?

## Output format

Write a single Markdown report to `/Users/meharban/Projects/Autonmous_Factory/multi_llm_orchestrator/case-studies/project_33a/docs/audit_apr28/AUDIT_<YOUR_NAME>.md` with sections:
1. **Verdict** — top-line PASS / PASS-WITH-CAVEATS / FAIL + 1 paragraph
2. **CRITICAL findings** (must fix before customer demo)
3. **HIGH findings** (fix in next sprint)
4. **MEDIUM/LOW findings** (cleanup)
5. **What you actually verified** — list the commands you ran and what you read
6. **Honest acknowledgements** — what did you skip due to time / context window?

Score 0–100 at the end. Be brutal. Codex previously scored a Claude-presented "99% proven" result at 2/10 for fake calibration. Don't be that. If you don't verify a claim — say so. Don't rubber-stamp.

Time budget: ~30 minutes. Pick the most load-bearing claims first.
