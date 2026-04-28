# URIP-Adverb Security Review

**Date:** 2026-04-27
**Reviewer:** Opus security agent (read-only)
**Scope:** Backend (URIP `backend/`), Compliance Service (`compliance/backend/compliance_backend/`), Shared (`shared/auth/`, `shared/tenant/`), Connectors framework (`connectors/base/`)
**Verdict:** **NOT READY FOR PRODUCTION.** Multiple CRITICAL cross-tenant data leaks; vulnerable JWT library; weak default secrets shipped in `.env`; evidence integrity unverifiable.

---

## Executive Summary

**41 findings:** **9 critical**, **13 high**, **12 medium**, **7 low**.

The biggest exposures are (1) entire production routers with **no tenant filtering at all** (URIP `acceptance.py`, `reports.py`, `settings.py`, `compliance score snapshot`/`policies pending`/`vendor risk score` endpoints, etc.), (2) the project ships with a hardcoded JWT secret string `"urip-dev-secret-change-in-production"` as both code default AND committed `.env`, (3) `python-jose==3.3.0` is in active CVE — algorithm-confusion + DoS, (4) the **`POST /controls/{id}/run` endpoint lets the caller supply `tenant_config` and `connector_data` from the request body**, meaning a tenant can manufacture a passing audit run, (5) **evidence storage has no integrity hash, so on-disk artifacts can be silently tampered with** before an external auditor downloads them.

The auditor portal is the strongest part of the system (time/framework/tenant bound, server-side revocation re-checked per request, activity logged) but ships alongside admin endpoints whose role check is just `claims.get("role") in {"admin", "owner", "compliance_admin"}` — none of those roles exist in URIP's `ROLE_HIERARCHY` (which only knows `board`/`executive`/`it_team`/`ciso`), so in INTEGRATED mode every URIP login can call the "admin"-gated compliance routes because the gate never matches.

---

## Critical Findings (must fix before any deployment)

### CRIT-001: Cross-tenant data leak — `backend/routers/acceptance.py` has no tenant filter on any query
- **File:** `backend/routers/acceptance.py:38-215` (every endpoint)
- **Issue:** `list_acceptance_requests`, `create_acceptance_request`, `approve_acceptance`, `reject_acceptance` query `AcceptanceRequest`, `Risk`, and `User` tables without ANY `tenant_id` filter:
  - L44 `query = select(AcceptanceRequest)` — returns rows from every tenant.
  - L92 `select(Risk).where(Risk.risk_id == data.risk_id)` — risk_id is unique only per-tenant in practice; you can fetch any tenant's risk by string-guessing.
  - L153, L196 `select(AcceptanceRequest).where(AcceptanceRequest.id == ...)` — CISO of tenant A can approve/reject acceptance requests of tenant B.
  - L56-60 batch-fetch of `Risk` and `User` by ID with NO tenant filter — leaks names of users across tenants.
