# URIP Audit — Codex (Apr 28, 2026)

## 1. Verdict

**PASS-WITH-CAVEATS.** The Wave 1 claims you listed largely hold in-code: Compliance runs **530/0**, `python-jose` is gone from production code (PyJWT is used in both URIP + Compliance), CrowdStrike RTR now performs a real OAuth2 client-credentials exchange and sends `Authorization: Bearer …`, `storage_uri` is no longer exposed on Compliance API response schemas, and the frontend sidebar includes the 5 new module pages.  

However: the “**1923/0-fail URIP**” claim did **not** reproduce in this environment because **Celery is not installed here**, causing all Celery tests to fail on import. That may be an environment/packaging issue (Docker installs it), but the claim as-stated is not true “against this codebase in this runtime”.

## 2. Important findings (must fix before customer demo)

### HIGH-001 — “1923/0-fail URIP” does not hold in this environment (Celery import failures)
- **Claim:** “1923/0-fail URIP” (Wave 1 status update).
- **Reality:** Full-suite run fails due to `ModuleNotFoundError: No module named 'celery'` when importing the Celery app.
- **Evidence:**
  - Celery is imported unconditionally: `backend/services/celery_app.py:31`.
  - Celery tests import the module-level singleton: `tests/test_celery/test_celery_app.py:37`.
  - Dependency is declared (so Docker/CI should install it): `requirements.txt:53`.
- **What I observed:** `python3 -m pytest -q` → **12 failed** (11 Celery tests + 1 transient earlier; rerun excluding Celery was clean). `python3 -m pytest -q -k 'not test_celery'` → **1948 passed, 3 skipped, 11 deselected**.
- **Suggested fix:**
  - Make the dev/test harness deterministic: document the required install step (or ship `make test` that creates a venv and installs `requirements.txt`).
  - In CI, run tests in a clean environment that installs `requirements.txt` so “0-fail” is reproducible.
  - If you want “import safety” even without optional deps: gate Celery import behind an explicit feature flag and make the tests enforce “Celery installed when Celery tests run” (but don’t hide real missing-dependency issues in production images).

### HIGH-002 — Test-count claim is stale (1923 vs actual ~1962)
- **Claim:** “1923” URIP tests (Wave 1 status update).
- **Reality:** This repo currently contains ~**1962** collected tests (from the runs above), not 1923.
- **Evidence:** My `pytest` runs reported totals consistent with **1948 passed + 3 skipped + 11 deselected = 1962** (excluding Celery) and **1947 passed + 12 failed + 3 skipped = 1962** (including Celery).
- **Suggested fix:** Don’t publish exact test counts in narrative updates unless you pin them to a command/CI artifact; otherwise say “1900+”.

## 3. Significant findings (fix in next sprint)

### MED-001 — CSPM connectors are “present” but not covered by connector test suite (import-time deps)
- **Claim:** Connectors are “LIVE” and conform to the contract (§5).
- **Reality:** Source-level contract compliance is strong across all 29 connectors, but the connector test suite does not cover the CSPM connector modules (AWS/Azure/GCP). In this runtime, importing `connectors/aws_cspm/connector.py` fails due to missing `boto3`.
- **Evidence:**
  - Contract + metadata contract defined: `connectors/base/connector.py:203` (contract) and `connectors/base/registry.py:41` (required metadata).
  - Requirements explicitly call out boto3 for AWS CSPM + Trust Center S3: `requirements.txt:41`.
  - Connector test directory does not include CSPM connector tests: `tests/test_connectors/` (no `test_aws_cspm.py`, `test_azure_cspm.py`, `test_gcp_cspm.py`).
- **Suggested fix:** Add at least “import + metadata + normalize smoke” tests for the 3 CSPM connectors so “LIVE” has harness coverage and doesn’t regress silently.

### MED-002 — Compliance Alembic config is cwd-sensitive (easy to run wrong migrations)
- **Claim:** Migration chain should be linear and usable.
- **Reality:** `compliance/alembic.ini` is correct only if you run Alembic from the `compliance/` directory; running from repo root points `script_location=alembic` at the *URIP* migrations.
- **Evidence:** `compliance/alembic.ini:6` (“Run from: compliance/ directory”) and `compliance/alembic.ini:9` (`script_location = alembic`).
- **Suggested fix:** Make `script_location` resilient (use `%(here)s/alembic`) so it works from any working directory.

## 4. Cleanup findings (low-priority polish)

### LOW-001 — `storage_uri` redaction is correct but should stay regression-tested
- **Claim:** L2 `storage_uri` leak fixed.
- **Reality:** ✅ Fixed: response schemas omit `storage_uri`, and tests enforce this.
- **Evidence:** `compliance/backend/compliance_backend/routers/evidence.py:44`, `compliance/backend/compliance_backend/routers/vendors.py:94`, `tests/test_audit_low/test_low_fixes.py:95`.
- **Suggested fix:** None; keep the tests.

### LOW-002 — PyJWT migration complete, but docs/comments still mention jose in places
- **Claim:** `python-jose` fully replaced.
- **Reality:** ✅ No `from jose import …` in production code; both services use `jwt` (PyJWT). Some comments reference the old library for historical context.
- **Evidence:** `compliance/backend/compliance_backend/middleware/auth.py:26`, `requirements.txt:23`.
- **Suggested fix:** Optional: prune legacy comments once the migration is “boring”.

## 5. What I actually verified (commands I ran)

- Read audit prompt: `sed -n '1,200p' docs/audit_apr28/AUDIT_PROMPT_SOFT.md`
- Full URIP suite (failed in this runtime): `python3 -m pytest -q`
- URIP suite excluding Celery (clean): `python3 -m pytest -q -k 'not test_celery'`
- Compliance backend suite (clean, 530 tests): `python3 -m pytest -q compliance/backend/tests`
- Connector inventory: `find connectors -maxdepth 2 -type f -name connector.py | sort`
- Alembic heads:
  - URIP: `alembic heads`
  - Compliance (correct cwd): `cd compliance && alembic -c alembic.ini heads`
- Focused source inspections (evidence cited above): `nl -ba <file> | sed -n …`

## 6. Acknowledgements (skipped due to time / environment)

- Did not run a real Celery worker with Redis (no broker in this audit runtime); only assessed code + tests.
- Did not exercise real upstream vendor APIs (all connector validations here are code/tests only).
- Did not fully verify “3 deployment modes” end-to-end (Docker Compose scenarios), only inspected `Dockerfile` install behavior (`Dockerfile:10`).

---

## Score

**90 / 100**

**Why not higher:** the Wave 1 “URIP 1923/0-fail” statement is not reproducible in this runtime (Celery missing), and the exact test-count claim is stale. The core security/contract fixes you called out are real and regression-tested.

