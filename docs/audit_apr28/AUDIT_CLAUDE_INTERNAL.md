# URIP-Adverb v5 — Internal Claude Audit (Apr 28, 2026)

Auditor: Claude Opus 4.7 (1M ctx)  
Mode: read-only, INV-0 enforced (no `rm`)  
Scope: Wave 1 worker reports + MASTER_BLUEPRINT.md claims vs on-disk reality

---

## 1. Verdict — **PASS-WITH-CAVEATS** (score 78/100)

The Wave 1 sprint largely delivered what it claimed. All 11 new routers are registered, the Alembic chain is single-headed, the connector contract is honoured by 28/29 tested connectors, multi-tenant scoping holds up under five-router spot-check, agent ingest implements HMAC + timestamp + replay-cache, and Trust Center streaming verifies the time-bound access token before serving bytes. The §13 honest-caveat language is present and consistent.

However, **two real bugs** show up under integration-style execution that the worker reports glossed over:
1. The `python-jose → PyJWT` migration claim is **complete in the URIP backend but NOT in `compliance/backend/`** — the dependency, the import, and the test `test_crit005_pyjwt_migration` all confirm regression. **18 compliance-backend tests fail.**
2. `bug_bounty/connector.py` ships `CREDENTIAL_FIELDS` with the **wrong schema shape** (`key` instead of `name`; `options` as plain strings instead of `list[dict]`), which crashes `GET /api/connectors` with a Pydantic ValidationError every time bug_bounty's metadata is exposed. Two router tests fail in the URIP backend specifically because of this.

Plus one MEDIUM cockpit-UX gap: **the 5 new MVP-scaffold pages exist on disk but are not linked from `frontend/js/sidebar.js`** — a customer demoing the product cannot reach DSPM, AI-Security, ZTNA, Attack-Path, or Risk-Quantification from the navigation.

These are concrete, fixable defects — not architectural problems. Recommend fixing CRITICALs before any customer demo, HIGH before next sprint close, MEDIUM before public launch.

---

## 2. CRITICAL findings (must fix before customer demo)

### C1 — `python-jose` CVE-replacement is INCOMPLETE in `compliance/backend`
- **Claim** (commit `aa09c…`/`1a83f…` and Wave 1 dependency hygiene): "python-jose 3.3.0 (CVE-2024-33663, CVE-2024-33664, library unmaintained) replaced with PyJWT 2.9+".
- **Reality**: `compliance/backend/pyproject.toml` still declares `python-jose[cryptography]>=3.3.0`. `compliance/backend/compliance_backend/middleware/auth.py:26` still imports `from jose import JWTError, jwt, ExpiredSignatureError`. Four test files in `compliance/backend/tests/` still `from jose import jwt`.
- **Evidence**:
  ```
  $ grep -r "from jose" backend/ compliance/backend/
  compliance/backend/tests/test_auth_modes.py:9:from jose import jwt
  compliance/backend/tests/test_framework_routes.py:9:from jose import jwt
  compliance/backend/tests/test_framework_reports/test_framework_reports_router.py:16:from jose import jwt
  compliance/backend/tests/test_framework_reports/test_training_bgv_rollup.py:7:from jose import jwt
  compliance/backend/compliance_backend/middleware/auth.py:26:from jose import JWTError, jwt, ExpiredSignatureError

  $ pytest compliance/backend/tests/test_crit005_pyjwt_migration.py
  FAILED tests/test_crit005_pyjwt_migration.py::test_compliance_middleware_auth_uses_pyjwt
   - Legacy JWT lib ImportFrom lingers in compliance_backend/middleware/auth.py
  FAILED tests/test_crit005_pyjwt_migration.py::test_verify_token_rejects_tampered_signature
  FAILED tests/test_crit005_pyjwt_migration.py::test_verify_token_rejects_expired_token
  FAILED tests/test_crit005_pyjwt_migration.py::test_verify_token_rejects_alg_none_token
  FAILED tests/test_crit005_pyjwt_migration.py::test_verify_token_rejects_alg_hs512_when_only_hs256_allowed
  ```
- **Fix**: Port `compliance_backend/middleware/auth.py` to `pyjwt` (already used in some compliance modules per `pyproject.toml` line "pyjwt[crypto]>=2.9,<3"). Delete `python-jose` from `compliance/backend/pyproject.toml`. Replace the four `from jose import jwt` test imports.