- **Reproduction:** Auth as tenant-A CISO; call `POST /api/acceptance/{tenant-B-acceptance-id}/approve` → succeeds.
- **Impact:** Total cross-tenant data leak + cross-tenant write. Any authenticated CISO can approve every other tenant's risk acceptances.
- **Fix:** Wrap every `select(...)` with `apply_tenant_filter(query, AcceptanceRequest)` (and similarly for Risk/User), and ensure `acceptance` model has `tenant_id` (it does — it's just unused). On `create_acceptance_request`, filter risk lookup by `Risk.tenant_id == TenantContext.get()`.

### CRIT-002: Cross-tenant data leak — `backend/routers/reports.py` generates reports across all tenants
- **File:** `backend/routers/reports.py:18-171`
- **Issue:** `POST /api/reports/generate` (L18) and `GET /api/reports/certin` (L148) query `Risk` with no tenant filter. The Excel/PDF returned to caller contains **every tenant's risks**.
- **Reproduction:** Auth as any tenant user → `POST /api/reports/generate {"report_type":"board","format":"pdf"}` → PDF lists rows for every tenant in the database.
- **Impact:** Catastrophic data leak: a single low-privileged user (anyone passing `get_current_user`) can exfiltrate the entire risk register of every customer.
- **Fix:** Add `query = apply_tenant_filter(query, Risk)` at L25 and L154; gate generate behind `role_required("ciso")` or at minimum `it_team`.

### CRIT-003: Cross-tenant user enumeration & cross-tenant user mutation — `backend/routers/settings.py`
- **File:** `backend/routers/settings.py:34-108, 121-167, 190-209`
- **Issue:**
  - `GET /api/settings/users` (L34) returns ALL users system-wide — no `User.tenant_id` filter.
  - `POST /api/settings/users` (L55) creates users **without** stamping `tenant_id`, leaving them orphan/global.
  - `PATCH /api/settings/users/{user_id}` (L86) mutates any user globally — tenant A's CISO can promote tenant B's user to a different role, or `is_active=False` to deactivate them.
  - `GET/POST /api/settings/connectors` (L121, L143) operate on `ConnectorConfig` globally — no tenant filter; created connectors have no `tenant_id`.
  - `POST /api/settings/connectors/{id}/test` (L190) accepts any connector_id across tenants.
- **Impact:** Cross-tenant privilege escalation (tenant A's CISO disables tenant B's CISO; promotes anyone), cross-tenant credential theft (read connector config from any tenant), full PII leak (every user email + role across every tenant).
- **Fix:** Add `User.tenant_id == TenantContext.get()` to every query; on create, set `tenant_id=TenantContext.get()`; on `update_user`, after fetching, verify `user.tenant_id == TenantContext.get()` and 404 otherwise. Same for ConnectorConfig.

### CRIT-004: Default JWT secret is hardcoded, committed in `.env`, and identical in both code default and config — trivially forgeable tokens
- **Files:** `backend/config.py:8`, `.env:5`, `.env.example:3`
- **Issue:** `JWT_SECRET_KEY: str = "urip-dev-secret-change-in-production"` is the default. The committed `.env` (in cwd, but `.env` is gitignored — so each dev's local `.env` likely has the same string) and `.env.example` both contain the same literal. If env var unset, the *default* in code is used — the literal `"urip-dev-secret-change-in-production"`. Anyone who has read this repo (or the ADVERB_BLUEPRINT.md, or this audit) can mint valid `is_super_admin: true` JWTs.
- **Impact:** Total auth bypass. Forged JWT with `is_super_admin: True` bypasses tenant filter (`get_current_user` lines 70-75 will not require tenant_id) AND bypasses every `require_module` gate AND every `require_super_admin` check — full platform admin from any unauthenticated attacker.
- **Reproduction:** `python -c 'from jose import jwt; print(jwt.encode({"sub":"00000000-0000-0000-0000-000000000000","role":"ciso","is_super_admin":True,"exp":9999999999}, "urip-dev-secret-change-in-production", algorithm="HS256"))'`
- **Fix:**
  1. Remove the default literal from `backend/config.py` — make `JWT_SECRET_KEY` a required field with no default; raise on startup if blank.
  2. Add a startup assertion in `backend/main.py`: `assert settings.JWT_SECRET_KEY not in {"", "urip-dev-secret-change-in-production"}`.
  3. Same fix for `compliance/backend/compliance_backend/config.py:25` (`COMPLIANCE_JWT_SECRET = "change-me-in-production"`) and `:26` (`URIP_JWT_SECRET = "urip-shared-secret"`).
  4. Rotate any production-issued JWTs.

### CRIT-005: `python-jose 3.3.0` — algorithm confusion + DoS CVE
- **Files:** `requirements.txt:15`, `compliance/backend/pyproject.toml:18`
- **Issue:** `python-jose[cryptography]==3.3.0` (URIP) and `python-jose>=3.3.0` (compliance). Known CVEs:
  - **CVE-2024-33663** (HIGH) — algorithm confusion: an attacker can bypass HS256 verification by signing a token with a different algorithm.
  - **CVE-2024-33664** (MEDIUM) — DoS via crafted JWE with extreme `p2c` value, hangs server.
  - The library is essentially unmaintained (last release 2021).
- **Impact:** Combined with CRIT-004's known secret OR with any leaked HS256 secret, attacker can mint tokens. Algorithm-confusion path: in environments where any RS256 public key is reachable, attacker can sign tokens using HS256 with the public key as the secret.
- **Fix:** Replace `python-jose` with `pyjwt[crypto]` everywhere. Update `decode_token` in `backend/middleware/auth.py:39-46` and `compliance_backend/middleware/auth.py:42-52` and `compliance_backend/middleware/auditor_auth.py:74-91` and `shared/auth/jwt_verifier.py:50-54` to PyJWT API and pin `algorithms=["HS256"]` on every decode (already done — but on the vulnerable lib).

### CRIT-006: Audit integrity — `POST /controls/{id}/run` lets the caller supply the inputs that determine pass/fail
- **File:** `compliance/backend/compliance_backend/routers/controls.py:127-155`
- **Issue:** The body schema `TriggerRunRequest` (L52-56) accepts `tenant_config: Optional[dict]` and `connector_data: Optional[dict]`. These are passed straight through `engine.run_control()` to the rule's `check()` method (`control_engine.py:122-130`). A tenant admin can therefore supply favourable inputs (e.g. `mfa_enforced: True`) and produce a passing `ControlCheckRun` row that is then auto-attached as evidence and influences the compliance score.
- **Impact:** Compliance fraud — tenant can manufacture a passing audit posture. This invalidates the entire purpose of automated controls and the score that auditors rely on. SOC2 / ISO27001 non-repudiation is broken.
- **Fix:** Remove `tenant_config` and `connector_data` from the request body. Require the engine to fetch them from server-side sources only (tenant settings table, connector service). At minimum, log a warning + tag the run with `provenance="caller-supplied"` and exclude such runs from compliance score and from auditor exports.

### CRIT-007: Module gate is only applied to ONE endpoint — gate is effectively absent
- **Files:** `backend/routers/risks.py:71` is the *only* use of `require_module(...)` in the backend.
- **Issue:** `create_risk`, `update_risk`, `assign_risk`, dashboard KPIs, dashboard charts/alerts, reports, acceptance, remediation, audit-log, threat-intel, asset-taxonomy — none of these are gated by their respective module subscription. A tenant whose only active subscription is `CORE` can call every "VM" endpoint except the list endpoint by calling `POST /api/risks` directly. They can run reports, view dashboard KPIs, etc.
- **Impact:** Module-based monetisation is non-existent in practice. Customers pay for tiers they can already use. Worse: a "CORE only" tenant can populate the risk register and have it appear in the (also-ungated) dashboard.
- **Fix:** Add `Depends(require_module("VM"))` (or correct module) to *every* router function that operates on module-scoped data. Audit every route in `backend/routers/` against the `MODULE_CODES` map.

### CRIT-008: Compliance "admin" role gate matches roles that don't exist — admin endpoints accessible by NO ONE in INTEGRATED mode
- **Files:**
  - `compliance/backend/compliance_backend/routers/auditor_invitations.py:76-81`
  - `compliance/backend/compliance_backend/routers/admin_evidence_requests.py:41-46`
  - `compliance/backend/compliance_backend/routers/admin_auditor_activity.py:36-41`
  - `compliance/backend/compliance_backend/routers/compliance_score.py:79-84`
  - `compliance/backend/compliance_backend/routers/policies.py:36-44`
- **Issue:** `_require_admin(claims)` checks `claims.get("role") in {"admin", "owner", "compliance_admin"}`. URIP only mints JWTs with `role` in `{"ciso","it_team","executive","board"}` (`backend/middleware/auth.py:26-36`, `backend/middleware/rbac.py:6-11`). In INTEGRATED mode (URIP's JWT verified by Compliance), the admin gate **never** passes — admin endpoints are unreachable. In STANDALONE mode, no user creation path exists (compliance has no `users` table or sign-up); the admin gate also never passes.
- **Impact:** Either (a) compliance is unusable (admin can never invite an auditor, fulfil evidence requests, or trigger snapshots), OR (b) someone will "fix" this by adding `"ciso"` to the allow-list, in which case **every CISO of every tenant becomes auditor-portal admin and policy admin**, with no further check. The current state is also inconsistent: `policies.py:39` requires only `"admin"` (not the wider set) — so a ciso who can pass _require_admin in one router still can't publish policies in another.
- **Fix:** Standardise the role model across the two services. Decide on a canonical set (e.g. `ciso` is admin) and use a single helper. Document the contract. Verify policy publish, auditor invitation create, evidence request fulfil, snapshot trigger all route through the same guard.

### CRIT-009: Evidence files have no integrity hash — auditor cannot detect tampering
- **Files:** `compliance/backend/compliance_backend/models/evidence.py:31-72`, `compliance/backend/compliance_backend/services/storage.py:127-148`, `compliance/backend/compliance_backend/services/evidence_service.py:70-188`
- **Issue:** When evidence is captured, only `storage_uri` is stored in the DB. There is no `sha256_digest`, `signed_at`, or signature column. The on-disk file (`FilesystemStorage` writes plain bytes to a tenant-keyed path) is mutable by anyone with filesystem access (admin, sysadmin, infra automation, or an attacker who pivots in). When an external auditor calls `GET /auditor/evidence/{id}/download`, they receive whatever is at the URI — with no way to verify the bytes match what was originally captured.
- **Impact:** A tenant can replace incriminating evidence (e.g. an actual MFA-disabled config) with a fabricated passing screenshot before audit handoff. Compliance non-repudiation is broken; this likely fails SOC2 CC7.2 / ISO 27001 A.12.4.
- **Fix:**
  1. Add `sha256_digest: str` and `byte_size: int` columns to `Evidence`. Populate at write time. Verify on read (and on bundle export); raise on mismatch.
  2. Store an HMAC of the digest using a server-side key in a tamper-evident log (or write the digest to an append-only audit log).
  3. (Long-term) Sign evidence at capture time with a per-tenant key (e.g. KMS-issued) and include the signature in the bundle.

---

## High Findings

### HIGH-001: Vendor risk service has no tenant-scoped lookups — cross-tenant vendor mutation
- **File:** `compliance/backend/compliance_backend/services/vendor_risk.py:78-93, 96-123, 164-235`
- **Issue:**
  - `record_response()` (L78) loads `VendorQuestionnaire` by id without joining `Vendor` or filtering by `tenant_id`.
  - `upload_document()` (L96) takes `vendor_id` from the request and accepts any value — caller could upload documents to another tenant's vendor (the calling router checks vendor ownership, but the service is now reusable and unsafe).
  - `calculate_risk_score()` (L164) looks up vendor by id only — no tenant filter. The router enforces tenant scope by pre-fetching vendor first, but the service is one parameter swap from cross-tenant write.
- **Fix:** Make `tenant_id` a required parameter on every service function and `WHERE` it in the query. Don't rely on the router to do scoping for a service.

### HIGH-002: Vendor document upload silently drops the file
- **File:** `compliance/backend/compliance_backend/services/vendor_risk.py:96-123`
- **Issue:** `upload_document` builds `storage_uri = f"memory://vendor_documents/{vendor_id}/...{filename}"` but never actually writes the file content anywhere. The DB row is created with a non-functional URI; the bytes are lost.
- **Impact:** Compliance evidence (DPA, SOC2 reports, insurance certificates) appears uploaded but is unrecoverable for audit. Vendor risk score is computed against a "valid document exists" check which is now satisfied by an empty husk.
- **Fix:** Use the `Storage` abstraction (same as `EvidenceService`); persist bytes; validate content_type whitelist; cap size; sha256 + size on the DB row.

### HIGH-003: Auditor invitation token has weak guarantees — multi-use, no logout, no IP binding
- **Files:** `compliance/backend/compliance_backend/routers/auditor_invitations.py:152-175`, `compliance/backend/compliance_backend/services/auditor_service.py:131-156`
- **Issue:** The "accept" endpoint can be called repeatedly with the same token (the comment at L13-16 calls this a feature). On every call a fresh JWT is minted. Two implications:
  1. There is no single-use semantics; if the invitation URL is leaked (email forward, screenshot in a ticket), the leaker AND the original recipient can both redeem.
  2. The minted JWT has no logout/revocation list — it remains valid until `expires_at`. Revoking the `AuditorAccess` row stops the per-request `get_active_access` check, which IS good (so revoke works), but the token itself is still on its expiry timer.
- **Fix:** (a) For typical use, single-use with `accepted_at IS NULL` check then set; provide an explicit "regenerate token" admin action. (b) Bind the token to client IP or fingerprint (defence-in-depth). (c) Reduce token lifetime materially.

### HIGH-004: `risks.py` `sort_by` accepts arbitrary attribute names — info disclosure & potential crash
- **File:** `backend/routers/risks.py:106`
- **Issue:** `sort_col = getattr(Risk, sort_by, Risk.cvss_score)` — caller supplies `sort_by` as a query param. Any attribute on the Risk class can be addressed; non-column attributes (e.g. `__tablename__`) will cause an `AttributeError` on `.desc()` → 500. Worse, a sort by an internal column (`tenant_id`) leaks the order in which tenants are stored.
- **Fix:** Whitelist allowed sort fields: `if sort_by not in {"composite_score","cvss_score","severity","created_at","updated_at"}: sort_by = "composite_score"`.

### HIGH-005: Search/filter parameters have no length cap — DoS via `%` LIKE blowup
- **File:** `backend/routers/risks.py:94-100`
- **Issue:** `Risk.owner_team.ilike(f"%{owner}%")` and `Risk.finding.ilike(f"%{search}%")` with raw user input. Sending `search=%%%%%%%%%%%%%%%%%%%%%%%` (or a 10MB string) forces a pathological pattern across every row.
- **Fix:** Add `max_length=100` to the Query() definition and reject if input contains only wildcard characters.

### HIGH-006: Tenant `is_active` is never checked on auth — deactivated tenants can still log in
- **Files:** `backend/middleware/auth.py:49-81`, `backend/routers/auth.py:34-83`
- **Issue:** `Tenant.is_active` exists and is settable via `PATCH /admin/tenants/{slug}`, but no auth path joins on the tenants table to enforce it. A tenant marked inactive remains fully usable until each user is individually disabled.
- **Fix:** In `get_current_user`, after loading user, also load tenant and reject with 403 if `tenant.is_active is False`.

### HIGH-007: Module subscription `expires_at` is never enforced
- **Files:** `backend/middleware/module_gate.py:70-77`, `backend/models/subscription.py:90`
- **Issue:** `require_module` only checks `is_enabled.is_(True)`. Trial subscriptions with `expires_at < now` still pass the gate.
- **Fix:** Add `(TenantSubscription.expires_at.is_(None) | (TenantSubscription.expires_at > func.now()))` to the where clause.

### HIGH-008: No login attempt logging — security incidents are invisible
- **Files:** `backend/routers/auth.py:34-83`, `backend/middleware/auth.py`
- **Issue:** Successful logins, failed logins, JWT verification failures — none are logged or written to `AuditLog`. SIEM / SOC has no visibility into auth events.
- **Fix:** Write `AuditLog(action="login_success"|"login_failure", user_id=..., tenant_id=..., ip_address=client_ip, details={...})` on every login attempt. Same for logout (when added).

### HIGH-009: Rate limit uses raw `req.client.host` — broken behind any reverse proxy
- **File:** `backend/routers/auth.py:35-36`
- **Issue:** `req.client.host` is the immediate TCP peer. Behind nginx/Vercel/Railway (which the production reference doc confirms is the deployment), this is the proxy's IP — every user is throttled together. The rate limit will lock out everyone after one bad password from anyone, OR be a no-op (since the proxy IP almost never reaches 5 fails in 15 min).
- **Fix:** Trust `X-Forwarded-For`'s left-most value but only if the connection came from a known proxy IP (configurable). Use `request.client` only if no trusted proxy. Better: replace in-memory dict with Redis-backed limiter (slowapi, fastapi-limiter) so it works across multiple workers.

### HIGH-010: Compliance audit-log equivalent doesn't exist — only auditor_activity_log exists
- **Files:** Compliance routers
- **Issue:** Tenant-side state changes (publish policy, fulfil evidence request, trigger control run, register vendor, calculate score) write nothing to a tenant-visible audit log. Only AUDITOR actions are logged. A malicious admin can quietly publish a fraudulent policy version with no trace.
- **Fix:** Add a `compliance_audit_log` table mirroring URIP's `audit_log`; write entries from every state-changing route.

### HIGH-011: Evidence upload — no file size limit, no content-type validation, weak filename sanitisation
- **Files:** `compliance/backend/compliance_backend/routers/evidence.py:121-161`, `compliance/backend/compliance_backend/services/evidence_service.py:131-188`, `compliance/backend/compliance_backend/services/storage.py:113-119`
- **Issue:**
  - `content = await file.read()` (`evidence.py:142`) reads the entire upload into memory unbounded — single 10GB POST OOMs the service.
  - No `content_type` check; the `evidence_type` parameter is taken from the form, not from the file. Caller can label a `.exe` as `screenshot` then have it served back with `Content-Type: image/png` (XSS via SVG, malware delivery).
  - `safe_name = filename.replace("/", "_").replace("\\", "_").replace("..", "_")` (`evidence_service.py:163`) strips `..` literal but not `....//`, NUL bytes, leading `/`, or unicode normalisation tricks. `storage.py:113` does the same to `tenant_id` and `audit_period`.
  - Filesystem path uses parent directory traversal vulnerable input.
- **Fix:** Cap upload size (`MaxUpload` middleware or stream-and-count). Validate `file.content_type` against a whitelist matching `evidence_type`. Use `secrets.token_hex(16) + os.path.splitext(filename)[1]` as the on-disk name and ignore caller filename. Reject any `tenant_id`/`audit_period` string that contains characters outside `[A-Za-z0-9_-]`.

### HIGH-012: ReDoS — tenant-supplied regex patterns compiled and run on every asset classification
- **Files:** `backend/services/asset_criticality_service.py:138-153`, `backend/routers/asset_taxonomy.py:199-259`
- **Issue:** Tenant admins can POST keyword patterns that are compiled with `re.compile(p, re.IGNORECASE)` and run with `pattern.search(asset_name)` on every risk creation. A pattern like `(a+)+b` makes classification take seconds per asset; combine with a bulk import.
- **Fix:** Validate patterns with `re2` (RE2 has linear time guarantees) OR use a glob/wildcard syntax instead of full regex OR cap regex compile/run with a timeout.

### HIGH-013: Evidence service `control_id` not tenant-validated — orphan/invalid references
- **Files:** `compliance/backend/compliance_backend/services/evidence_service.py:131-188`, `compliance/backend/compliance_backend/routers/evidence.py:121-161`
- **Issue:** Caller-supplied `control_id` is written to the Evidence row without checking that the control exists or that the tenant has access to the framework that owns the control. Tenant A can attach evidence to a control_id that belongs to tenant B's framework instance (or to a non-existent control).
- **Fix:** Look up the Control row, derive the framework (and assert it's enabled for the caller's tenant), THEN persist evidence.

---

## Medium Findings

### MED-001: Audit log entries on update/assign in `risks.py` don't carry `tenant_id`
- **File:** `backend/routers/risks.py:271-277, 308-313`
- **Issue:** `AuditLog(...)` is created without `tenant_id=TenantContext.get()` for `risk_updated` and `risk_assigned`, breaking `apply_tenant_filter(AuditLog)` queries — these updates will be invisible to the tenant in `audit_log` listings (which DO filter by tenant).
- **Fix:** Add `tenant_id=TenantContext.get()` to every `AuditLog(...)` constructor.

### MED-002: AuditLog model allows `tenant_id` NULL — silent rows that escape tenant filter
- **File:** `backend/models/audit_log.py:25-29`, similar on every domain model (`Risk`, `User`, `RemediationTask`, etc.)
- **Issue:** Every "tenant-isolated" model declares `tenant_id` as nullable. `apply_tenant_filter` enforces equality on a non-null context, so NULL rows are excluded — but if any code path writes a NULL row (and MED-001 shows it does), those rows become invisible to BOTH the rightful tenant AND any audit attempt.
- **Fix:** Backfill all rows with correct tenant_id, then run an alembic migration to make `tenant_id` NOT NULL for `audit_logs`, `risks`, `acceptance_requests`, `remediation_tasks`, `connector_configs`, `users` (after backfill).

### MED-003: `LoginRequest` accepts arbitrary email without validation
- **File:** `backend/schemas/auth.py:4-7`
- **Issue:** `email: str` (not `EmailStr`). Allows oversized inputs, NULL bytes, etc. Same for password — no `max_length`.
- **Fix:** `email: EmailStr = Field(..., max_length=320)`, `password: str = Field(..., min_length=1, max_length=200)`.

### MED-004: `UserCreate` has no password length validation
- **File:** `backend/routers/settings.py:19-24`
- **Issue:** `password: str` accepted with no min_length and no max_length. Empty passwords → bcrypt hashes empty string. Long passwords (>72 bytes) silently truncated by bcrypt — collision risk.
- **Fix:** `password: str = Field(..., min_length=12, max_length=72)`. Same for `TenantAdminUserCreate.password` (currently `min_length=8` — fine for that field).

### MED-005: Bcrypt — silent 72-byte truncation
- **File:** `backend/middleware/auth.py:18-23`
- **Issue:** `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())` silently truncates input >72 bytes. A user with password `XXXXX...(80 char)1` and `XXXXX...(80 char)2` will have the same hash.
- **Fix:** Either (a) pre-hash with `hashlib.sha256(pw).digest()` then bcrypt the digest (Django's approach), or (b) switch to argon2id via `passlib`, which is in `requirements.txt` but not used.

### MED-006: Email enumeration via timing — bcrypt skipped for unknown users
- **File:** `backend/routers/auth.py:43-52`
- **Issue:** When email doesn't match any user, code skips `verify_password` (bcrypt is slow). Response time differs measurably between known and unknown emails, allowing user enumeration.
- **Fix:** Always run a dummy bcrypt verify against a fixed hash if user is None, then return the generic 401.

### MED-007: CORS in compliance is wide open — `allow_credentials=True` with hardcoded localhost origins; on URIP, `*` permitted
- **Files:** `backend/main.py:14-31`, `compliance/backend/compliance_backend/main.py:47-53`
- **Issue:** URIP's CORS handles `*` as wildcard with `allow_credentials=False` (correct). But it doesn't reject prod-unsafe `*` — operators easily set `CORS_ORIGINS=*` in env. Compliance hardcodes localhost. Production deployment requires explicit allowlist.
- **Fix:** Add a startup check that refuses `*` in production. Document a config matrix per environment.

### MED-008: Evidence bundle export — no size cap, in-memory zip; auditor portal can DoS the service
- **File:** `compliance/backend/compliance_backend/services/evidence_service.py:283-351`
- **Issue:** Build entire ZIP in `io.BytesIO` then return as response. For a tenant with thousands of large screenshots/configs across years of audit periods, this consumes multiple GB of RAM and several minutes of CPU per request. No streaming, no pagination, no rate-limit.
- **Fix:** Stream the zip via `StreamingResponse`; or generate an async background job + signed download URL.

### MED-009: Policy acknowledgment "signature" is just an unverified string
- **File:** `compliance/backend/compliance_backend/models/policy.py:148`, `compliance/backend/compliance_backend/services/policy_manager.py:99-141`
- **Issue:** `signature: str` (max 500 chars) is accepted from the user verbatim. There's no hash of the policy content at signing time, no IP/user-agent capture, no server-side signature derivation. A policy can be silently mutated server-side after acknowledgment and the ack would still appear "valid".
- **Fix:** Capture `policy_version_content_hash`, `ip_address`, `user_agent`, `server_timestamp_signature` (HMAC over user_id + policy_version_id + content_hash + acknowledged_at). Make the column NOT NULL on those new fields.

### MED-010: Auditor `get_control` 404 on cross-framework reads — but leaks existence via subtle status differences
- **File:** `compliance/backend/compliance_backend/routers/auditor.py:184-244`
- **Issue:** `Control not found` (L196) vs `Control not in audited framework` (L201) — distinguishes "doesn't exist" from "wrong framework", letting an auditor probe the existence of controls outside their scope.
- **Fix:** Return identical `404 Control not found.` in both cases.

### MED-011: AuditLog table is not append-only at DB level
- **File:** `backend/models/audit_log.py:11`
- **Issue:** No DB-level guarantee against UPDATE or DELETE on `audit_logs`. A DBA or anyone with write access (e.g. a service-role token) can modify history.
- **Fix:** PostgreSQL: revoke `UPDATE`, `DELETE` on `audit_logs` from the application role; only allow `INSERT`/`SELECT`. Use a separate, restricted role for audit reads.

### MED-012: Compliance models use `String(255)` for tenant_id with no FK to tenants table
- **Files:** `compliance/backend/compliance_backend/models/auditor.py:60`, `evidence.py:53`, `vendor.py:57`, `control_run.py:42`, `score_snapshot.py:40`, `policy.py:47, 142` (mixed: 36 vs 255)
- **Issue:** Type drift between Policy (`String(36)`) and others (`String(255)`); no FK to a tenants table. In INTEGRATED mode, URIP issues UUID strings; in STANDALONE mode the tenant_id is essentially free-form. Inconsistent length means a tenant_id stored from one path may not match a query from another (e.g. trailing whitespace not stripped). No FK means orphan rows reference deleted tenants forever.
- **Fix:** Standardise on `String(36)` (UUID); add a CHECK constraint for UUID format; document that compliance is identity-managed (URIP owns tenants table) and don't claim "standalone" without owning a tenants table.

---

## Low / Code Quality Findings

### LOW-001: Logger output never sanitised — captured tenant ids, evidence ids embedded in log strings
- **Files:** `compliance/backend/compliance_backend/services/evidence_service.py:121-124, 184-187`
- **Issue:** `logger.info("EvidenceService.upload_manual_evidence: id=%s control=%s tenant=%s", record.id, control_id, tenant_id)` — no secrets, but a log injection vector if `control_id` or `tenant_id` contained newlines (since both are user-controllable in standalone mode).
- **Fix:** Use structured logging (`logger.info(..., extra={"control_id": ...})`) and reject non-UUID tenant_id at request time.

### LOW-002: TODO/FIXME hot spots — categorise before launch
- **P0** (blocking — correctness):
  - `compliance/backend/compliance_backend/services/storage.py:8,173` — S3Storage not implemented; **FilesystemStorage cannot be used in multi-node prod** (each node has its own copy of evidence, none consistent).
  - `compliance/backend/compliance_backend/services/control_engine.py:22` (TODO P2B.3.2) — scheduling not wired; controls never run automatically; compliance score is stale.
- **P1**:
  - `compliance/backend/compliance_backend/services/control_rules/builtin/*.py` — 9 control rules read from `tenant_config` instead of integrating with URIP connectors. Same as CRIT-006 — caller-supplied state.
- **P2**:
  - `connectors/base/credentials_vault.py:14` — "Key rotation: not in scope for P1.6". Add MultiFernet rotation before prod.

### LOW-003: `try/except Exception` in connectors silently swallows
- **File:** `backend/services/exploitability_service.py:80, 108`
- **Issue:** While both branches log via `exc_info=True` (good), the broad `Exception` masks programmer errors (e.g. attribute errors). Narrow exceptions per call.
- **Fix:** `except (httpx.HTTPError, asyncio.TimeoutError, KeyError) as exc:`.

### LOW-004: Hardcoded production-ish data in `threat_intel.py` — `royalenfield.com` IPs and domains
- **File:** `backend/routers/threat_intel.py:106-141`
- **Issue:** `simulated_hits` dict contains tenant-specific data (RE infra, RE domains). Will appear in EVERY tenant's IOC match view. Confusing at minimum, brand-leakage at worst.
- **Fix:** Move simulated data behind a feature flag or seed-only path; for non-RE tenants return empty.

### LOW-005: `.env.credentials.URIP-PRODUCTION-REFERENCE` contains live Neon DB credentials in plaintext on disk
- **File:** `.env.credentials.URIP-PRODUCTION-REFERENCE`
- **Issue:** While `.gitignore` excludes the pattern (good), the file persists on every dev machine that clones-and-pulls metadata. It contains a Neon DB URL with embedded password (`npg_paQI6oqks5OJ`). Anyone who pivots onto a developer laptop or accidentally tarballs the repo gets prod DB.
- **Fix:** Move credentials to a secrets manager (1Password, Doppler, AWS Secrets Manager). Rotate the leaked Neon password. Delete the file (`mv` to a trash dir per INV-0).

### LOW-006: `frontend` static-mount serves at `/` — exposes any future config files in `frontend/`
- **File:** `backend/main.py:51`
- **Issue:** `app.mount("/", StaticFiles(directory="frontend", html=True))` after API routes. Any file dropped into `frontend/` (config.js with API tokens, .env mistakes, source maps, internal HTML) is publicly served. No restriction.
- **Fix:** Add an explicit allowlist of file extensions (`.html`, `.js`, `.css`, `.svg`, `.png`, `.jpg`, `.woff2`) via a thin custom static handler. Verify nothing sensitive lands in `frontend/`.

### LOW-007: `compliance/backend/compliance_backend/services/storage.py` — backend selected by env var, default is filesystem with global mutable singleton
- **File:** `compliance/backend/compliance_backend/services/storage.py:197-208`
- **Issue:** `get_storage()` returns a fresh instance per call — fine — but `FilesystemStorage._DEFAULT_BASE_DIR` is computed at import time from `__file__` parents. If service runs in a container where `__file__` differs from the writable mount, evidence is written into a path that gets blown away on container restart. Also no permission check on directory.
- **Fix:** Require `EVIDENCE_STORAGE_BASE_DIR` to be set explicitly in production; refuse to start if path doesn't exist, isn't writable, or is world-writable. Explicit chmod 0700 on creation.

---

## Domain-by-Domain Audit Matrix

| Domain | Status | Notes |
|---|---|---|
| **A. Tenant Isolation** | FAIL | URIP risks/dashboard/remediation/audit-log/asset-taxonomy/tenants are tenant-scoped (good); URIP **acceptance, reports, settings/users, settings/connectors, threat_intel** are NOT (CRIT-001/002/003). Compliance routers are mostly scoped via `require_tenant`, but `controls.py:trigger_run` lets caller forge inputs (CRIT-006). Cross-tenant returns are 404 in correct routers (good); but acceptance allows cross-tenant approve/reject. |
| **B. Authentication & JWT** | FAIL | Default secret known and shipped in `.env` (CRIT-004). Vulnerable jose lib (CRIT-005). HS256 enforced in decode calls (good). Tenant deactivation not enforced (HIGH-006). Login enumeration via timing (MED-006). Auditor JWT well-designed (revocation re-checked DB-side). No refresh tokens. |
| **C. Authorization (RBAC + Module Gate)** | FAIL | Module gate applied to ONE endpoint (CRIT-007). Role hierarchy is small (4 roles, fine). Compliance admin gate uses non-existent roles (CRIT-008). Super-admin bypass implemented correctly per spec but fragile under CRIT-004. Auditor portal correctly read-only — only POST is `/auditor/evidence-requests`. |
| **D. SQL Injection** | PASS | No raw `text()` in production routers; all queries use SQLAlchemy parameterised ORM. The one risk is `getattr(Risk, sort_by, ...)` (HIGH-004). LIKE patterns parameterised but unbounded length (HIGH-005). |
| **E. Secret Handling** | FAIL | Default JWT secret (CRIT-004). Compliance secrets default `change-me-in-production` and `urip-shared-secret` (CRIT-004). `URIP_FERNET_KEY` raises if unset (good). Live Neon DB password in `.env.credentials.URIP-PRODUCTION-REFERENCE` on disk (LOW-005). No credential rotation strategy (`credentials_vault.py:14`). |
| **F. File Upload / Storage** | FAIL | No size limit (HIGH-011). No content-type validation (HIGH-011). Filename sanitisation weak (HIGH-011). Vendor docs silently dropped (HIGH-002). Filesystem permissions never set (LOW-007). |
| **G. Audit Trail Completeness** | FAIL | No login attempt logging (HIGH-008). Some risk update audit log entries omit tenant_id (MED-001). Compliance has NO admin audit log — only auditor activity (HIGH-010). Audit table not append-only at DB level (MED-011). |
| **H. Rate Limiting / DoS** | FAIL | Login rate limit per-IP, in-memory dict, broken under proxy (HIGH-009). API endpoints: no general throttling. Pagination enforced on most list endpoints (good). Evidence bundle and report generate are unbounded (MED-008). ReDoS via tenant taxonomy (HIGH-012). |
| **I. CORS / CSRF** | PARTIAL | URIP CORS handles `*` correctly; compliance CORS hardcoded localhost (MED-007). No CSRF protection — pure JWT API; tokens in Authorization header. Static frontend mount could leak files (LOW-006). |
| **J. Dependency Security** | FAIL | `python-jose==3.3.0` — CVE-2024-33663 (HIGH algo-confusion), CVE-2024-33664 (MED DoS) (CRIT-005). `passlib[bcrypt]==1.7.4` — last release 2020; no CVEs at time of audit but unmaintained. `bcrypt` library used via passlib — silent 72-byte truncation (MED-005). |
| **K. Compliance-Specific** | FAIL | Auditor portal IS read-only (good — only POST is evidence-request). Evidence has no integrity hash (CRIT-009). Policy acknowledgment signature is unverified (MED-009). Access review decisions auditable BUT compliance audit log doesn't exist (HIGH-010). Caller-supplied control inputs (CRIT-006). |
| **L. Code Quality Smells** | OK | No `try: pass` swallowing in production paths (LOW-003 close but logs). RE-flavoured hardcoded data in threat_intel (LOW-004). TODOs categorised (LOW-002). |

---

## Files Audited

| Path | Lines |
|---|---|
| `backend/middleware/auth.py` | 82 |
| `backend/middleware/tenant.py` | 55 |
| `backend/middleware/module_gate.py` | 87 |
| `backend/middleware/rbac.py` | 27 |
| `backend/services/tenant_query.py` | 60 |
| `backend/services/crypto_service.py` | 28 |
| `backend/services/asset_criticality_service.py` | (key sections L130-180) |
| `backend/services/exploitability_service.py` | (key sections) |
| `backend/routers/auth.py` | 107 |
| `backend/routers/risks.py` | 319 |
| `backend/routers/acceptance.py` | 215 |
| `backend/routers/remediation.py` | 173 |
| `backend/routers/dashboard.py` | 231 |
| `backend/routers/reports.py` | 202 |
| `backend/routers/settings.py` | 210 |
| `backend/routers/audit_log.py` | 75 |
| `backend/routers/asset_taxonomy.py` | 387 |
| `backend/routers/tenants.py` | 494 |
| `backend/routers/threat_intel.py` | 198 |
| `backend/models/user.py` | 36 |
| `backend/models/risk.py` | 69 |
| `backend/models/audit_log.py` | 30 |
| `backend/models/acceptance.py` | 41 |
| `backend/models/remediation.py` | 38 |
| `backend/models/connector.py` | 36 |
| `backend/models/tenant.py` | 43 |
| `backend/models/subscription.py` | 90 |
| `backend/models/asset_taxonomy.py` | 116 |
| `backend/models/tenant_connector_credential.py` | 54 |
| `backend/schemas/auth.py` | 27 |
| `backend/schemas/risk.py` | 68 |
| `backend/config.py` | 84 |
| `backend/main.py` | 51 |
| `backend/database.py` | 19 |
| `backend/utils.py` | 11 |
| `compliance/backend/compliance_backend/middleware/auth.py` | 86 |
| `compliance/backend/compliance_backend/middleware/tenant.py` | 68 |
| `compliance/backend/compliance_backend/middleware/auditor_auth.py` | 167 |
| `compliance/backend/compliance_backend/services/storage.py` | 208 |
| `compliance/backend/compliance_backend/services/evidence_service.py` | 351 |
| `compliance/backend/compliance_backend/services/auditor_service.py` | 219 |
| `compliance/backend/compliance_backend/services/policy_manager.py` | 249 |
| `compliance/backend/compliance_backend/services/vendor_risk.py` | 282 |
| `compliance/backend/compliance_backend/services/control_engine.py` | (L1-130 reviewed) |
| `compliance/backend/compliance_backend/routers/auditor.py` | 487 |
| `compliance/backend/compliance_backend/routers/auditor_invitations.py` | 210 |
| `compliance/backend/compliance_backend/routers/admin_evidence_requests.py` | 126 |
| `compliance/backend/compliance_backend/routers/admin_auditor_activity.py` | 80 |
| `compliance/backend/compliance_backend/routers/evidence.py` | 245 |
| `compliance/backend/compliance_backend/routers/policies.py` | 319 |
| `compliance/backend/compliance_backend/routers/vendors.py` | 365 |
| `compliance/backend/compliance_backend/routers/controls.py` | 184 |
| `compliance/backend/compliance_backend/routers/frameworks.py` | 226 |
| `compliance/backend/compliance_backend/routers/compliance_score.py` | 215 |
| `compliance/backend/compliance_backend/models/auditor.py` | 165 |
| `compliance/backend/compliance_backend/models/evidence.py` | 72 |
| `compliance/backend/compliance_backend/models/policy.py` | 162 |
| `compliance/backend/compliance_backend/config.py` | 49 |
| `compliance/backend/compliance_backend/main.py` | 81 |
| `shared/auth/jwt_verifier.py` | 54 |
| `connectors/base/credentials_vault.py` | 153 |
| `connectors/base/connector.py` | (L1-80 reviewed) |
| `requirements.txt` | 35 |
| `compliance/backend/pyproject.toml` | 46 |
| `.env`, `.env.example`, `.env.credentials.URIP-PRODUCTION-REFERENCE`, `.gitignore` | (read) |
| `.github/workflows/ci.yml` | 28 |

## Files SKIPPED

- `frontend/*.html`, `frontend/js/*.js` — frontend code; out of scope (server-side audit). Worth a separate XSS / CSP review.
- `connectors/sentinelone/`, `connectors/tenable/`, `connectors/adverb_simulator.py`, `connectors/simulator_connector.py` — not on the requested file list; spot-check only of `connectors/base/` framework. Each concrete connector should be re-audited for credential handling, raw HTTP error messages, and rate-limit honouring.
- `compliance/backend/compliance_backend/services/scoring_engine.py` — read for context not deeply audited; relies on tenant-filtered ControlCheckRun rows so tenant safety inherits from controls.py state.
- `compliance/backend/compliance_backend/services/control_rules/**` — concrete control rule plugins. Spot-checked: all read from `tenant_config` (CRIT-006 root cause), so no further per-rule audit until that issue is fixed.
- `alembic/versions/*.py`, `compliance/alembic/versions/*.py` — migration scripts; correctness reviewed via model audit.
- `tests/`, `compliance/backend/tests/` — test suites; out of scope for production security review.
- `backend/seed.py`, `backend/simulator.py`, `backend/backfill_exploitability.py` — operator scripts; spot-checked for raw text() (only seed.py uses it, with hardcoded SQL, no user input).
- Frontend deps — not requested; recommend separate `npm audit` / Snyk run on `compliance/frontend/`.

---

## Recommended Remediation Order

1. **Today:** Fix CRIT-004 (rotate JWT secret, remove default). Roll any production tokens.
2. **Today:** Fix CRIT-005 (replace `python-jose` with `pyjwt`).
3. **This week:** CRIT-001, CRIT-002, CRIT-003 (tenant filtering on acceptance, reports, settings).
4. **This week:** CRIT-008 (compliance admin role consistency) — without this nothing in compliance admin works at all.
5. **Before any auditor sees the system:** CRIT-006 (control_engine input integrity), CRIT-009 (evidence hashing).
6. **Before public launch:** CRIT-007 (module gate everywhere), all HIGH findings.
7. **Hardening sprint:** MED + LOW.
