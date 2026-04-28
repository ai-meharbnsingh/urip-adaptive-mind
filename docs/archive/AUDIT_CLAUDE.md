# URIP-Adverb Security Audit (Claude/Opus)

**Date:** 2026-04-27
**Reviewer:** Opus (read-only)
**Scope:** URIP backend (`backend/`), Compliance Service (`compliance/backend/compliance_backend/`), shared (`shared/auth/`, `shared/tenant/`), Hybrid-SaaS agent (`agent/`, `backend/routers/agent_ingest.py`), Connectors framework (`connectors/base/`)
**Method:** Re-audit from scratch — trust nothing, verify every claimed fix line by line.

## Verdict

**NOT YET PRODUCTION-READY.** The big-ticket CRITs from `SECURITY_REVIEW.md` are mostly fixed and the new attack surface (PyJWT migration, evidence integrity, agent HMAC) is well thought through. **However, two CRITICAL holes remain open:**

1. **CRIT-008 incomplete** — `compliance/backend/compliance_backend/routers/policies.py:37` still ships its **own local `require_admin`** that checks `claims.get("role") != "admin"`. The shared `require_compliance_admin` helper that fixes the bug for every other admin router is *not* called here. In INTEGRATED mode, no URIP user can publish policies, list expiring policies, or create policy versions — and the test in `compliance/backend/tests/test_critfix_security.py` does not cover the policies router. Same broken gate the original review described, just narrower.
2. **CRIT-004 partially open in compliance** — `compliance/backend/compliance_backend/config.py:25-26` keeps `COMPLIANCE_JWT_SECRET = "change-me-in-production"` and `URIP_JWT_SECRET = "urip-shared-secret"` as module-level defaults with **no startup enforcement**. The URIP backend got `_enforce_jwt_secret_policy()` (refuses `prod`/`staging` with default secret); compliance was *not* given the same gate. A misconfigured production deployment can ship the well-known secret and silently mint forged auditor-portal JWTs.

There are also several material H-band gaps: compliance service has **zero** rate limiting (HIGH-009 was URIP-only), the auditor invitation `accept` endpoint can still be brute-forced, the live Neon DB password file (`.env.credentials.URIP-PRODUCTION-REFERENCE`) is still on disk, and `backend/routers/risks.py` `search`/`owner` parameters still have no length cap (HIGH-005 unfixed).

## Counts

**31 findings: 2 CRITICAL / 7 HIGH / 14 MEDIUM / 8 LOW**

## Comparison vs Original SECURITY_REVIEW.md

| Original | Status now | Notes |
|---|---|---|
| 9 CRIT | **7 fixed, 2 partially-open** | CRIT-001/002/003/005/006/007/009 fixed. CRIT-004 fixed in URIP backend, NOT compliance. CRIT-008 fixed in 4 of 5 admin routers, NOT in `policies.py`. |
| 13 HIGH | **8 fixed, 5 still open** | HIGH-002/004/006/007/008/011/012/013 fixed. HIGH-001 partially (router enforces tenant, but service still tenant-blind). HIGH-003 unfixed (multi-use accept, no IP binding, long lifetime). HIGH-005 unfixed (no max_length cap on `search`/`owner`). HIGH-009 fixed in URIP, missing in compliance. HIGH-010 fixed (compliance_audit_log table + `write_audit` helper added). |
| 12 MED | **5 fixed, 7 still open** | MED-001/010 fixed. MED-002/003/004/005/006/007/008/009/011/012 NOT fixed. |
| 7 LOW | **0 fixed, 7 still open** | LOW-001 through LOW-007 — none touched. |
| **NEW issues this audit** | **+5** | CL-NEW-1 (compliance has zero rate limiting), CL-NEW-2 (storage_uri leaks fs path in API response), CL-NEW-3 (evidence.py download swallows EvidenceTamperError as 500), CL-NEW-4 (audit log endpoint mishandles login_attempt rows with NULL user_id), CL-NEW-5 (logo_url + secondary_color have no scheme validation — `javascript:` XSS). |

---

## Critical Findings

### CRIT-A · `policies.py` admin gate is still the broken legacy version

