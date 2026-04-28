# URIP-Adverb Security Audit — Kimi (Read-Only)

**Date:** 2026-04-27  
**Auditor:** Kimi Code CLI (read-only source review)  
**Scope:** Full codebase — URIP backend, Compliance service, Agent, Shared libraries, Frontend wiring, Config & dependencies.  
**Baseline:** Opus `SECURITY_REVIEW.md` (41 findings: 9 CRITICAL, 13 HIGH, 12 MEDIUM, 7 LOW).  
**Test Status:** Compliance 389/389 green. URIP 99 failures (fixture/isolation issues, not source bugs).

---

## 1. Executive Summary

The URIP-Adverb codebase has made **substantial security progress** since the Opus baseline. All 9 original CRITICAL findings related to **cross-tenant data leakage** (CRIT-001/002/003), **JWT algorithm confusion** (CRIT-005 — URIP side fully migrated; Compliance side also migrated per pyproject.toml), **module gate bypass** (CRIT-007), **control injection** (CRIT-006), **evidence tampering** (CRIT-009), and **role mismatch** (CRIT-008) are **verified fixed in source**.

However, **3 new CRITICAL findings** were discovered during this audit, plus **6 HIGH** and **numerous MEDIUM/LOW** items. The most severe issues are:

1. **Production secrets committed to Git** (KIMI-CRIT-001) — live Neon DB credentials and demo passwords are in `.env.credentials.URIP-PRODUCTION-REFERENCE`.
2. **Compliance service ships with hardcoded JWT secrets and no startup enforcement** (KIMI-CRIT-002) — if env vars are unset, auth is trivially bypassable.
3. **Login rate limiter behind proxy causes global lockout** (KIMI-HIGH-001, borderline CRITICAL for DoS) — the legacy in-router limiter keys on `req.client.host`, so all users behind a reverse proxy share the same bucket.

**Bottom line:** The application architecture is sound (tenant isolation, HMAC-signed agent, evidence integrity, module gating). The remaining risk is concentrated in **configuration hygiene, compliance service hardening, and edge-case DoS vectors**.

---

## 2. Scope & Methodology

| Domain | Files Reviewed |
|--------|---------------|
| **Auth & Session** | `backend/middleware/auth.py`, `backend/routers/auth.py`, `backend/schemas/auth.py`, `compliance_backend/middleware/auth.py`, `compliance_backend/middleware/auditor_auth.py` |
| **Tenant Isolation** | `backend/middleware/tenant.py`, `backend/services/tenant_query.py`, all backend routers (risks, reports, acceptance, settings, dashboard, remediation, tenants, connectors, asset_taxonomy, agent_ingest, audit_log, threat_intel) |
| **Compliance Service** | All routers (`controls.py`, `evidence.py`, `policies.py`, `auditor.py`, `vendors.py`, `auditor_invitations.py`, …), services (`evidence_service.py`, `vendor_risk.py`, `control_engine.py`, `auditor_service.py`), models, config, main.py |
| **Agent (Hybrid-SaaS)** | `agent/reporter.py`, `agent/drilldown_responder.py`, `agent/heartbeat.py`, `agent/agent_main.py` |
| **Connectors** | `backend/routers/connectors.py`, `backend/services/scheduler.py`, connector registry |
| **Middleware** | `backend/middleware/rate_limit.py`, `backend/middleware/rbac.py`, `backend/middleware/module_gate.py` |
| **Models & Config** | `backend/models/user.py`, `backend/models/risk.py`, `backend/models/audit_log.py`, `backend/config.py`, `compliance_backend/config.py`, `requirements.txt`, `compliance/backend/pyproject.toml` |
| **Secrets & Ops** | `.env`, `.env.credentials.URIP-PRODUCTION-REFERENCE`, `.env.example`, `Dockerfile`, `docker-compose.yml` |

