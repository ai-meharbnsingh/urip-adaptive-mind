# URIP — Adaptive Mind — Changelog

## v1.0 — 2026-04-28

First production-ready release. **31 production connectors, 15 compliance frameworks, 5-round external tri-audit**.

### Connectors
- **Identity / SSO**: ms_entra. *(Okta in flight — see ROADMAP_GLOBAL_COVERAGE.md)*
- **NAC / PAM**: forescout_nac, cyberark_pam. *(HashiCorp Vault in flight)*
- **Endpoint (EDR / XDR)**: crowdstrike, sentinelone, manageengine_ec.
- **Cloud (CSPM)**: aws_cspm, azure_cspm, gcp_cspm.
- **Vulnerability Management**: tenable.
- **External Surface / Threat Intel**: cloudsek, easm (Censys + Shodan + Detectify multi-adapter).
- **SASE / Edge**: zscaler, netskope.
- **Firewall**: fortiguard_fw.
- **OT / ICS**: armis_ot.
- **DAST**: burp_enterprise. *(GitHub Advanced Security + Snyk in flight)*
- **Email Security**: email_security, m365_collab.
- **MDM**: manageengine_mdm.
- **ITSM**: jira (✓), servicenow (✓), manageengine_sdp (✓ all bidirectional).
- **LMS**: knowbe4, hoxhunt.
- **BGV**: authbridge, ongrid.
- **SIEM**: generic siem.
- **Bug bounty**: generic bug_bounty.
- **CERT-IN**: cert_in.
- **DLP**: gtb.
- **Simulators (dev/test)**: simulator, extended_simulator (hidden behind `?include_dev=true`).

### Compliance frameworks (15 — all seeded with cross-mappings)
SOC 2, ISO 27001:2022, ISO 27017, ISO 27018, ISO 27701, ISO 42001 (AI MS), GDPR, HIPAA, PCI DSS v4.0, India DPDP Act 2023, NIST CSF 2.0, CIS Controls v8, DORA, EU AI Act, NIS2.

### Architecture
- **Multi-tenant** with `TenantContext` middleware enforcing per-tenant isolation across every domain table.
- **Bidirectional ticketing** with HMAC-verified webhooks (Jira + ServiceNow + ManageEngine SDP).
- **Trust Center** + **Auto-Remediation** + **VAPT Vendor Portal**.
- **Sprinto-equivalent compliance module** at `/compliance/frameworks` with auditor portal, evidence requests, framework reports.
- **Event bus** with Redis pub/sub for cross-pod delivery (`URIP_DISTRIBUTED_EVENTS=1`).
- **Notifications** Redis-backed by default when `REDIS_URL` is set; falls back to in-process for dev/test.
- **RBAC scope hardening** (`require_scope`) on top-5 admin routes (tenants, modules, scoring, vapt, settings) — full overhaul tracked in `docs/SCALING.md`.

### Observability
- **Prometheus** `/metrics` endpoint via `prometheus-fastapi-instrumentator`.
- **Structured JSON logging** + optional SysLog/Loki shipping (`URIP_SYSLOG_HOST` / `URIP_LOKI_URL`).
- **Health probes** `/api/health` (process), `/api/ready` (DB + Redis async ping), `/healthz` (k8s-style liveness).
- **Audit log** persists every state-changing action with tenant + user + IP.

### Security hardening
- **Multi-stage Dockerfile** with non-root `appuser` (UID 1001).
- **Pydantic v2** migration (1,659 → 0 deprecation warnings on `backend/config.py`).
- **JWT_SECRET_KEY** policy enforcement at boot — refuses to start in production with the well-known dev default.
- **Tenant isolation** on the ticketing webhook (cross-tenant data leak risk closed in commit `4d52877`).
- **Admin password** in `bootstrap_dev.py` env-driven via `URIP_DEV_ADMIN_PASSWORD` or auto-generated 20-char.
- **Rate limiting** Redis-backed in prod via `RATE_LIMIT_STORAGE_URI=redis://...`.
- **CI security job** runs `pip-audit` against `requirements.txt` on every PR.
- **Backup script** with PIPESTATUS-safe pruning + 14-day retention.

### Deployment
- **Vercel** for frontend (`urip.adaptive-mind.com`) with rewrite to backend.
- **Hostinger VPS** for backend + compliance + Redis + Postgres via `docker-compose.prod.yml`.
- **nginx** reverse-proxy with `/api/*` → `:8089`, `/compliance-api/*` → `:8091`.

### Audit trail (5 rounds, 3 external auditors)

| Round | Codex | Kimi | Gemini |
|---|---|---|---|
| A (baseline) | 84 | 58 | 72 |
| B (after Bucket A+B+C fixes) | 61 | 84 | 82 |
| C (after round-B fixes) | 57 | 88 | 92 |
| D (after Bucket D1+D2+D3 fixes) | 41 (REJECT — schemas untracked) | 90 | 98 |
| E (after schemas committed + datetime fixes) | 72 | 85 | 90 |

Final commit: `fefabe3` (round-E gap fixes — clean-clone test guard, ?include_dev opt-in, alembic 0017 tenant rename, naming consistency).

### Known deferred work (see `docs/SCALING.md` + `docs/ROADMAP_GLOBAL_COVERAGE.md`)
- Full RBAC overhaul (only top-5 admin routes scoped today).
- `_NOTIFICATIONS` durable event log via Redis Streams (currently pub/sub only).
- TLS between Vercel and VPS — pending DNS propagation for `api.urip.adaptive-mind.com`, then certbot.
- Connector roadmap P0s: Workday HRIS, MS Defender for Endpoint, Wiz / Prisma Cloud / Orca CNAPP.
- Compliance frameworks: SEC, CMMC 2.0, HITRUST, SOC 1, ISO 22301, Singapore PDPA, Australia, Brazil LGPD, UAE/Saudi PDPL.