- **File:** `compliance/backend/compliance_backend/routers/policies.py:37-45`
- **Issue:** A local `require_admin` Dependency checks `claims.get("role") != "admin"` and raises 403 otherwise. In INTEGRATED mode (URIP issues the JWT, where roles are `{board, executive, it_team, ciso}` per `backend/middleware/rbac.py:6-11`), this check never matches — the policies admin endpoints become unreachable for every URIP tenant user. The CRIT-008 remediation introduced `compliance_backend.middleware.auth.require_compliance_admin` (which DOES accept `ciso`/`is_super_admin`/`is_compliance_admin`), and four of the five admin routers (`auditor_invitations.py`, `admin_evidence_requests.py`, `admin_auditor_activity.py`, `compliance_score.py`) call it via `_require_admin` shims — but `policies.py` was missed.
- **Impact:** `POST /policies` (create_policy), `GET /policies/expiring`, and `POST /policies/{id}/versions` (publish_version) are all unreachable from any URIP-issued JWT; the policy admin pane is simply broken in INTEGRATED mode. Worse: when someone "fixes" this by relaxing the comparison locally instead of routing through the shared helper, the next reviewer will diverge again.
- **Reproduction:** `curl -H "Authorization: Bearer <ciso JWT issued by URIP>" -X POST <compliance>/policies -d '{...}'` → 403 with "Admin role required". The same JWT works on `/auditor-invitations` (which uses the centralised helper).
- **Fix:** Replace the local `require_admin` with one that calls `require_compliance_admin(claims)` exactly like `auditor_invitations.py:80-85`. Add a test mirroring `test_critfix_security.py` that runs a `ciso`-role JWT against `POST /policies` and asserts it does not 403.

### CRIT-B · Compliance service ships with hardcoded JWT secrets, no startup gate

- **Files:** `compliance/backend/compliance_backend/config.py:25-26`, `compliance/backend/compliance_backend/main.py` (no enforcement)
- **Issue:** `COMPLIANCE_JWT_SECRET: str = "change-me-in-production"` and `URIP_JWT_SECRET: str = "urip-shared-secret"` are pydantic-settings defaults. Unlike the URIP backend (`backend/config.py:112-150`, which calls `_enforce_jwt_secret_policy()` on startup and refuses to boot in `prod`/`staging` envs with the dev default), compliance has no such guard. Any operator who forgets to set both secrets in production gets a service that mints forgeable auditor JWTs (`COMPLIANCE_JWT_SECRET` is what `auditor_service._mint_auditor_jwt` signs with — `services/auditor_service.py:248-262`) AND, in INTEGRATED mode, accepts forged URIP tokens (`URIP_JWT_SECRET` is the verifier secret per `middleware/auth.py:44-50`).
- **Impact:** Total auth bypass into the auditor portal AND the compliance admin endpoints. An attacker who knows the literal `"change-me-in-production"` (i.e. anyone who can read this repo) can mint a JWT with `kind="auditor"`, fake `access_id`, fake `tenant_id`, and download every tenant's evidence — *if* a matching `AuditorAccess` row happens to exist (auditor_auth.py also re-checks DB, which mitigates but does not fully neutralise). For non-auditor tokens, INTEGRATED-mode forgery is unconditional.
- **Reproduction:** `python -c 'import jwt; print(jwt.encode({"sub":"x","role":"ciso","tenant_id":"any","exp":9999999999}, "urip-shared-secret", algorithm="HS256"))'` → token decoded by compliance in INTEGRATED mode without protest.
- **Fix:** Mirror `backend/config.py`. Add `COMPLIANCE_ENV` env var, define `PRODUCTION_LIKE_ENVS`, and refuse to import compliance config when env is `prod|production|staging` AND either secret equals its default. Bonus: assert `COMPLIANCE_JWT_SECRET != URIP_JWT_SECRET` (they must be distinct so a leaked URIP secret does not also forge auditor tokens).

---

## High Findings

### HIGH-A · Compliance service has **zero** rate limiting (CL-NEW-1)

- **Files:** `compliance/backend/compliance_backend/main.py` (no slowapi wiring), entire compliance service.
- **Issue:** HIGH-009's `slowapi`-based limiter at `backend/middleware/rate_limit.py` is wired into URIP's `backend/main.py:76`. Compliance's `main.py` does not import or install any rate-limit middleware. `grep` for `slowapi|Limiter|limiter` under `compliance/` returns nothing.
- **Impact:** `POST /auditor-invitations/accept` is a public, unauthenticated endpoint that exchanges a token for a JWT (`routers/auditor_invitations.py:170-192`). With no rate limit, an attacker can brute-force the 32-byte URL-safe token (256 bits — astronomically hard) — but more dangerous: the auditor JWT minting endpoint, the compliance admin endpoints, and the evidence bundle download endpoint all have no per-IP/per-tenant throttle, enabling cheap DoS or credential-spray against the compliance API.
- **Fix:** Lift `install_rate_limiting` into compliance, or install `slowapi` directly in `compliance_backend/main.py`. At minimum: `5/minute` on `POST /auditor-invitations/accept`, `60/minute` on every write endpoint.

### HIGH-B · `risks.py` `search`/`owner` query params have no length cap — DoS via `%`-blowup (HIGH-005 still open)

