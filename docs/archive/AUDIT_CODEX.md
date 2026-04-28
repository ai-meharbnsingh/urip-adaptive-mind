# URIP-Adverb Security Audit (Codex)

## Verdict
NOT READY FOR PRODUCTION.

## Counts: 3 CRITICAL / 7 HIGH / 7 MEDIUM / 5 LOW

## Critical / High / Medium / Low findings (each with file:line + reproduction + impact + fix)

### CRITICAL

#### CRIT-001 — Compliance JWT secrets default to well-known values; no prod enforcement (token forgery → cross-tenant takeover)
- **File:** `compliance/backend/compliance_backend/config.py:16` (defaults at `:25` and `:26`)
- **Also:** `compliance/backend/compliance_backend/middleware/auth.py:44` (selects secret) and `compliance/backend/compliance_backend/middleware/auth.py:67` (verifies token)
- **Reproduction:**
  1. Run Compliance with defaults (no env vars overriding secrets).
  2. Forge a token using the default secret for the active mode:
     - STANDALONE: sign with `COMPLIANCE_JWT_SECRET` default.
     - INTEGRATED: sign with `URIP_JWT_SECRET` default.
  3. Include any victim `tenant_id` in the token claims and call tenant-scoped routes, e.g. `GET /evidence` or `POST /vendors`.
     - Example (STANDALONE; mints arbitrary tenant access):
       - Create token: `python -c 'import jwt, time; print(jwt.encode({"sub":"attacker","tenant_id":"VICTIM_TENANT","role":"admin","exp":int(time.time())+3600}, "change-me-in-production", algorithm="HS256"))'`
       - Use it: `curl -H "Authorization: Bearer <TOKEN>" http://localhost:8001/evidence`
- **Impact:** Any attacker who can reach the Compliance API can mint valid JWTs and set `tenant_id` to any value, bypassing tenant isolation, authorization, and all auditor/admin gates that rely on claims. This is a full confidentiality + integrity breach across all tenants.
- **Fix:**
  - Remove secret defaults and enforce “must be set” at startup (same pattern as URIP’s `backend/config.py` secret policy).
  - In production-like environments, refuse to start if secrets are empty or match any known dev placeholder.
  - Require and validate standard claims (`exp`, `iss`, and mode-specific `aud`) during decode.

#### CRIT-002 — Evidence bundle export bypasses integrity verification and omits hashes (tamper undetectable in bundle workflow)
- **File:** `compliance/backend/compliance_backend/services/evidence_service.py:344`
- **Reproduction:**
  1. Upload evidence normally via `POST /evidence` (creates `Evidence.content_sha256`).
  2. Modify the stored artifact directly in the filesystem storage location (or any storage backend) after upload.
  3. Download the bundle via `GET /evidence/bundle`.
  4. Observe: bundle is produced successfully and includes the tampered bytes; no integrity error is raised; `manifest.json` does not include `content_sha256`.
- **Impact:** An attacker with storage access (malicious admin, compromised host, compromised bucket credentials) can silently alter evidence and still produce a “valid” bundle for auditor handoff. This breaks evidence integrity and non-repudiation guarantees for the primary offline export path.
- **Fix:**
  - During export, verify each artifact against `Evidence.content_sha256` (reuse `get_evidence_content()` which already performs the check).
  - Include `content_sha256` in `manifest.json` for every record.
  - Fail closed on hash mismatch (surface as explicit error to caller).

#### CRIT-003 — Default URIP docker-compose deploys with known JWT secret (super-admin token forgery)
- **File:** `.env:6` (sets dev env), `.env:11` (known JWT secret), `docker-compose.yml:28` (loads `.env`)
- **Reproduction:**
  1. Deploy using the repo’s `docker-compose.yml` unchanged.
  2. Forge an URIP JWT signed with the configured secret in `.env`.
     - Example: `python -c 'import jwt, time; print(jwt.encode({"sub":"00000000-0000-0000-0000-000000000000","role":"ciso","tenant_id":"00000000-0000-0000-0000-000000000000","is_super_admin":True,"exp":int(time.time())+3600}, "urip-dev-secret-change-in-production", algorithm="HS256"))'`
  3. Call any admin-only URIP route with `Authorization: Bearer <TOKEN>`.
- **Impact:** The “default deployment path” is remotely compromiseable by token forgery. This yields full platform compromise (including cross-tenant admin actions) if the service is exposed.
- **Fix:**
  - Remove `.env` from any production deployment artifact and require secret injection via your production secret manager.
  - Force `URIP_ENV=production` in any non-local compose/helm chart and refuse to start if `JWT_SECRET_KEY` is the dev default.
  - Add a hard “production guard” that checks both `URIP_ENV` and whether the host is running in a production deployment mode (e.g., `DEPLOYMENT_ENV` or `ALLOW_DEV_DEFAULTS=false`).

