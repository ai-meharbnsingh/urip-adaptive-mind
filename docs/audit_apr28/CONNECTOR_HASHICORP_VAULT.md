# HashiCorp Vault Connector — Build Summary

**Date:** 2026-04-28  
**Author:** Claude Sonnet 4.6  
**Status:** Complete — 18/18 tests green

---

## Files Created / Modified

### New files

| File | Purpose |
|------|---------|
| `connectors/hashicorp_vault/__init__.py` | Package marker |
| `connectors/hashicorp_vault/api_client.py` | Async HTTPX wrapper for Vault HTTP API v1 |
| `connectors/hashicorp_vault/schemas.py` | Pydantic v2 models (VaultHealth, VaultAuditDevice, VaultAuthMethod, VaultMount) |
| `connectors/hashicorp_vault/connector.py` | HashicorpVaultConnector — BaseConnector implementation |
| `connectors/hashicorp_vault/README.md` | Token creation, recommended ACL policy HCL |
| `tests/test_connectors/hashicorp_vault/__init__.py` | Test package marker |
| `tests/test_connectors/hashicorp_vault/test_connector.py` | 18 tests covering all specified cases |

### Modified files

| File | Change |
|------|--------|
| `connectors/base/setup_guides_data.py` | Added `_HASHICORP_VAULT` spec + registered in `SETUP_GUIDES` dict |
| `backend/connector_loader.py` | Added `import connectors.hashicorp_vault.connector` in Identity/NAC/PAM section |
| `frontend/js/connector-schemas.js` | Added `hashicorp_vault` entry with logo URL and credential fields |

---

## Architecture Decisions

### Posture connector, not CVE connector
Vault doesn't produce CVEs — it exposes secrets management hygiene. All findings use `external_id` = posture finding code (e.g. `VAULT-AUDIT-DISABLED`) rather than CVE IDs. Domain = `identity`. RISK_INDEX_DOMAIN = `"identity"`.

### /sys/health status code handling
Vault intentionally returns non-200 codes from `/sys/health`. The `VaultAPIClient.healthcheck()` method bypasses the standard `_request()` helper (which raises on 5xx) and handles the response directly:
- 200/429/473 → `urip_health_status = "healthy"` 
- 472 → `"degraded"`
- 501/503 → `"critical"`

### asyncio.run() pattern
Matches the canonical jira connector pattern. All async methods in `VaultAPIClient` are called via `_run_async(coro)` = `asyncio.run(coro)` — always creates a fresh event loop, avoiding Python 3.12+ deprecation of `get_event_loop()` in non-async contexts.

### SETUP_GUIDE wiring
`SETUP_GUIDE = SETUP_GUIDES.get("hashicorp_vault")` — the guide spec is in `setup_guides_data.py` (keeping the connector source file readable). This matches the Jira/ServiceNow pattern.

---

## Posture Findings Matrix

| Code | Severity | Trigger |
|------|----------|---------|
| VAULT-AUDIT-DISABLED | critical | No audit devices at /sys/audit |
| VAULT-SEALED | critical | sealed: true in /sys/health |
| VAULT-NOT-INITIALIZED | critical | initialized: false in /sys/health |
| VAULT-ROOT-TOKEN | high | URIP token has "root" in policies |
| VAULT-USERPASS-AUTH | medium | userpass auth method enabled |
| VAULT-KV-V1-MOUNT | low | KV engine with options.version="1" |
| VAULT-PERFORMANCE-STANDBY | info/low | performance_standby: true |

---

## Test Results

```
18 passed, 0 failed, 0 errors
Runtime: 0.13s
```

All 14 required tests pass, plus 4 extras (metadata, missing-cred validation, before-auth health check, before-auth not raising).

Adjacent connector regression: 144 passing (jira, ghas, okta, snyk) — no regressions.

---

## Non-Overlapping Scope Compliance

Only the following files were touched:
- `connectors/hashicorp_vault/*` (new)
- `tests/test_connectors/hashicorp_vault/*` (new)
- `frontend/js/connector-schemas.js` — one new entry added
- `connectors/base/setup_guides_data.py` — one new spec + one dict entry
- `backend/connector_loader.py` — one import line in PAM section

No files from Okta, GHAS, or Snyk scopes were modified.