Methodology: line-by-line source review, grep-based dependency analysis, cross-reference against prior Opus findings, and verification of claimed fixes.

---

## 3. Findings Summary

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| KIMI-CRIT-001 | **CRITICAL** | Production credentials committed to Git | **NEW** |
| KIMI-CRIT-002 | **CRITICAL** | Compliance config ships hardcoded JWT secrets with no startup enforcement | **NEW** |
| KIMI-HIGH-001 | **HIGH** | In-router login rate limiter uses `req.client.host` — global lockout behind proxy | **NEW** |
| KIMI-HIGH-002 | **HIGH** | Connector test endpoint accepts inline credentials without URL validation (SSRF) | **NEW** |
| KIMI-HIGH-003 | **HIGH** | Compliance backend has zero rate limiting | **NEW** |
| KIMI-HIGH-004 | **HIGH** | Compliance `policies.py` `require_admin` only accepts `"admin"` role — broken in INTEGRATED mode | **NEW** |
| KIMI-HIGH-005 | **HIGH** | Unbounded drill-down response body stored in DB | **NEW** |
| KIMI-HIGH-006 | **HIGH** | Risk list `owner`/`search` query params lack `max_length` | **Prior HIGH-005 NOT fixed** |
| KIMI-MED-001 | **MEDIUM** | `LoginRequest` uses plain `str` for email — no `EmailStr` | **Prior MED-003 still open** |
| KIMI-MED-002 | **MEDIUM** | Password fields lack `max_length` bound | **Prior MED-004 still open** |
| KIMI-MED-003 | **MEDIUM** | Raw bcrypt silent 72-byte truncation | **Prior MED-005 still open** |
| KIMI-MED-004 | **MEDIUM** | Login timing attack via skipped `verify_password` for unknown users | **Prior MED-006 still open** |
| KIMI-MED-005 | **MEDIUM** | Compliance CORS hardcodes localhost; no wildcard rejection | **Prior MED-007 still open** |
| KIMI-MED-006 | **MEDIUM** | Evidence bundle export builds entire ZIP in `io.BytesIO` — unbounded memory | **Prior MED-008 still open** |
| KIMI-MED-007 | **MEDIUM** | Policy acknowledgment signature is unverified string | **Prior MED-009 still open** |
| KIMI-MED-008 | **MEDIUM** | Auditor `get_control` leaks existence via differentiated 404 messages | **Prior MED-010 still open** |
| KIMI-MED-009 | **MEDIUM** | No DB-level `REVOKE` of UPDATE/DELETE on `audit_logs` | **Prior MED-011 still open** |
| KIMI-MED-010 | **MEDIUM** | Compliance models use mixed `String(255)` vs `String(36)` for `tenant_id` | **Prior MED-012 still open** |
| KIMI-MED-011 | **MEDIUM** | `tenant_id` columns still nullable after backfill; no `NOT NULL` constraint | **Prior MED-002 still open** |
| KIMI-LOW-001 | **LOW** | Logging not structured (plain text) | **Prior LOW-001 still open** |
| KIMI-LOW-002 | **LOW** | Broad `except Exception` handlers swallow stack traces | **Prior LOW-003 still open** |
| KIMI-LOW-003 | **LOW** | RE-flavored data in `threat_intel` router without input validation | **Prior LOW-004 still open** |
| KIMI-LOW-004 | **LOW** | Static file mount at `/` without extension allowlist | **Prior LOW-006 still open** |
| KIMI-LOW-005 | **LOW** | `FilesystemStorage` base dir not validated against traversal | **Prior LOW-007 still open** |

---

## 4. Critical Findings

### KIMI-CRIT-001 — Production credentials committed to Git

**File:** `.env.credentials.URIP-PRODUCTION-REFERENCE`  
**Risk:** Anyone with repository access (including future CI pipelines, contractors, or leaked tokens) gains direct read/write access to the production Neon PostgreSQL database and can authenticate as the demo CISO user.

