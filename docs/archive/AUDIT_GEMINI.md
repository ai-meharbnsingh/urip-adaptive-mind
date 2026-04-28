# URIP-Adverb Security Audit (Gemini)

## Verdict: FAILED
The URIP-Adverb platform exhibits several architectural security flaws and critical credential exposures that must be remediated before production deployment. While the "CritFix" sprint addressed immediate cross-tenant leaks in the primary API, the Compliance Service and Hybrid-SaaS agent components remain highly vulnerable.

## Counts: 5 CRITICAL / 5 HIGH / 4 MEDIUM / 2 LOW

---

## Findings by Severity

### CRITICAL
1. **[CRIT-G1] Live Production Credentials Exposure**
   - **File:** `.env.credentials.URIP-PRODUCTION-REFERENCE:22-23`
   - **Impact:** Contains live Neon PostgreSQL connection strings (`NEON_DB_URL_SYNC`, `NEON_DB_URL_ASYNC`) including plaintext passwords for the production owner account. Full compromise of production data is possible.
   - **Fix:** Immediately rotate Neon DB credentials. Delete this file and ensure it is added to `.gitignore`. Use a secure vault (e.g., AWS Secrets Manager, HashiCorp Vault) for production secrets.

2. **[CRIT-G2] Hardcoded JWT Secrets in Compliance Service**
   - **File:** `compliance/backend/compliance_backend/config.py:34-35`
   - **Impact:** `COMPLIANCE_JWT_SECRET` and `URIP_JWT_SECRET` have hardcoded default values ("change-me-in-production", "urip-shared-secret"). Unlike the main backend, there is no enforcement logic to prevent startup with these defaults in production. Attackers can forge administrative JWTs.
   - **Fix:** Implement `_enforce_jwt_secret_policy` in `compliance/backend/config.py` similar to `backend/config.py`.

3. **[CRIT-G3] Insecure Hybrid-SaaS Secret Management**
   - **File:** `backend/routers/agent_ingest.py:171` / `agent/reporter.py:53`
   - **Impact:** The `shared_secret_hash` (SHA256 of the plain secret) is used directly as the HMAC key for agent-to-cloud communication. Since the cloud DB stores this hash in the `agent_registrations` table, a DB compromise allows an attacker to impersonate every registered agent and push fraudulent metadata or intercept drilldown requests.
   - **Fix:** Use a secondary hash or a key derivation function (KDF) like HKDF to derive the HMAC key from the stored secret, ensuring the stored value cannot be used directly as a signing key.

4. **[CRIT-G4] Memory-exhaustion (DoS) in Evidence Export**
   - **File:** `compliance/backend/compliance_backend/services/evidence_service.py:391-413`
   - **Impact:** `export_evidence_bundle` builds a ZIP archive entirely in memory using `io.BytesIO`. It fetches ALL evidence for a tenant without pagination or size limits. A tenant with several GBs of evidence can trigger an OOM (Out Of Memory) crash, effectively causing a Denial of Service.
   - **Fix:** Implement a streaming ZIP generator or offload bundle creation to a background worker that writes to a temporary file/S3 bucket.

5. **[CRIT-G5] Default JWT Secret in Root .env**
   - **File:** `.env:23`
   - **Impact:** `JWT_SECRET_KEY` is set to `urip-dev-secret-change-in-production`. While `backend/config.py` warns about this, the existence of this default in the primary configuration file increases the risk of accidental deployment with weak secrets.
   - **Fix:** Remove the default value from `.env` and require it to be set via environment variables in deployment.

### HIGH
1. **[HIGH-G1] Timing Attack in Authentication**
   - **File:** `backend/routers/auth.py:100-112`
   - **Impact:** The login endpoint returns immediately if a user is not found, but proceeds to an expensive `verify_password` call if the user exists. This allows an attacker to enumerate valid email addresses based on response time.
   - **Fix:** Always perform a dummy `bcrypt` check when a user is not found to ensure consistent response timing.

2. **[HIGH-G2] Weak Password Policy**
   - **File:** `backend/routers/settings.py:38` / `backend/routers/tenants.py:154`
   - **Impact:** `UserCreate` and `TenantAdminUserCreate` only enforce `min_length=8`. For a security orchestration platform, this is insufficient. Furthermore, it lacks a `max_length` check, leaving it vulnerable to Long Password DoS against the `bcrypt` algorithm.
   - **Fix:** Increase `min_length` to 12 and set `max_length` to 72 (bcrypt limit).

3. **[HIGH-G3] Insecure File Upload Validation**
   - **File:** `compliance/backend/compliance_backend/routers/_upload_guards.py:91-92`
   - **Impact:** Relies exclusively on the client-provided `Content-Type` header. An attacker can upload a malicious script (e.g., `.php`, `.sh`) by spoofing the header to `image/png`.
   - **Fix:** Use a library like `python-magic` to verify the file's magic numbers/MIME type from the actual content.