---

### HIGH

#### HIGH-001 — Tenant agent license key stored in plaintext (DB compromise → agent impersonation)
- **File:** `backend/models/tenant.py:42`
- **Reproduction:**
  1. Obtain DB read access (backup leak, SQL injection elsewhere, insider).
  2. Read `tenants.license_key`.
  3. Call `POST /api/agent-ingest/register` with `tenant_slug` + stolen `license_key` to obtain a fresh shared secret and impersonate the agent.
- **Impact:** A DB read compromise becomes an agent-auth compromise, enabling forged agent metadata uploads and drilldown responses for the tenant.
- **Fix:** Store only a salted hash of the license key (e.g., `sha256(salt || key)` or a password hash), compare hashes in constant time, and never persist the plaintext key.

#### HIGH-002 — Hybrid-SaaS drilldown SSE endpoint is unbounded and DB-polling (easy authenticated DoS)
- **File:** `backend/routers/agent_ingest.py:557` (SSE stream polls DB at `:575`–`:599`)
- **Also:** `backend/middleware/rate_limit.py:119` (no rate limit policy for `GET /api/agent-ingest/*`, only `/api/auth/me`)
- **Reproduction:**
  1. Authenticate as any tenant user.
  2. Open many parallel connections to `GET /api/agent-ingest/drilldown-stream/{token}` (valid or invalid tokens still incur DB queries until termination).
  3. Each connection polls the DB every 0.5 seconds for up to 90 seconds.
- **Impact:** A single tenant user can drive sustained DB load and connection pressure, degrading availability for the entire URIP service.
- **Fix:** Add explicit rate limits for `GET /api/agent-ingest/drilldown-stream/` and `POST /api/agent-ingest/drilldown-request`, and replace per-connection DB polling with a push mechanism or shared fan-out (or at least exponential backoff + server-side connection caps).

#### HIGH-003 — `shared/` still declares `python-jose` dependency (known CVEs; supply-chain risk)
- **File:** `shared/pyproject.toml:11`
- **Reproduction:** Install `urip-shared` as declared; dependency resolution pulls `python-jose[cryptography]>=3.3.0` even though the codebase migrated to PyJWT in other places.
- **Impact:** Vulnerable/unmaintained JWT/JWE library remains in the dependency closure, increasing attack surface and audit/compliance risk.
- **Fix:** Remove `python-jose` from `shared/` dependencies and pin to `PyJWT[crypto]` (or remove JWT deps entirely from `shared/` if not required).

#### HIGH-004 — Policy acknowledgments are not non-repudiable (signature is attacker-controlled string)
- **File:** `compliance/backend/compliance_backend/models/policy.py:148`, `compliance/backend/compliance_backend/services/policy_manager.py:99`, `compliance/backend/compliance_backend/routers/policies.py:92`
- **Reproduction:**
  1. Call `POST /policies/{id}/acknowledge` with any `signature` string (e.g., `"ok"`).
  2. Later, mutate policy content by publishing a new version or (worse) DB-side edits; acknowledgments do not bind to a content hash or server-derived signature.
- **Impact:** The system cannot prove what content was acknowledged at the time of acknowledgment. This breaks policy non-repudiation and weakens audit defensibility.
- **Fix:** Store `policy_version_content_sha256`, `ip_address`, `user_agent`, and a server-derived HMAC signature over `(tenant_id, user_id, policy_version_id, content_hash, acknowledged_at)`; reject acknowledgments that do not include required fields.

#### HIGH-005 — “No raw findings leave the agent” is enforced via a brittle denylist (easy to leak sensitive fields not listed)
- **File:** `agent/reporter.py:37` and `backend/routers/agent_ingest.py:79`
- **Reproduction:** Send metadata containing sensitive identifiers under non-denylisted keys (e.g., `{"host":"prod-db-01","email":"alice@example.com"}`); denylist does not catch these.
- **Impact:** The core Hybrid-SaaS confidentiality guarantee can be violated by connector payload shape changes, developer mistakes, or adversarial payload construction, without triggering protections.
- **Fix:** Replace denylist scanning with an explicit allowlist schema for metadata payloads (Pydantic models that reject unknown keys), plus server-side size limits and structured validation.

#### HIGH-006 — Evidence bundle export is in-memory with no size/rate controls (authenticated memory exhaustion)
- **File:** `compliance/backend/compliance_backend/services/evidence_service.py:378`
- **Reproduction:** Upload many large artifacts (up to the per-upload cap), then call `GET /evidence/bundle` repeatedly; the service builds the entire ZIP in `io.BytesIO`.
- **Impact:** A tenant user can exhaust RAM/CPU and degrade or crash the Compliance service.
- **Fix:** Stream ZIP responses (e.g., `StreamingResponse`) or generate bundles asynchronously with stored artifacts and signed download URLs; add rate limiting for bundle endpoints.