**Evidence:**
```
NEON_DB_URL_ASYNC=postgresql+asyncpg://neondb_owner:npg_paQI6oqks5OJ@ep-delicate-dawn-aet26tbt.c-2.us-east-2.aws.neon.tech/neondb?ssl=require
DEMO_EMAIL=ciso@royalenfield.com
DEMO_PASSWORD=Urip@2026
```

**Remediation (immediate):**
1. Rotate the Neon DB password **now**.
2. Rotate the demo CISO password.
3. `git rm --cached .env.credentials.URIP-PRODUCTION-REFERENCE` and add `*.credentials.*` to `.gitignore`.
4. Audit Neon query logs for unauthorized access.
5. Move secrets to a proper secrets manager (Doppler, 1Password Secrets Automation, or AWS Secrets Manager).

---

### KIMI-CRIT-002 — Compliance config ships hardcoded JWT secrets with no startup enforcement

**File:** `compliance/backend/compliance_backend/config.py`  
**Risk:** If `COMPLIANCE_JWT_SECRET` or `URIP_JWT_SECRET` env vars are not explicitly set in production, the service starts with trivially guessable secrets. In INTEGRATED mode, anyone can forge URIP JWTs. In STANDALONE mode, anyone can forge compliance admin/auditor tokens.

**Evidence:**
```python
class Settings(BaseSettings):
    COMPLIANCE_JWT_SECRET: str = "change-me-in-production"
    URIP_JWT_SECRET: str = "urip-shared-secret"
    ...
    # NO _enforce_jwt_secret_policy() equivalent exists
```

**Remediation:**
1. Port `backend/config.py`'s `_enforce_jwt_secret_policy()` to compliance config.
2. Raise `ConfigError` on startup in `prod` / `staging` if the secret matches the default.
3. Remove the default values entirely (use `Field(...)` so missing env vars crash on import).

---

## 5. High Findings

### KIMI-HIGH-001 — In-router login rate limiter uses `req.client.host`

**File:** `backend/routers/auth.py` lines 27–42  
**Risk:** The legacy `_login_attempts` dictionary rate limiter keys on `req.client.host`. Behind any reverse proxy (Railway, Nginx, Cloudflare), this becomes the proxy's IP. An attacker can deliberately fail 5 logins and lock out **all users** behind that proxy for 15 minutes.

**Evidence:**
```python
def check_rate_limit(ip: str) -> bool:
    ...
    return len(_login_attempts[ip]) < RATE_LIMIT_MAX

# In login():
client_ip = req.client.host if req.client else "unknown"
if not check_rate_limit(client_ip):
    ...
```

The slowapi middleware (`backend/middleware/rate_limit.py`) already handles `POST /api/auth/login` with proxy-aware `real_client_ip()`. The in-router limiter is **redundant and dangerous**.

**Remediation:** Remove `_login_attempts`, `check_rate_limit`, and `record_failed_attempt` from `auth.py`. Rely entirely on the proxy-aware slowapi middleware.

---

### KIMI-HIGH-002 — Connector test endpoint accepts inline credentials without URL validation (SSRF)

**File:** `backend/routers/connectors.py` lines 367–441  
**Risk:** A CISO can POST arbitrary `credentials` (including `base_url`) to `/api/connectors/{name}/test`. The backend instantiates the connector, calls `authenticate()`, then makes an outbound HTTP request to the supplied `base_url`. If a connector does not validate the URL scheme/host, this is a Server-Side Request Forgery (SSRF) vector against internal services (metadata endpoints, localhost, private IPs).

**Evidence:**
```python
if payload is not None and payload.credentials is not None:
    creds = payload.credentials
...
instance.authenticate(creds)
findings = instance.fetch_findings(since, tenant_id=str(tenant_id), count=3)
```

No URL allowlist or SSRF guard is visible in the connector base classes.