- **File:** `backend/routers/risks.py:94-97, 124-134`
- **Issue:** `search: str | None = Query(default=None)` and `owner: str | None = Query(default=None)` are still raw — no `max_length` and no rejection of pure-wildcard input. The original review prescribed `max_length=100`; the diff was not applied. `Risk.finding.ilike(f"%{search}%")` with a 1MB wildcard string produces a pathological LIKE pattern across every row.
- **Impact:** Authenticated CISO can DoS the risks list endpoint by submitting `search="%" * 1_000_000`. With no per-tenant cap on row count either, this scales linearly with the tenant's risk register.
- **Fix:** `Query(default=None, max_length=100)` on both. Reject inputs containing only `%` / `_` characters.

### HIGH-C · Auditor invitation token is multi-use, no IP binding, no logout (HIGH-003 still open)

- **Files:** `compliance/backend/compliance_backend/routers/auditor_invitations.py:170-192`, `services/auditor_service.py:167-192`
- **Issue:** The accept endpoint can be called repeatedly with the same token; the comment at line 13-16 frames this as a feature ("auditor switches devices"). Token lifetime equals `expires_at` (admin-set, no upper bound enforced). No IP/user-agent binding on the minted JWT. Forwarded-link reuse is undetectable. The original review's recommendation (single-use accept by default; admin "regenerate token" action; bind to client IP; cap lifetime) was not implemented.
- **Impact:** A leaked invitation URL (email forward, Slack screenshot, support ticket attachment) lets the leaker AND the original auditor mint independent JWTs. Revoking the AuditorAccess row stops *new* requests via DB re-check (good — see `auditor_auth.py:115-121`), but the already-minted JWT remains decode-valid for the rest of its lifetime; the DB re-check is the only thing keeping it from working — so any drift in that check is fatal.
- **Fix:** Make accept single-use by default (set `accepted_at` at first call; reject subsequent calls or reuse explicit "regenerate" admin action). Cap `expires_at` server-side at 90 days. Optionally bind the JWT to client IP and revalidate on every request (defence-in-depth).

### HIGH-D · Vendor risk service still does not enforce tenant scope at the service layer (HIGH-001 partial)

- **Files:** `compliance/backend/compliance_backend/services/vendor_risk.py:79-94, 226-248`
- **Issue:** `record_response()` looks up `VendorQuestionnaire` by id with no `tenant_id` join. `calculate_risk_score()` looks up `Vendor` by id with no `tenant_id` join. The `vendors.py` router DOES check tenant ownership before calling these (good), but the original review explicitly flagged that "the service is one parameter swap from cross-tenant write." That hardening was never done. If anyone ever invokes these helpers from a job, scheduled task, or new endpoint without first checking tenant ownership, cross-tenant write happens silently.
- **Impact:** Latent — depends entirely on the router never being bypassed. Defence-in-depth gap.
- **Fix:** Make `tenant_id` a required parameter on every service function and add `WHERE` clauses. Don't trust the caller's filter.

### HIGH-E · Tenant `logo_url` / colour fields have no scheme validation — XSS via `javascript:` (CL-NEW-5)

- **File:** `backend/routers/tenants.py:108-115`
- **Issue:** `TenantUpdate.logo_url: str | None = None` is accepted verbatim and stored into `tenant.settings`. The frontend then renders this URL into `<img src=...>` (or potentially `<a href=...>`) without scheme allowlist. A super-admin who is malicious or compromised can set `logo_url=javascript:alert(document.cookie)` and trigger XSS for every user of the targeted tenant.
- **Impact:** Stored XSS in white-label branding — every CISO/IT-team member of the tenant lands on a page that runs attacker JS. Combined with super-admin compromise this allows session hijack across every tenant. Even without compromise, a super-admin who turns hostile can backdoor any tenant invisibly.
- **Fix:** Validate `logo_url` against `^https?://` and a domain allowlist if appropriate. Validate `primary_color`/`secondary_color` more strictly than the current 6-hex regex (it is fine — but ensure the frontend also escapes when interpolating into CSS variables, which is a separate XSS pivot).

### HIGH-F · Tenant `audit_period` and `tenant_id` reach filesystem path with weak sanitisation (HIGH-011 partial)

- **Files:** `compliance/backend/compliance_backend/services/storage.py:113-119`, `routers/evidence.py:130`
- **Issue:** The router accepts `audit_period: Optional[str] = Form(None)` (evidence.py:130) and `tenant_id` from `require_tenant` (string-typed in compliance, see `middleware/tenant.py:53`). Both are used unfiltered in `_resolve_path`, which only does `.replace("/", "_").replace("..", "_")` literal string replaces. Misses: NUL bytes (`\x00`), backslashes (path separator on cross-platform), unicode normalisation tricks (`..` resolves to `..` after NFC), CR/LF for log injection, leading/trailing whitespace causing same-path collisions. Filenames are now properly sandboxed by `_upload_guards.sanitise_filename`, but the *directory components* are not.
- **Impact:** Path traversal is largely closed by the literal `..` replacement, but secondary issues remain: weird tenant_id strings (rare in INTEGRATED mode where they are UUIDs from URIP, common in STANDALONE mode where the tenant_id is whatever the JWT claim says) can produce on-disk paths that mask each other or escape into adjacent directories on Windows hosts. Best practice: refuse non-UUID tenant_id and constrain audit_period to `YYYY` / `YYYY-Q[1-4]`.
- **Fix:** Add a `^[A-Za-z0-9_-]{1,100}$` regex on tenant_id and audit_period in `_resolve_path`; raise on mismatch. Store the canonical audit_period elsewhere if richer formatting is needed.