#### HIGH-007 — URIP login rate limiting uses peer IP and global process memory (proxy/global lockout DoS)
- **File:** `backend/routers/auth.py:28` (global dict) and `backend/routers/auth.py:81` (uses `req.client.host`)
- **Reproduction:** Run URIP behind a reverse proxy; make 5 bad login attempts from any client → the proxy IP’s bucket is exhausted → all users behind that proxy get locked out for 15 minutes.
- **Impact:** Auth availability is attacker-controlled in common deployments (reverse proxy / load balancer), enabling easy global lockout. Also duplicates the middleware limiter with inconsistent semantics.
- **Fix:** Remove the in-router limiter and rely on `backend/middleware/rate_limit.py` (trusted-proxy aware). If a second limiter is required, key it on the same `real_client_ip()` logic and use a shared backend (Redis) rather than a process-global dict.

---

### MEDIUM

#### MED-001 — Agent request “anti-replay” is timestamp-only (replay within window accepted)
- **File:** `backend/routers/agent_ingest.py:158`
- **Reproduction:** Capture a signed request (e.g., metadata push) and replay it within ±300 seconds; signature remains valid and the request is accepted.
- **Impact:** Enables duplicate snapshot insertion and operational confusion; increases blast radius of any network-level capture within a short window.
- **Fix:** Add nonce/jti (unique request id) and store seen nonces per tenant for the replay window; reject duplicates.

#### MED-002 — Pending drilldown request queue can be starved by expired rows (availability bug)
- **File:** `backend/routers/agent_ingest.py:498`
- **Reproduction:**
  1. Create >50 drilldown requests and let them expire.
  2. Agent polls `GET /api/agent-ingest/pending-requests`.
  3. Query returns only the first 50 unfulfilled rows (expired), then filters them out in response; valid newer requests can be hidden indefinitely.
- **Impact:** Tenant drilldown stops working until manual cleanup; authenticated users can self-DoS drilldown functionality.
- **Fix:** Filter `expires_at > now()` in the DB query before applying `.limit(50)`, and/or periodically purge expired unfulfilled rows.

#### MED-003 — Compliance tenant_id is unconstrained string in evidence records (type drift; weak isolation invariants)
- **File:** `compliance/backend/compliance_backend/models/evidence.py:53`
- **Reproduction:** In STANDALONE mode, mint tokens with arbitrary `tenant_id` strings (including whitespace variants) and create/read evidence; inconsistent tenant_id formats can create “shadow tenants” and complicate enforcement.
- **Impact:** Tenant boundary invariants become brittle (string normalization, mismatch bugs, orphaned data). This is not an immediate exploit by itself, but it increases the probability of isolation failures over time.
- **Fix:** Standardize tenant_id to UUID string (`String(36)`), validate format at auth boundary, and add DB constraints (UUID-format CHECK or FK to a tenant registry in standalone mode).

#### MED-004 — URIP serves entire `frontend/` directory, including `.vercel` metadata
- **File:** `backend/main.py:121` and `frontend/.vercel/project.json:1`
- **Reproduction:** Request `GET /.vercel/project.json` from the URIP host (served by StaticFiles).
- **Impact:** Leaks Vercel project/org identifiers and any other accidentally-shipped frontend artifacts, increasing phishing/account takeover and environment fingerprinting risk.
- **Fix:** Exclude dot-directories and deployment metadata from runtime static assets; denylist dotfiles at the static server layer; build a dedicated dist folder for public assets.

#### MED-005 — Rate limiting fails open on storage backend errors (protection drops during Redis outages)
- **File:** `backend/middleware/rate_limit.py:171`
- **Reproduction:** Misconfigure or disrupt the limiter storage backend; middleware logs a warning and proceeds without rate limiting.
- **Impact:** During partial outages, the system becomes brute-forceable and more DoS-prone precisely when under stress.
- **Fix:** Prefer fail-closed (429) for high-risk endpoints (`/api/auth/login`), or implement a local fallback limiter for outage mode.

#### MED-006 — Compliance CORS allows credentials with environment-controlled origins; no production guardrails
- **File:** `compliance/backend/compliance_backend/main.py:48`
- **Reproduction:** Set `CORS_ORIGINS` to an overly broad set (or include `*` depending on Starlette behavior) and run the service; cookies/credentials may be sent cross-origin.
- **Impact:** Misconfiguration can expose authenticated endpoints to unwanted origins.
- **Fix:** Add startup validation that refuses unsafe CORS configs in production-like environments; document allowed origins explicitly per environment.