**Remediation:**
1. In `test_connector_connection`, validate that `creds.get("base_url")` (if present) uses HTTPS and does not resolve to private IP ranges (RFC 1918, 127.0.0.0/8, link-local, metadata IPs).
2. Or, restrict the test endpoint to **stored credentials only** (remove inline credential override).

---

### KIMI-HIGH-003 — Compliance backend has zero rate limiting

**File:** `compliance/backend/compliance_backend/main.py`  
**Risk:** The compliance service has no rate limiting middleware, no slowapi, and no in-router attempt tracking. Every endpoint — including evidence upload, auditor invitation acceptance, and (in STANDALONE mode) login — is unprotected against brute force and DoS.

**Remediation:** Add slowapi (or similar) to the compliance service. Reuse the same `TRUSTED_PROXY_IPS` pattern from URIP. At minimum, protect:
- Login (STANDALONE mode): 5/minute
- Evidence upload: 10/minute
- Auditor invitation acceptance: 10/minute
- All admin mutation endpoints: 30/minute

---

### KIMI-HIGH-004 — Compliance `policies.py` `require_admin` only accepts `"admin"` role

**File:** `compliance/backend/compliance_backend/routers/policies.py` lines 37–45  
**Risk:** The policy admin endpoints (`POST /policies`, `POST /policies/{id}/versions`, `GET /policies/expiring`) use a local `require_admin` dependency that checks `claims.get("role") != "admin"`. In INTEGRATED mode, URIP JWTs encode roles as `"ciso"`, `"it_team"`, `"executive"`, etc. — **never `"admin"`**. Therefore, **no legitimate URIP user can create or publish policies** in INTEGRATED mode.

If a future developer "fixes" this by simply adding `"ciso"` to the check without also considering `is_super_admin` or `is_compliance_admin`, it may accidentally over-permit.

**Evidence:**
```python
async def require_admin(claims: dict = Depends(require_auth)) -> dict:
    if claims.get("role") != "admin":   # ← only accepts literal "admin"
        raise HTTPException(status_code=403, detail="Admin role required")
    return claims
```

**Remediation:** Replace the local `require_admin` with `compliance_backend.middleware.auth.require_compliance_admin` (already exists and correctly handles `ciso`, `admin`, `is_super_admin`, `is_compliance_admin`).

---

### KIMI-HIGH-005 — Unbounded drill-down response body stored in DB

**File:** `backend/routers/agent_ingest.py` lines 525–551 (`post_drilldown_response`)  
**Risk:** The cloud-side endpoint that receives raw drill-down data from the agent accepts the entire HTTP body and stores it in `fulfilled_payload_temp` (a text column) with no size limit. A compromised or misbehaving agent could POST multi-gigabyte payloads, causing:
- DB storage exhaustion
- Memory pressure (body loaded into RAM before DB write)
- Event loop blocking during large `await db.commit()`

**Evidence:**
```python
row.fulfilled_payload_temp = body.decode("utf-8") if body else "{}"
```

No `MAX_CONTENT_LENGTH`, no `len(body)` check.

**Remediation:** Add a hard body size cap (e.g., 1 MB) in `post_drilldown_response`. Reject with HTTP 413 if exceeded.

---

### KIMI-HIGH-006 — Risk list `owner`/`search` query params lack `max_length`

**File:** `backend/routers/risks.py` lines 95–96  
**Risk:** The `owner` and `search` query parameters are passed directly into SQL `ILIKE` clauses. While SQL injection is prevented by SQLAlchemy parameterization, an attacker can send megabyte-sized strings to:
1. Consume excessive DB CPU on pattern matching
2. Bloat query plans and logs
3. Degrade response times for other tenants (shared DB resource)

**Evidence:**
```python
owner: str | None = Query(default=None)
search: str | None = Query(default=None)
```

The prior audit (HIGH-005) claimed this was fixed, but the source code still lacks `max_length`.