### C2 — `bug_bounty` connector ships CREDENTIAL_FIELDS with broken shape; crashes `GET /api/connectors`
- **Claim**: "CSPM connectors got full 8-field metadata; 4 connector CATEGORY allowlist fixes" — implies all connectors conform.
- **Reality**: `connectors/bug_bounty/connector.py:91` declares
  ```python
  {"key": "platform", "label": "Platform", "type": "select",
   "options": ["hackerone", "bugcrowd", "webhook"], "required": True}
  ```
  But `backend/schemas/connectors.py:25 CredentialFieldOut` requires `name: str` and `options: list[dict[str, str]] | None`. Result: `backend/routers/connectors.py:453` raises `pydantic_core.ValidationError: 4 validation errors for CredentialFieldOut`.
- **Evidence**:
  ```
  $ pytest tests/test_routers/test_connectors_router.py
  FAILED tests/test_routers/test_connectors_router.py::TestListConnectors::test_list_returns_all_registered_connectors
  FAILED tests/test_routers/test_connectors_router.py::TestListConnectors::test_list_marks_unconfigured_by_default
  E   pydantic_core._pydantic_core.ValidationError: 4 validation errors for CredentialFieldOut
  E   name → Field required (input had 'key' instead)
  E   options.0 → Input should be a valid dictionary (got 'hackerone')
  E   options.1 → Input should be a valid dictionary (got 'bugcrowd')
  E   options.2 → Input should be a valid dictionary (got 'webhook')
  ```
- **Behaviour note**: failures are order-dependent in `pytest` (pass when `test_connectors_router.py` runs alone because some other test changes registry state). In production this **always** fails because the catalog endpoint always materialises every registered connector's metadata.
- **Fix**: rewrite `connectors/bug_bounty/connector.py:90-95` to `{"name": "platform", ..., "options": [{"value": "hackerone", "label": "HackerOne"}, ...]}`. Verify no other connector uses `key`-instead-of-`name` (`grep -rn '"key":' connectors/*/connector.py`).

---

## 3. HIGH findings (next sprint)

### H1 — 18 compliance-backend test failures (blocks Sprinto-equivalent claim)
- **Claim**: "Native Sprinto-equivalent compliance module on the same data layer"; "1800+ tests".
- **Reality**: `cd compliance/backend && pytest -q` → `18 failed, 512 passed`. Themes:
  - `test_crit005_pyjwt_migration` (5 fails) — see C1.
  - `test_critfix_uploads/test_high011_evidence_upload` (multiple fails) — content-type sniffing returns `None` for known-good PDFs and PNGs, server rejects with 422 ("detected None"). Looks like a regression in the magic-bytes detector or a missing dependency (`python-magic` / `libmagic`).
  - `test_critfix_security.py::test_new2_auditor_jwt_exp_is_utc_seconds` — auditor JWT exp claim format wrong.
  - `test_evidence_routes.py::test_upload_evidence_success` — assertion error.
  - `test_vendor_routes.py::test_vendor_document_upload_multipart_and_expiring_docs` — content-type chain.
- **Evidence**: `compliance/backend/tests/` final line: `18 failed, 512 passed in 8.67s`.
- **Fix**: triage in this order: (a) finish the PyJWT migration → kills 5; (b) fix or stub-out the libmagic content-type detector → kills 7-8; (c) re-stamp the auditor-JWT exp serialization.

### H2 — URIP backend collection: 1957 tests, full run = 2 fails (1916 passed, 3 skipped, 38 deselected by ignore)
- **Claim**: "1800+ tests" — exceeded.
- **Reality**: collection works; full run: `2 failed, 1916 passed, 3 skipped in 348.11s` — both failures are C2 above.
- **Fix**: covered by C2.

### H3 — `aws_cspm` connector fails to import in venv (boto3 not installed)
- **Claim**: "boto3 added to requirements.txt" — yes, it's there. But the active `.venv/` has no `boto3` installed (`pip list | grep boto3` → empty). Other deps (celery, redis, respx) are installed.
- **Reality**: `python /tmp/audit_helpers/check_connectors.py` returns `aws_cspm: import error: ModuleNotFoundError: No module named 'boto3'`. Source code itself has full contract (DISPLAY_NAME, CATEGORY="CSPM", all 4 methods, all 8 metadata fields).
- **Fix**: `pip install -r requirements.txt` in the dev venv, or add boto3 to a CI-bootstrap step. Severity HIGH because the claim "25 production connectors LIVE" is technically false at runtime in this venv (24 importable).