### HIGH-G · No SSRF guard on connector test/configure endpoints

- **File:** `backend/routers/connectors.py:367-441`
- **Issue:** `test_connector_connection` accepts caller-supplied `payload.credentials` (which includes `base_url` for SentinelOne, Netskope, ManageEngine SDP, MS Entra) and immediately authenticates against that URL via the live connector. Behind a tenant boundary this is "feature, not a bug" — except a CISO can supply `base_url=http://169.254.169.254/latest/meta-data/` (AWS IMDS), `http://localhost:5432/` (internal DB ports), or `http://internal-service:8080/` and watch the connector probe internal infrastructure. Same risk on `POST /api/connectors/{name}/configure` followed by `/test`. The connectors do not validate their own `base_url` against an external scheme/netloc allowlist.
- **Impact:** SSRF — authenticated CISO can scan internal network, fetch cloud-metadata service, probe internal HTTP services. Combined with super-admin compromise, full internal reconnaissance.
- **Fix:** Reject `base_url` whose hostname resolves to private IP space (RFC1918 / loopback / link-local) at the connector layer. Optionally limit to a per-vendor public hostname allowlist (`*.tenable.com`, `*.sentinelone.net`, etc.).

---

## Medium Findings

### MED-A · MED-002 still open — `tenant_id` nullable on every domain model
**Files:** `backend/models/audit_log.py:29-33`, every model declared in `backend/models/`. Login attempt rows for unknown emails legitimately need NULL `tenant_id` (HIGH-008 fix), but every other domain model still permits NULL — `apply_tenant_filter` will silently skip those rows. No alembic migration to backfill + NOT NULL.

### MED-B · MED-003 still open — `LoginRequest.email: str` (no EmailStr, no max_length)
**File:** `backend/schemas/auth.py:5-7`. Allows oversized inputs and NULL bytes. Spec said `email: EmailStr = Field(..., max_length=320)`.

### MED-C · MED-004 still open — `UserCreate.password: str` (only `min_length=8`)
**File:** `backend/routers/settings.py:34-39`. No `max_length` cap; bcrypt silently truncates >72 bytes (MED-005, also still open).

### MED-D · MED-005 still open — bcrypt truncates >72-byte passwords
**File:** `backend/middleware/auth.py:28-29`. `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())` silently drops bytes 73+. Two distinct 80-char passwords differing only past byte 72 hash identically.

### MED-E · MED-006 still open — email enumeration via timing
**File:** `backend/routers/auth.py:101-120`. When email isn't found, `verify_password` is skipped; response time is measurably faster. The original review prescribed a dummy bcrypt against a fixed hash.

### MED-F · MED-007 still open — compliance CORS hardcoded localhost; URIP CORS does not refuse `*` in prod
**Files:** `backend/main.py:78-96`, `compliance/backend/compliance_backend/main.py:48-54`. Production deployment with `CORS_ORIGINS=*` is silently accepted on URIP; compliance is locked to `http://localhost:3001,http://localhost:3000` and there is no env-driven override path documented.