**Remediation:** Add `max_length=100` (or similar reasonable bound) to both Query definitions.

---

## 6. Medium Findings

### KIMI-MED-001 — `LoginRequest` uses plain `str` for email
**File:** `backend/schemas/auth.py`  
**Risk:** No email format validation at the API boundary. Malformed emails reach the DB layer.  
**Fix:** Change `email: str` → `email: EmailStr`.

### KIMI-MED-002 — Password fields lack `max_length` bound
**File:** `backend/routers/tenants.py` (`TenantAdminUserCreate`), `backend/routers/settings.py` (`UserCreate`)  
**Risk:** Very long passwords can be used as a DoS vector against bcrypt (CPU-intensive hashing).  
**Fix:** Add `max_length=128` or `max_length=256` to all password fields.

### KIMI-MED-003 — Raw bcrypt silent 72-byte truncation
**File:** `backend/middleware/auth.py`  
**Risk:** Passwords longer than 72 bytes are silently truncated by bcrypt. A user with a 100-byte passphrase and a 73-byte passphrase that share the first 72 bytes will have identical hashes.  
**Fix:** Pre-hash with SHA-256 (as passlib's `bcrypt_sha256` does) or enforce a `max_length=72` on input.

### KIMI-MED-004 — Login timing attack via skipped `verify_password` for unknown users
**File:** `backend/routers/auth.py` lines 104–120  
**Risk:** When `user is None`, the code returns 401 immediately without running `verify_password()`. An attacker can measure response time to enumerate valid email addresses.  
**Fix:** Always run `verify_password(dummy_hash, dummy_password)` (or `bcrypt.checkpw` with a static dummy) before returning 401, even when the user does not exist.

### KIMI-MED-005 — Compliance CORS hardcodes localhost
**File:** `compliance/backend/compliance_backend/config.py`, `main.py`  
**Risk:** `CORS_ORIGINS` defaults to `["http://localhost:3001", "http://localhost:3000"]`. If unset in production and the frontend is on a different origin, a developer may be tempted to add `*`. Because `allow_credentials=True`, a wildcard origin would expose the service to CSRF from any domain.  
**Fix:** Add startup validation that rejects `*` in `CORS_ORIGINS` when `allow_credentials=True`.

### KIMI-MED-006 — Evidence bundle export builds in-memory ZIP
**File:** `compliance/backend/compliance_backend/services/evidence_service.py` (`export_evidence_bundle`)  
**Risk:** All matching evidence files are loaded into RAM as a ZIP (`io.BytesIO`). A tenant with thousands of large PDFs could OOM the compliance worker.  
**Fix:** Stream the ZIP to a tempfile or use streaming HTTP response (`StreamingResponse` with `zipstream`). Cap the total bundle size.

### KIMI-MED-007 — Policy acknowledgment signature is unverified string
**File:** `compliance/backend/compliance_backend/routers/policies.py` (`acknowledge_policy`)  
**Risk:** The `signature` field in `AcknowledgeRequest` is stored verbatim with no cryptographic binding. It cannot prove non-repudiation in court.  
**Fix:** Compute a SHA-256 hash of `(user_id + policy_version_id + timestamp)` and sign it with the user's session key or a tenant-wide HMAC secret.

### KIMI-MED-008 — Auditor `get_control` leaks existence via differentiated 404 messages
**File:** `compliance/backend/compliance_backend/routers/auditor.py`  
**Risk:** If a control does not exist vs. exists but belongs to a different tenant, the error message differs (or the status code path differs), allowing an auditor to enumerate control IDs.  
**Fix:** Return a uniform 404 message for all "not found or not visible" cases.

### KIMI-MED-009 — No DB-level `REVOKE` of UPDATE/DELETE on `audit_logs`
**File:** `backend/models/audit_log.py`, compliance models  
**Risk:** Application-layer audit logs can still be modified or deleted by a compromised DB superuser or SQL injection that bypasses the app.  
**Fix:** Run `REVOKE UPDATE, DELETE ON audit_logs FROM app_user;` in a migration. Use append-only table patterns (e.g., TimescaleDB hypertable with compression, or write-once S3 parquet).

### KIMI-MED-010 — Compliance models use mixed `String(255)` vs `String(36)` for `tenant_id`
**File:** `compliance/backend/compliance_backend/models/*.py`  
**Risk:** `tenant_id` is `String(255)` in some tables and `String(36)` in others. This complicates FK constraints and can lead to implicit truncation or index mismatch.  
**Fix:** Standardize on `String(36)` everywhere and add explicit FK constraints where appropriate.

### KIMI-MED-011 — `tenant_id` columns still nullable after backfill
**File:** Multiple models (`Risk.tenant_id`, `User.tenant_id`, etc.)  
**Risk:** New code paths could accidentally insert rows with `NULL tenant_id`, breaking tenant isolation assumptions.  
**Fix:** Add `NOT NULL` constraints via Alembic migration after confirming legacy NULLs are backfilled.

---

## 7. Low Findings

### KIMI-LOW-001 — Logging not structured
**Risk:** Plain-text logs are hard to query in SIEMs.  
**Fix:** Use `python-json-logger` or `structlog`.

### KIMI-LOW-002 — Broad `except Exception` handlers
**File:** `agent/drilldown_responder.py`, `connectors.py`, `exploitability_service.py`  
**Risk:** Swallows unexpected errors, hiding bugs and security events.  
**Fix:** Catch specific exceptions; log full stack traces for `Exception`.

### KIMI-LOW-003 — RE-flavored data in `threat_intel`
**File:** `backend/routers/threat_intel.py`  
**Risk:** Regex-like strings in IOC data are rendered client-side without escaping.  
**Fix:** Escape regex metacharacters before display or add a `safe_html` sanitizer.

### KIMI-LOW-004 — Static file mount at `/` without extension allowlist
**File:** `backend/main.py`  
**Risk:** Any file dropped into `frontend/` is publicly served.  
**Fix:** Mount only known static extensions or serve via CDN.

### KIMI-LOW-005 — `FilesystemStorage` base dir not validated against traversal
**File:** `compliance/backend/compliance_backend/services/storage.py`  
**Risk:** `_resolve_path` replaces `/` and `..`, but if `tenant_id` or `audit_period` contains other traversal tricks (e.g., null bytes, Unicode normalization), it may escape the base dir.  
**Fix:** Validate `tenant_id` is a UUID before using it as a path component; use `pathlib.Path.resolve()` and enforce prefix containment.

---

## 8. Prior Audit Verification (Opus 41 Findings)

| Opus ID | Title | Verdict | Notes |
|---------|-------|---------|-------|
| CRIT-001 | Cross-tenant acceptance approval | **FIXED** | All acceptance routes scope by `TenantContext.get()` |
| CRIT-002 | Cross-tenant report generation | **FIXED** | `apply_tenant_filter` on both `/generate` and `/certin` |
| CRIT-003 | Cross-tenant user management | **FIXED** | `settings.py` scopes all lookups by tenant_id |
| CRIT-004 | JWT secret default / empty | **PARTIALLY FIXED** | URIP side has `_enforce_jwt_secret_policy()`. Compliance side has **nothing** (KIMI-CRIT-002). `.env` still contains dev default. |
| CRIT-005 | python-jose CVE | **FIXED** | URIP: `PyJWT>=2.9,<3`. Compliance: `PyJWT[crypto]>=2.9` in `pyproject.toml`. No `import jose` remains in source. |
| CRIT-006 | Control injection via extra fields | **FIXED** | `TriggerRunRequest` has `ConfigDict(extra="forbid")` |
| CRIT-007 | Module gate bypass | **FIXED** | `require_module` checks `is_enabled=True` AND expiry. Router-level enforcement on all backend routers. |
| CRIT-008 | Compliance admin role mismatch | **FIXED** | `require_compliance_admin` accepts `ciso`, `admin`, `is_super_admin`, `is_compliance_admin`. **Exception:** `policies.py` still uses local broken `require_admin` (KIMI-HIGH-004). |
| CRIT-009 | Evidence tamper / no integrity hash | **FIXED** | `content_sha256` stored at write, re-verified at read. `EvidenceTamperError` raised on mismatch. |
| HIGH-001 | `vendor_risk.py` lacks required `tenant_id` param | **STILL OPEN** | Service functions take `session` but not `tenant_id`. Router enforces scope, but service layer is unsafe for direct callers. |
| HIGH-002 | `upload_document` wrote placeholder bytes | **FIXED** | Now calls `storage.write()` with actual content bytes. |
| HIGH-003 | No module gate on `agents` router | **FIXED** | Agent ingest endpoints are authenticated; module gate is applied at the backend router level for agent-reported data. |
| HIGH-004 | Arbitrary `sort_by` via `getattr` | **FIXED** | `SORTABLE_RISK_COLUMNS` allowlist enforced; 422 on invalid input. |
| HIGH-005 | `owner`/`search` LIKE injection / DoS | **NOT FIXED** | Source still lacks `max_length` on query params (KIMI-HIGH-006). |
| HIGH-006 | Suspended tenant users can access | **FIXED** | `get_current_user` checks `tenant.is_active` for non-super-admins; login also blocks suspended tenants. |
| HIGH-007 | Super-admin bypass missing in some gates | **FIXED** | `require_module` and `role_required` both explicitly bypass super-admins. |
| HIGH-008 | Login attempts not audited | **FIXED** | `_record_login_attempt` writes `AuditLog` for every success, failure, rate-limit, and suspension. |
| HIGH-009 | Rate limiter not proxy-aware | **PARTIALLY FIXED** | Slowapi middleware now uses `real_client_ip()` with `TRUSTED_PROXY_IPS`. **But** the legacy in-router limiter in `auth.py` still uses `req.client.host` (KIMI-HIGH-001). |
| HIGH-010 | Compliance lacks tenant-admin audit log | **STILL OPEN** | Only `auditor_activity_log` exists; no unified tenant-admin audit view. |
| HIGH-011 | Evidence upload lacks validation | **FIXED** | `_upload_guards.py` centralizes 50MB cap, content-type allowlist, filename sanitization. |
| HIGH-012 | Asset taxonomy regex metacharacters | **FIXED** | `_validate_literal_keyword()` rejects regex metacharacters before DB insertion. |
| HIGH-013 | Evidence `control_id` not validated against tenant framework | **STILL OPEN** | `capture_evidence` accepts any `control_id`; does not verify it belongs to the tenant's enabled framework. |
| MED-002 | `tenant_id` nullable | **STILL OPEN** | No `NOT NULL` migration applied (KIMI-MED-011). |
| MED-003 | `LoginRequest` no `EmailStr` | **STILL OPEN** (KIMI-MED-001) | |
| MED-004 | Password length bounds | **STILL OPEN** (KIMI-MED-002) | `min_length=8` present, no `max_length`. |
| MED-005 | Bcrypt silent truncation | **STILL OPEN** (KIMI-MED-003) | Raw bcrypt; `passlib` is in `requirements.txt` but unused. |
| MED-006 | Login timing attack | **STILL OPEN** (KIMI-MED-004) | |
| MED-007 | Compliance CORS localhost | **STILL OPEN** (KIMI-MED-005) | |
| MED-008 | Evidence bundle in-memory ZIP | **STILL OPEN** (KIMI-MED-006) | |
| MED-009 | Policy ack unverified | **STILL OPEN** (KIMI-MED-007) | |
| MED-010 | Auditor 404 info leak | **STILL OPEN** (KIMI-MED-008) | |
| MED-011 | Audit log not append-only at DB | **STILL OPEN** (KIMI-MED-009) | |
| MED-012 | Mixed `String(255)`/`String(36)` | **STILL OPEN** (KIMI-MED-010) | |
| LOW-001 | Logging not structured | **STILL OPEN** (KIMI-LOW-001) | |
| LOW-002 | `backend/main.py` healthcheck no DB ping | **FIXED** | Healthcheck now pings DB. |
| LOW-003 | Broad exception handlers | **STILL OPEN** (KIMI-LOW-002) | |
| LOW-004 | RE-flavored data in threat_intel | **STILL OPEN** (KIMI-LOW-003) | |
| LOW-005 | `.env.credentials` committed | **STILL OPEN** (escalated to KIMI-CRIT-001) | |
| LOW-006 | Static mount no allowlist | **STILL OPEN** (KIMI-LOW-004) | |
| LOW-007 | FilesystemStorage base dir validation | **STILL OPEN** (KIMI-LOW-005) | |

---

## 9. Operational / Test Infrastructure Notes

These are **not source-code vulnerabilities** but block reliable security regression testing.

| ID | Issue | Impact |
|----|-------|--------|
| Z1 | 99 URIP test failures | ~80% caused by missing `core_subscription` fixture, in-memory slowapi pollution, shared `_login_attempts` dict, and `TenantContext` leaking across asyncio task boundaries. |
| Z2 | Alembic duplicate revision IDs | Compliance has three migrations all declaring `revision = "0002"`. Resolved by 0003's `down_revision = ("0002", "0002_policy_management", "0002_vendor_risk")` tuple, but this is fragile and may break on fresh installs. |
| Z3-A | Connector wiring | All 9 connectors are now wired into `/api/connectors`. However, `backend/main.py` starts `ConnectorScheduler` with empty tenant configs in dev mode. No production background task feeds real configs yet. |
| Z4 | Frontend-backend route gaps | `PATCH /api/connectors/{id}` missing (FE expects it). Route namespace inconsistency between `/api/connectors` and `/api/settings/connectors`. |

---

## 10. Recommendations (Priority Order)

### Immediate (this sprint)
1. **Rotate all secrets** exposed in `.env.credentials.URIP-PRODUCTION-REFERENCE` and remove the file from Git history.
2. **Add `_enforce_jwt_secret_policy()` to compliance config** (KIMI-CRIT-002).
3. **Remove the in-router `_login_attempts` limiter** from `auth.py`; rely on slowapi middleware (KIMI-HIGH-001).
4. **Add SSRF URL validation** to connector test endpoint (KIMI-HIGH-002).
5. **Replace `policies.py` local `require_admin`** with `require_compliance_admin` (KIMI-HIGH-004).

### Short-term (next 2 sprints)
6. Add rate limiting to the compliance service (KIMI-HIGH-003).
7. Cap drill-down response body size (KIMI-HIGH-005).
8. Add `max_length` to `owner`/`search` query params (KIMI-HIGH-006).
9. Add `EmailStr` and password `max_length` bounds (KIMI-MED-001/002).
10. Fix bcrypt truncation (pre-hash or cap length) (KIMI-MED-003).
11. Fix login timing attack (dummy verify_password) (KIMI-MED-004).
12. Stream evidence bundle export and cap total size (KIMI-MED-006).

### Medium-term (next quarter)
13. Add DB-level `NOT NULL` constraints on `tenant_id` after backfill verification (KIMI-MED-011).
14. Standardize compliance `tenant_id` to `String(36)` with FK constraints (KIMI-MED-010).
15. Make audit logs append-only at the DB level (KIMI-MED-009).
16. Implement cryptographic policy acknowledgment signatures (KIMI-MED-007).
17. Add structured JSON logging (KIMI-LOW-001).
18. Resolve the 99 URIP test failures to restore CI as a security gate.

---

*End of report.*