### H4 — `acceptance.py` cross-tenant defence-in-depth gap on Risk/User join
- **Claim**: multi-tenant isolation everywhere.
- **Reality**: `backend/routers/acceptance.py:73,76` does `select(Risk).where(Risk.id.in_(risk_ids))` and `select(User).where(User.id.in_(user_ids))` *without* an explicit `tenant_id` filter. The IDs come from already-tenant-scoped `AcceptanceRequest` rows, so under normal data integrity this is safe — but `audit_log.py:86-89` already added the same defensive filter (`if hasattr(User, "tenant_id"): user_query = user_query.where(...)`) and the comment there explicitly says "Codex LOW-003: defensive tenant filter on the user join. Even if a corrupted audit row references a user_id from another tenant, the enrichment never loads the foreign user row." — `acceptance.py` should mirror that pattern.
- **Fix**: add the same `if hasattr(Model, "tenant_id"): query = query.where(Model.tenant_id == TenantContext.get())` to both joins.

---

## 4. MEDIUM / LOW findings

### M1 — 5 new MVP-scaffold modules not in sidebar nav (cockpit-UX gap)
- **Claim**: Wave 1e — DSPM / AI Security / ZTNA / Attack Path / Cyber Risk Quantification "each ships model + service + REST router + 1 frontend page + tests". The blueprint claims they are "promoted to LIVE at MVP scaffold depth … so a buyer sees the module exists in nav".
- **Reality**: pages exist on disk:
  ```
  frontend/dspm-dashboard.html
  frontend/ai-security-dashboard.html
  frontend/ztna-dashboard.html
  frontend/attack-path.html
  frontend/risk-quantification.html
  ```
  But `frontend/js/sidebar.js` `NAV_SECTIONS` (Main / Connectors / CSPM / Analytics / Administration / Settings) contains **zero** links to any of them. A logged-in user has no way to navigate to these from the cockpit shell — only by typing the URL.
- **Evidence**: `grep -iE "dspm|ai-security|ztna|attack-path|risk-quant" frontend/js/sidebar.js` → no output.
- **Fix**: add a "Section 13 / Strategic Modules" nav group with the 5 entries. ~30 lines.

### M2 — Migration chain testable on Postgres only; SQLite smoke-test blocked by `now()` raw SQL in 0001
- **Claim**: linear migration chain.
- **Reality**: `alembic heads` confirms single head `0015_p33a_section13_modules`. Two branches at `0010_*` are properly merged at `0011_merge_vapt_intelligence` (`down_revision = ("0010_vapt_vendor_portal", "0010_risk_intelligence_engine_fields")`). However, attempting `alembic upgrade head` against a fresh SQLite DB fails inside `0001_multi_tenant_foundation` because of a raw-SQL `INSERT ... VALUES (..., now())` that's Postgres-specific. **This is not a chain bug** — it's that 0001 is hand-written SQL with a vendor function. Linear chain confirmed; CI should run the upgrade against ephemeral Postgres, not SQLite.
- **Fix** (optional): replace `now()` with portable `func.now()` via SQLAlchemy core, or skip data-seed inserts on SQLite. Severity LOW.

### M3 — `frontend/js/sidebar.js` also missing Compliance / Trust Center / Threat-Intel-WordCloud links
- **Reality**: scanning `NAV_SECTIONS`, there is no entry for the Compliance dashboard pages, Trust Center admin page, auditor portal, or the new word-cloud/threat-map enhancements. (`threat-map.html` is linked under "Main" — that one is fine.)
- **Fix**: same fix as M1 — add the missing groups.

### L1 — `python-jose` lingers in 4 compliance test files even though tests are still expected to use it currently
- See C1; the test files importing `from jose import jwt` are the same as the production code's choice. Once C1 is fixed, those tests must be ported too. LOW because they depend on C1.

---

## 5. What I actually verified (commands run)