#### MED-007 — Auditor invitation tokens are redeemable repeatedly until expiry/revocation (token leakage amplification)
- **File:** `compliance/backend/compliance_backend/services/auditor_service.py:167`
- **Reproduction:** Re-use the same invitation token multiple times; each redemption yields a new auditor JWT until the invitation expires or is revoked.
- **Impact:** If an invitation token leaks (email forwarding, logs, browser history), an attacker can mint new auditor JWTs repeatedly without detection until revocation.
- **Fix:** Enforce single-use redemption (invalidate token hash after first accept) or add binding (IP/device fingerprint) plus strict audit logging on every redemption.

---

### LOW

#### LOW-001 — Threat intel “simulated hits” ships customer-specific/legacy IOCs (information disclosure to all tenants)
- **File:** `backend/routers/threat_intel.py:117`
- **Reproduction:** Call `GET /api/threat-intel/iocs/match`; observe hardcoded IPs/domains in responses.
- **Impact:** Leaks legacy customer/engagement artifacts; undermines tenant confidentiality expectations.
- **Fix:** Remove customer-specific literals; generate tenant-local synthetic data or gate simulation behind an explicit demo flag.

#### LOW-002 — Upload allowlist trusts client-supplied `Content-Type` (no sniffing; limited hardening)
- **File:** `compliance/backend/compliance_backend/routers/_upload_guards.py:110`
- **Reproduction:** Upload non-PNG bytes with `Content-Type: image/png`; validation passes.
- **Impact:** Low direct risk because downloads are forced as attachments, but it weakens file-type guarantees and complicates downstream scanning/handling.
- **Fix:** Add lightweight magic-byte sniffing for common types and set `X-Content-Type-Options: nosniff` on downloads.

#### LOW-003 — Audit log enrichment queries users without tenant filter (defensive hardening)
- **File:** `backend/routers/audit_log.py:78`
- **Reproduction:** Requires prior data corruption (audit log row referencing a user_id from another tenant); enrichment query would load that user.
- **Impact:** Low likelihood exploit path, but violates strict “always tenant-scope” discipline.
- **Fix:** Add `User.tenant_id == TenantContext.get()` to the enrichment query (or join through tenant-scoped audit rows).

#### LOW-004 — JWT claim hardening gaps (no `iss`/`aud` verification; exp not required)
- **File:** `backend/middleware/auth.py:58`, `shared/auth/jwt_verifier.py:56`, `compliance/backend/compliance_backend/middleware/auth.py:67`
- **Reproduction:** If an attacker can sign tokens (e.g., due to secret compromise), tokens without `exp` are accepted; issuer/audience are not constrained.
- **Impact:** Increases blast radius of any secret compromise and complicates multi-environment separation.
- **Fix:** Require `exp`, set and validate `iss`/`aud`, and consider key rotation with `kid` support.

#### LOW-005 — Global “email already registered” leaks cross-tenant user existence to tenant CISO
- **File:** `backend/routers/settings.py:103`
- **Reproduction:** As a tenant CISO, attempt to create a user with an email used by another tenant; endpoint returns 409.
- **Impact:** Small cross-tenant information leak (user enumeration by privileged tenant users).
- **Fix:** Make email uniqueness tenant-scoped or return a generic “cannot create user” without confirming existence.

## Domain matrix (A-M)

| Domain | Status | Findings |
|---|---:|---|
| A) Tenant isolation | FAIL | CRIT-001, MED-003, LOW-003, LOW-005 |
| B) Authentication & JWT (PyJWT) | FAIL | CRIT-001, CRIT-003, LOW-004 |
| C) Authorization (RBAC + module gate) | PARTIAL | CRIT-001 (claim-forgery bypass), HIGH-007 (auth availability), HIGH-004 (non-repudiation impacts admin workflows) |
| D) SQL injection / ORM safety | PASS (no exploit found) | (No runtime SQLi found; seed scripts use `text(f"...{table}...")` with fixed table lists.) |
| E) Secret handling | FAIL | CRIT-001, CRIT-003, HIGH-001, MED-004 |
| F) File upload / evidence storage | FAIL | CRIT-002, HIGH-006, LOW-002 |
| G) Audit trail completeness | PARTIAL | LOW-003 (defensive), HIGH-007 (login limiter/audit interaction) |
| H) Rate limiting / DoS | FAIL | HIGH-002, HIGH-006, HIGH-007, MED-005 |
| I) CORS / CSRF | PARTIAL | MED-006 (guardrails missing) |
| J) Dependency security | FAIL | HIGH-003 |
| K) Compliance auditor portal + evidence integrity hash + policy non-repudiation | FAIL | CRIT-002, HIGH-004, MED-007 |
| L) Hybrid-SaaS agent (HMAC, anti-replay, no-raw-findings, drilldown tokens) | FAIL | HIGH-001, HIGH-002, HIGH-005, MED-001, MED-002 |
| M) Code quality smells | PARTIAL | LOW-001, HIGH-007 |