4. **[HIGH-G4] Lack of Replay Protection in Agent Ingest**
   - **File:** `backend/routers/agent_ingest.py:145-154`
   - **Impact:** While `X-Timestamp` is checked for a 5-minute window, it is not checked for uniqueness (nonce). An attacker can capture and replay an agent's signed request multiple times within that 5-minute window.
   - **Fix:** Implement a short-lived cache (e.g., in Redis) to track and reject duplicate `X-Signature` values within the 5-minute window.

5. **[HIGH-G5] Nullable Tenant ID in Core Models**
   - **File:** `backend/models/risk.py:53` / `backend/models/audit_log.py:33`
   - **Impact:** `tenant_id` is defined as `nullable=True`. While the application layer (CritFix) enforces this, the database layer allows rows without tenant ownership, increasing the risk of data leakage if application-level checks are bypassed.
   - **Fix:** Update models to `nullable=False` and execute an Alembic migration to enforce this at the schema level.

### MEDIUM
1. **[MED-G1] XSS Vulnerability in Auditor Portal**
   - **File:** `compliance/frontend/js/api.js:239`
   - **Impact:** `openModal` sets `body.innerHTML = opts.body` if the body is a string. If user-supplied data (e.g., control titles or descriptions) is passed to a modal without proper escaping, reflected or stored XSS is possible.
   - **Fix:** Use `textContent` or a DOM sanitization library (e.g., DOMPurify) before setting `innerHTML`.

2. **[MED-G2] Hardcoded CORS Origins**
   - **File:** `compliance/backend/compliance_backend/config.py:27`
   - **Impact:** `CORS_ORIGINS` defaults to `localhost:3000/3001`. While configurable, hardcoded defaults in the config file are a maintenance and security risk.
   - **Fix:** Default to an empty list and require explicit configuration.

3. **[MED-G3] Missing Email Validation**
   - **File:** `backend/schemas/auth.py:5`
   - **Impact:** `LoginRequest` uses `email: str` instead of Pydantic's `EmailStr`. This allows malformed email strings to hit the database query layer.
   - **Fix:** Import and use `EmailStr` from `pydantic`.

4. **[MED-G4] Super-Admin Fallback Logic Flaw**
   - **File:** `backend/middleware/auth.py:95`
   - **Impact:** If a super-admin token does not include a `tenant_id`, `TenantContext.get()` will raise a `RuntimeError` in filtered routes. This leads to 500 errors for super-admins instead of a graceful "no tenant" state.
   - **Fix:** Update `apply_tenant_filter` to handle `None` for super-admins or ensure super-admins always have a "system" tenant context.

### LOW
1. **[LOW-G1] Brand Leakage in Threat Intel**
   - **File:** `backend/routers/threat_intel.py:121-125`
   - **Impact:** Hardcoded references to "Royal Enfield" domains in the simulator IOCs. This makes the product look unpolished and specific to one client.
   - **Fix:** Move IOC templates to a configuration file or database table.

2. **[LOW-G2] Hardcoded Agent DB Password**
   - **File:** `agent/local_db.py:46`
   - **Impact:** Default `urip_dev` password used in the agent's Postgres connection string.
   - **Fix:** Force `LOCAL_DB_URL` to be provided via environment variables without a default containing credentials.

---

## Domain Matrix

| Domain | Status | Key Issues |
| :--- | :--- | :--- |
| **A) Tenant Isolation** | PARTIAL | Nullable FKs in DB; Super-admin 500s. |
| **B) Auth (JWT)** | WEAK | Hardcoded secrets in Compliance; No email validation. |
| **C) RBAC** | OK | Role hierarchy is inverted but enforced. |
| **D) SQLi / ORM** | SAFE | SQLAlchemy used correctly. |
| **E) Secrets** | CRITICAL | Live production DB credentials in reference file. |
| **F) File Upload** | WEAK | Relies on spoofable Content-Type. |
| **G) Audit Trail** | OK | Implemented; integrity check for evidence added. |
| **H) Rate Limit / DoS** | WEAK | OOM DoS in evidence export. |
| **I) CORS/CSRF** | MED | Hardcoded origins. |
| **J) Dependencies** | OK | Migrated to PyJWT; python-jose removed. |
| **K) Auditor Portal** | WEAK | Potential XSS via innerHTML. |
| **L) Hybrid-SaaS Agent** | CRITICAL | HMAC key is the stored hash. |
| **M) Code Quality** | GOOD | Clean code, but security debt is high. |

---
*End of Audit Report*