| # | Verification | Command | Result |
|---|---|---|---|
| 1 | Connector contract compliance | `python /tmp/audit_helpers/check_connectors.py` | 28/29 PASS; aws_cspm fails at import (boto3 not in venv) |
| 2 | Alembic heads | `.venv/bin/alembic heads` | single head `0015_p33a_section13_modules` |
| 3 | Alembic upgrade attempt | `alembic -c /tmp/audit_helpers/alembic_sqlite.ini upgrade head` | env imports OK; fails on Postgres-only `now()` in 0001 (LOW) |
| 4 | Router registration | `grep "include_router" backend/main.py` | all 11 listed routers present |
| 5 | Test collection | `pytest tests/ --co -q` | **1957 tests collected**, no errors |
| 6 | URIP test full run | `pytest tests/ --ignore=tests/test_connectors_lms_bgv -q` | **1916 passed, 2 failed, 3 skipped** (5:48 wall) |
| 7 | Compliance test full run | `cd compliance/backend && pytest tests/ -q` | **512 passed, 18 failed** (8.67s) |
| 8 | python-jose grep | `grep -r "from jose" backend/ compliance/backend/` | 5 hits in compliance, 0 in URIP backend |
| 9 | HMAC + timestamp + replay-cache (agent_ingest) | grep + read `backend/routers/agent_ingest.py` | confirmed: HMAC-SHA256, X-Timestamp window ±300s, signature_replay_cache acts as nonce |
| 10 | Trust Center token verification | grep + read `backend/services/trust_center_service.py` | confirmed: hash_access_token + expires_at + revoked checks before stream |
| 11 | Tenant scoping (5 routers) | grep tenant in dspm/ai_security/ztna/attack_path/risk_quantification | scoping done in service layer (71 tenant_id refs) — routers delegate via tenant_id arg |
| 12 | Tenant scoping (broader) | scan all routers for `select` with no tenant filter | only `threat_intel.py` (read-only external feeds, no SQL) and `ticketing_webhook.py` (uses tenant_slug + HMAC) — both correct |
| 13 | Dead-code check | grep callers of connector_runner / auto_remediation_service / event_subscribers | all 3 have ≥1 router and/or main.py caller — INV-1 OK |
| 14 | Sidebar links for 5 modules | `grep -iE "dspm\|ai-security\|ztna\|attack-path\|risk-quant" frontend/js/sidebar.js` | **zero hits** — pages exist but unlinked |
| 15 | §5a.2 heading | `grep "5a.2" MASTER_BLUEPRINT.md` | confirmed updated to "(LIVE — framework complete)" |
| 16 | §13 honest caveat | grep "MVP scaffold" / "scaffold-grade" / PARTIAL→LIVE | confirmed: 8 scaffold-grade frameworks have explicit paywalled-PDF caveat; 5 modules have explicit MVP-scaffold caveat; PARTIAL section explicitly notes promotion |
| 17 | Recently-edited 8th-field | grep metadata count for cert_in/siem/email_security/bug_bounty | all 4 have ≥8 metadata fields |
| 18 | bug_bounty schema bug | read `connectors/bug_bounty/connector.py:91` + `backend/schemas/connectors.py:25-37` | mismatch confirmed (key vs name; options shape) |

---

## 6. Honest acknowledgements (what I skipped or hand-waved)

- **I did not run a real Postgres alembic upgrade.** I only ran `alembic heads` and a SQLite smoke that exposed a Postgres-only seed function in 0001. A green real-PG upgrade would harden the migration claim further; what I have is enough to confirm the chain is single-headed and the merge of `0010_vapt_vendor_portal` + `0010_risk_intelligence_engine_fields` is intact.
- **I did not load every router under TestClient** to confirm `GET /api/dspm/...` returns 200 with module gating + tenant scoping enforced end-to-end. I confirmed registration in `main.py`, presence of `tenant_id` plumbing, and module-gate decorators — but for the 5 new MVP-scaffold modules my evidence is structural, not behavioural.
- **I did not run the full 1957-test suite twice** to confirm the 2 connector-router failures are stable across runs; they fail in the full-suite run, pass in isolation, indicating registry-state bleed. The bug shape is real (`bug_bounty` ships wrong schema) regardless of test ordering.
- **I did not exercise the executor_factory** loading real CrowdStrike/Ansible/Fortinet/CyberArk credentials from the Fernet vault — the code path is tested by unit tests, but I didn't trace one full call from router → factory → vault → HTTPX request.
- **I did not validate the Trust Center HTTP-206 Range header** or the `s3://` / `http(s)://` adapters with real backends — I only confirmed the access-token verification gate fires before the stream opens.
- **I did not benchmark** the BFS attack-path engine or the FAIR LM × LEF math — the worker claims point-estimate / no Monte Carlo, which matches the source structure I scanned, but I did not run end-to-end calculations.

---

## 7. Score: **78 / 100**

| Dimension | Score | Notes |
|---|---|---|
| Architectural integrity | 17/20 | clean router registration, alembic linear, tenant_query helper sound |
| Wave 1 delivery vs claims | 13/20 | most worker claims hold; bug_bounty schema bug + python-jose-in-compliance are concrete misses |
| Test discipline (INV-4) | 14/20 | 1916/1918 URIP green; but 18/530 compliance fails fail loudly and would block release |
| Honest caveats (INV-5) | 19/20 | §13 caveats are exemplary — explicit PARTIAL→LIVE+caveat language |
| Multi-tenant isolation | 9/10 | strong overall; one defence-in-depth gap in `acceptance.py` joins |
| Cockpit UX (cohesion) | 6/10 | 5 new module pages orphaned from nav; product-demo blocker |

**Recommendation**: ship-blocker fixes are C1 (jose→PyJWT in compliance), C2 (bug_bounty schema), M1 (sidebar links). Estimated ~4–6 hours. After those, the platform is genuinely demo-ready at the depth claimed.