### MED-G · MED-008 still open — evidence bundle is built in-memory ZIP (DoS)
**File:** `compliance/backend/compliance_backend/services/evidence_service.py:344-412`. Single auditor request can OOM the service for large tenants. Bundle still does not include `content_sha256` in `manifest.json` (so external auditor cannot verify integrity end-to-end after they unzip — CRIT-009's hash benefit stops at the wire).

### MED-H · MED-009 still open — policy acknowledgment "signature" unverified
**Files:** `compliance/backend/compliance_backend/services/policy_manager.py:99-141`, `models/policy.py`. The signature column accepts whatever the user submits. No hash of policy version content captured at sign time; no IP/user-agent; no server-side HMAC. A policy can be silently mutated on the server after acknowledgment and the ack still appears valid. Non-repudiation broken.

### MED-I · MED-011 still open — `audit_logs` not append-only at DB level
**File:** `backend/models/audit_log.py`. No DB-level revocation of UPDATE/DELETE permissions on `audit_logs`. A DBA or compromised app role can rewrite history.

### MED-J · MED-012 still open — compliance models use `String(255)` tenant_id, no FK
**Files:** `compliance/backend/compliance_backend/models/{auditor,evidence,vendor,control_run,score_snapshot,policy}.py`. Inconsistent: Policy uses `String(36)` (UUID), others use `String(255)`. No FK to tenants table. In STANDALONE mode the column accepts any string.

### MED-K · `compliance_audit_log` only writes when callers remember (HIGH-010 fix incomplete)
**Files:** `compliance/backend/compliance_backend/services/audit_writer.py`, every router that mutates state. The new `write_audit` helper is great, but a grep finds it called in `vendors.py`, `evidence.py`, `policies.py` (publish/acknowledge/create), `controls.py`, `compliance_score.py`, `auditor_invitations.py`, `admin_evidence_requests.py` — but **NOT** in `auditor.py` non-read paths (e.g. `POST /auditor/evidence-requests`) where the auditor portal action is logged via `log_auditor_action` (separate stream — auditor activity log, not the tenant-side audit log). That asymmetry means a tenant admin who consumes their own admin audit log will not see auditor-driven evidence requests. Decide whether the two log streams should be merged or formally separated; document either way.

### MED-L · `audit_log.py` endpoint mishandles `login_attempt` rows with NULL `user_id` (CL-NEW-4)
**File:** `backend/routers/audit_log.py:77-97`. `user_ids = list(set(log.user_id for log in logs))` may include `None`; `select(User).where(User.id.in_(user_ids))` on Postgres will work but on SQLite `IN (NULL, ...)` is a 3-valued anomaly. Worse: `str(log.user_id)` returns the literal string `"None"` for those rows (line 88), which violates the `user_id: str` Pydantic model contract and produces nonsense UUIDs in the API response. HIGH-008 added `login_attempt` rows with `user_id=None`; the audit-log endpoint needs to handle them (filter them or expose a `user_email` field for them).

### MED-M · `evidence.py` tenant download path does NOT catch `EvidenceTamperError` (CL-NEW-3)
**File:** `compliance/backend/compliance_backend/routers/evidence.py:214-260`. The auditor route correctly catches `EvidenceTamperError` and returns 409 (`routers/auditor.py:309-326`). The tenant route only wraps `FileNotFoundError`. A tampered evidence row bubbles up an uncaught exception → 500. A tenant administrator cannot distinguish "missing file" from "tampered file" from their own UI. Mirror the auditor handler.

### MED-N · `storage_uri` leaks server filesystem path in API responses (CL-NEW-2)
**Files:** `compliance/backend/compliance_backend/routers/evidence.py:50, 78` (EvidenceOut), `routers/vendors.py:99` (VendorDocumentOut). The `storage_uri` field is `file:///absolute/path/...` in dev/single-node. Returning this to API clients leaks the on-host filesystem layout. Switch to opaque IDs in API responses; resolve URI server-side.

---

## Low Findings

### LOW-A · LOW-001 — log injection vector
**File:** `compliance/backend/compliance_backend/services/evidence_service.py:153-156, 220-223`. Logger uses positional %s formatting on `tenant_id` / `control_id`; if tenant_id ever contains a newline (possible in STANDALONE mode where it's a free-form string), log line splitting becomes possible.

### LOW-B · LOW-002 P0 still open — `S3Storage` not implemented; FilesystemStorage not multi-node safe
**File:** `compliance/backend/compliance_backend/services/storage.py:184-194`. `S3Storage.write/read/delete` raise `NotImplementedError`. Production deployment with multiple compliance pods will lose evidence between nodes.

### LOW-C · LOW-003 — broad `Exception` swallow in exploitability + connectors
**Files:** `backend/services/exploitability_service.py:80, 108`, `backend/routers/connectors.py:398-435` (multiple `except Exception` paths). Logs include `exc_info=True` (good) but mask programmer errors.

### LOW-D · LOW-004 still open — RoyalEnfield IPs hardcoded in threat_intel for ALL tenants
**File:** `backend/routers/threat_intel.py:118-154`. Every tenant sees the same five "matched" IOCs: `185.174.101.42`, `royal-enfield-hr.com`, `royalenfield-warranty.in`, `139.180.199.55`, `invoice-royalenfield.com`. Brand leakage at minimum, confusing-multi-tenant data at worst.

### LOW-E · LOW-005 still open — live Neon DB password in `.env.credentials.URIP-PRODUCTION-REFERENCE`
**File:** `/Users/.../.env.credentials.URIP-PRODUCTION-REFERENCE` (verified present). Contains live `npg_paQI6oqks5OJ` Neon password, Railway URLs, demo creds. `.gitignore` covers `.env.credentials*` (good — file is not in git) but file persists on every dev machine. Should be moved to a secrets manager and rotated.

### LOW-F · LOW-006 still open — `app.mount("/", StaticFiles(directory="frontend", html=True))` serves anything dropped into frontend/
**File:** `backend/main.py:121`. Any future config.js / source map / `.env.local` accidentally placed in `frontend/` is publicly accessible.

### LOW-G · LOW-007 still open — `EVIDENCE_STORAGE_BASE_DIR` not refused in prod when missing/world-writable
**File:** `compliance/backend/compliance_backend/services/storage.py:110-119`. No startup check that the dir exists, is writable, mode 0700.

### LOW-H · 5-minute anti-replay window on agent ingest is wide for a high-value path
**File:** `backend/routers/agent_ingest.py:75`. The replay window is 5 min and there is no nonce — any captured signed request can be replayed for that long. For `/heartbeat` this matters little; for `/metadata` (which mutates `RiskScoreSummary` snapshots) it could be exploited if an attacker briefly intercepts a signed request. Recommend a request-id + DB nonce table (or a Redis SETNX with TTL) instead of pure timestamp skew.

---

## Domain Audit Matrix (A–M)

| # | Domain | Status | Key observations |
|---|---|---|---|
| A | Tenant isolation | **PASS with one defence-in-depth gap** | URIP routers (acceptance/reports/settings/risks/dashboard/remediation/audit_log/asset_taxonomy/threat_intel) are tenant-scoped via `apply_tenant_filter` or explicit `tenant_id ==`. Compliance routers enforce tenant on every query. Cross-tenant accesses return 404 (no info leak). HIGH-D — `vendor_risk.py` services still tenant-blind; routers must enforce. |
| B | Authentication & JWT (PyJWT) | **PASS in URIP, FAIL in compliance** | PyJWT migration complete (no `from jose` in production code; tests still import `jose` for migration verification). HS256 pinned via `algorithms=[…]` everywhere. URIP has startup gate against default secret (CRIT-004 fixed for URIP). **Compliance has no startup gate — CRIT-B.** Tenant `is_active` enforcement on URIP login + every request (HIGH-006 fixed). No refresh token strategy (acceptable for the scope). |
| C | Authorization / Module gate / RBAC | **PASS with one gap** | Module gate applied router-level on every URIP router that needs it (CRIT-007 fixed). Compliance admin gate centralised — `is_compliance_admin` accepts ciso/super_admin/is_compliance_admin/legacy `admin`. **`policies.py` STILL ships the legacy local check — CRIT-A.** Super-admin bypass implemented correctly. Module subscription expiry honoured (HIGH-007 fixed). RBAC hierarchy small (4 roles) — fine. |
| D | SQL injection | **PASS** | No raw `text()` in production routers (verified via grep). `getattr(Risk, sort_by, ...)` replaced with allowlist (HIGH-004 fixed). LIKE patterns parameterised — but search/owner length still uncapped (HIGH-B). |
| E | Secret handling | **FAIL** | URIP rotates default secret with startup gate, but compliance does not (CRIT-B). `URIP_FERNET_KEY` raises if unset (good). `.env.credentials.URIP-PRODUCTION-REFERENCE` still on disk with live Neon DB password (LOW-E). No credential rotation (Fernet → MultiFernet) implemented. No secrets in logs verified by grep. |
| F | File upload | **PASS at router, MEDIUM gaps at storage** | `_upload_guards.read_and_validate_upload` enforces 50MB cap, content-type allowlist, filename sanitise + UUID prefix. Vendor docs persist real bytes (HIGH-002 fixed). Evidence content has SHA-256 integrity hash + tamper detection (CRIT-009 fixed). Storage layer still has weak audit_period / tenant_id sanitisation (HIGH-F). storage_uri exposed in API response (CL-NEW-2). |
| G | Audit trail | **MOSTLY PASS, two gaps** | URIP login attempts logged (HIGH-008 fixed). Risk update + assign carry tenant_id (MED-001 fixed). Compliance has the new `compliance_audit_log` + `write_audit` helper (HIGH-010 fixed). Auditor activity in separate stream (`auditor_activity_log`) — partial duplication (MED-K). audit_log endpoint mishandles login_attempt rows (CL-NEW-4). audit_logs table not append-only (MED-I). |
| H | Rate limiting / DoS | **URIP: PASS. Compliance: FAIL** | URIP installs slowapi via `install_rate_limiting()` with trusted-proxy XFF parsing (HIGH-009 fixed for URIP). **Compliance has no rate limiter — HIGH-A**. Evidence bundle in-memory zip (MED-G). ReDoS via taxonomy regex closed by literal-only keyword validation (HIGH-012 fixed). |
| I | CORS / CSRF | **PARTIAL** | URIP CORS handles wildcard correctly with `allow_credentials=False`; compliance hardcodes localhost. No CSRF (pure JWT bearer auth — N/A). Static frontend mount could leak files (LOW-F). |
| J | Dependency security | **PASS** | `python-jose` removed (CRIT-005 fixed). Production code uses PyJWT 2.9+ exclusively. `passlib[bcrypt]==1.7.4` still pinned and unmaintained but no known CVEs at audit time. SQLAlchemy bumped to >=2.0.40 (Python 3.14 compat — NEW-3). slowapi >=0.1.9 added. Recommend running `pip-audit` weekly. |
| K | Compliance-specific (auditor portal, evidence integrity, policy non-rep) | **PARTIAL** | Auditor portal correctly read-only except `POST /auditor/evidence-requests`. Time/framework/tenant binding enforced server-side per request (good). Evidence has SHA-256 + tamper detection (CRIT-009 fixed). Bundle export does not include content_sha256 in manifest (MED-G aside). Policy ack signature still unverified (MED-H). Caller cannot supply control inputs (CRIT-006 fixed). |
| L | Hybrid-SaaS agent | **PASS with one minor gap** | HMAC verification correct (sha256-of-secret used as HMAC key — symmetric, intentional). 5-min anti-replay window with no nonce (LOW-H — wide for `/metadata`). One-time drilldown tokens (32 bytes hex, 60s TTL, fulfilled_payload_temp wiped after SSE forward). License-key compare is constant-time via SHA256 + `hmac.compare_digest`. RAW_FINDING_DENY_KEYS recursive scan rejects raw findings on `/metadata`. Auditor JWT timezone fix verified (NEW-2 fixed via `_utc_epoch`). |
| M | Code quality / hardening | **OK** | Some `try/except Exception` branches with `exc_info=True` (LOW-C). Hardcoded RE IOCs in threat_intel.py (LOW-D). TODOs categorised in original review still open (LOW-B). |

---

## Files Audited

| Path | Notes |
|---|---|
| `backend/main.py` | Slowapi installed, CORS, frontend mount, 51 lines original → 122 lines (lifespan + scheduler added) |
| `backend/config.py` | `_enforce_jwt_secret_policy` startup gate verified |
| `backend/middleware/auth.py` | PyJWT migration verified, tenant `is_active` enforcement verified |
| `backend/middleware/tenant.py` | unchanged |
| `backend/middleware/module_gate.py` | expiry filter verified |
| `backend/middleware/rbac.py` | role hierarchy unchanged; super-admin bypass not in `role_required` (intentional) |
| `backend/middleware/rate_limit.py` | new — slowapi-backed limiter with trusted-proxy XFF |
| `backend/routers/auth.py` | login_attempt audit rows verified; legacy in-memory limiter still present alongside slowapi (redundant but harmless) |
| `backend/routers/risks.py` | sort_by allowlist verified; HIGH-005 search/owner caps NOT applied |
| `backend/routers/acceptance.py` | tenant filter on every query verified |
| `backend/routers/reports.py` | tenant filter on every query verified |
| `backend/routers/settings.py` | tenant filter + role gate verified |
| `backend/routers/remediation.py` | tenant filter verified |
| `backend/routers/dashboard.py` | tenant_id == TenantContext.get() on every aggregate |
| `backend/routers/audit_log.py` | tenant filter verified; CL-NEW-4 (login_attempt user_id NULL handling) |
| `backend/routers/asset_taxonomy.py` | literal-only keyword validation verified (HIGH-012 fixed) |
| `backend/routers/tenants.py` | super-admin gate verified; logo_url scheme not validated (HIGH-E) |
| `backend/routers/threat_intel.py` | LOW-D RoyalEnfield IPs still hardcoded |
| `backend/routers/agent_ingest.py` | HMAC verification + replay window + drill-down tokens reviewed |
| `backend/routers/connectors.py` | SSRF risk on connector test/configure (HIGH-G) |
| `backend/services/tenant_query.py` | unchanged |
| `backend/services/crypto_service.py` | Fernet key resolution + dev fallback ban verified |
| `backend/models/audit_log.py` | tenant_id still nullable (MED-002 still open) |
| `backend/schemas/auth.py` | LoginRequest still raw email/password (MED-003 still open) |
| `compliance/backend/compliance_backend/main.py` | NO rate limiter, NO startup secret gate |
| `compliance/backend/compliance_backend/config.py` | CRIT-B — defaults shipped, no enforcement |
| `compliance/backend/compliance_backend/middleware/auth.py` | PyJWT migration + `is_compliance_admin` helper verified |
| `compliance/backend/compliance_backend/middleware/auditor_auth.py` | DB re-check on every request verified; tenant/framework claim cross-check verified |
| `compliance/backend/compliance_backend/middleware/tenant.py` | tenant_id contextvar from JWT claim |
| `compliance/backend/compliance_backend/services/evidence_service.py` | content_sha256 write+read+verify path; bundle still in-memory; bundle manifest missing hash |
| `compliance/backend/compliance_backend/services/storage.py` | naïve directory-component sanitisation (HIGH-F) |
| `compliance/backend/compliance_backend/services/auditor_service.py` | NEW-2 _utc_epoch verified; multi-use accept (HIGH-C) |
| `compliance/backend/compliance_backend/services/policy_manager.py` | signature still unverified (MED-H) |
| `compliance/backend/compliance_backend/services/vendor_risk.py` | service-layer tenant scope still missing (HIGH-D) |
| `compliance/backend/compliance_backend/services/audit_writer.py` | new — central audit log helper |
| `compliance/backend/compliance_backend/services/control_engine.py` | server-side tenant_config / connector_data only (CRIT-006 fixed) |
| `compliance/backend/compliance_backend/routers/controls.py` | TriggerRunRequest extra="forbid" verified (CRIT-006 fixed) |
| `compliance/backend/compliance_backend/routers/policies.py` | **CRIT-A — local require_admin not migrated to centralised helper** |
| `compliance/backend/compliance_backend/routers/auditor_invitations.py` | uses centralised admin gate; HIGH-C concerns persist on accept endpoint |
| `compliance/backend/compliance_backend/routers/admin_evidence_requests.py` | uses centralised admin gate |
| `compliance/backend/compliance_backend/routers/admin_auditor_activity.py` | uses centralised admin gate |
| `compliance/backend/compliance_backend/routers/compliance_score.py` | uses centralised admin gate |
| `compliance/backend/compliance_backend/routers/evidence.py` | upload guards verified; download path doesn't catch EvidenceTamperError (MED-M); storage_uri exposed (CL-NEW-2) |
| `compliance/backend/compliance_backend/routers/auditor.py` | read-only except `POST /auditor/evidence-requests`; framework + period scoping; tamper handling 409 |
| `compliance/backend/compliance_backend/routers/vendors.py` | tenant ownership enforced; storage_uri exposed (CL-NEW-2); upload guards verified |
| `compliance/backend/compliance_backend/routers/_upload_guards.py` | new — 50MB cap + allowlist + UUID prefix |
| `compliance/backend/compliance_backend/models/evidence.py` | content_sha256 column added (CRIT-009 fixed) |
| `shared/auth/jwt_verifier.py` | PyJWT migration verified |
| `agent/agent_main.py`, `agent/reporter.py` | HMAC scheme matches cloud (sha256-of-secret as HMAC key) |
| `connectors/base/credentials_vault.py` | Fernet vault; no rotation strategy yet |
| `requirements.txt` | python-jose removed; PyJWT >=2.9, slowapi, sqlalchemy >=2.0.40 verified |
| `.env`, `.env.example`, `.env.credentials.URIP-PRODUCTION-REFERENCE`, `.gitignore` | live Neon password still on disk; .gitignore covers it |

## Files NOT audited (reason)

- `frontend/*.html`, `frontend/js/*.js` — out of scope (server-side audit). Recommend separate XSS / CSP review especially with HIGH-E (logo_url) finding.
- `connectors/{tenable,sentinelone,zscaler,netskope,ms_entra,manageengine_sdp,cloudsek}/connector.py` — only spot-checked SentinelOne for `base_url` handling. Each concrete connector should be re-audited for credential injection in error messages, raw HTTP error logging, and base_url scheme validation.
- `compliance/backend/compliance_backend/services/scoring_engine.py` — read for context only; tenant safety inherited from controls.py.
- `compliance/backend/compliance_backend/services/control_rules/builtin/*.py` — concrete control rule plugins. CRIT-006 ensures inputs are server-side; per-rule audit not in scope.
- `alembic/versions/*.py`, `compliance/alembic/versions/*.py` — migration scripts; correctness reviewed via current model state.
- `tests/`, `compliance/backend/tests/` — out of scope for production security review. Did spot-check `test_critfix_security.py` to confirm CRIT-A (policies.py) is not covered.
- `backend/seed.py`, `backend/simulator.py`, `backend/seed_simulators/*` — operator scripts; spot-checked for raw text() usage (none found).
- Frontend deps — not requested; recommend separate `npm audit` on `compliance/frontend/`.

---

## Recommended Remediation Order

1. **Today:** CRIT-A — fix `policies.py` admin gate (one-line replace + add test).
2. **Today:** CRIT-B — port URIP's `_enforce_jwt_secret_policy` to compliance, add `COMPLIANCE_ENV` env var.
3. **This week:** HIGH-A (compliance rate limiting), HIGH-B (risks search/owner caps), HIGH-G (connector SSRF), HIGH-C (single-use accept).
4. **Before any auditor sees the system:** HIGH-D (vendor_risk service tenant scope), HIGH-E (logo_url XSS), HIGH-F (audit_period / tenant_id regex).
5. **Before public launch:** all MED, especially MED-D/E (bcrypt truncation + timing oracle), MED-H (policy ack non-rep), MED-G (streaming bundle export), MED-K/L (audit log gaps), MED-I (audit_logs append-only DB role).
6. **Hardening sprint:** all LOW.
