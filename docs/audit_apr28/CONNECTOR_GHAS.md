# GHAS Connector — Build Summary (Apr 28, 2026)

## Status: COMPLETE — 29/29 tests passing

---

## Files Created

| File | Purpose |
|---|---|
| `connectors/ghas/__init__.py` | Package marker |
| `connectors/ghas/api_client.py` | Async httpx client — GitHub REST API v3 |
| `connectors/ghas/schemas.py` | Pydantic v2 models for 3 alert types |
| `connectors/ghas/connector.py` | GhasConnector — BaseConnector sync wrapper |
| `connectors/ghas/README.md` | Setup guide, PAT scopes, example payloads |
| `tests/test_connectors/ghas/__init__.py` | Test package marker |
| `tests/test_connectors/ghas/test_connector.py` | 29 tests (all green) |

## Files Modified

| File | Change |
|---|---|
| `connectors/base/setup_guides_data.py` | Added `_GHAS` SetupGuideSpec + `"ghas": _GHAS` in registry |
| `backend/connector_loader.py` | Added `import connectors.ghas.connector  # noqa: F401` in DAST section |
| `frontend/js/connector-schemas.js` | Added ghas entry with 3 credential fields |

---

## Architecture Decisions

**Category mapping**: GHAS is SAST + secret-scanning + SCA, not strictly DAST. Mapped to `CATEGORY="DAST"` / `MODULE_CODE="DAST"` as the closest existing URIP module until an "AppSec" module is added. Documented in connector docstring.

**Source sub-typing**: Three distinct `source` values (`ghas:code`, `ghas:secret`, `ghas:dependabot`) allow the URIP dashboard to aggregate or split by alert type without a separate connector per type.

**Severity logic**:
- Code scanning: `rule.security_severity_level` (primary) → `rule.severity` (fallback) → `"medium"` (default)
- Secret scanning: always `"critical"` with `exploit_status="active"` (leaked secret = P0 until rotated)
- Dependabot: `security_advisory.severity` directly (already uses CVSS-aligned taxonomy)

**Pagination**: `_paginate()` follows `Link: rel="next"` headers automatically. Hard cap at 1,000 items per alert type per sync cycle to prevent runaway pulls on large orgs.

**asyncio.run() pattern**: Mirrors the canonical Jira connector pattern. Each public method on `GhasConnector` is sync; it calls `asyncio.run()` over the async `GhasAPIClient` coroutine.

---

## Test Coverage (29 tests)

| Class | Tests | What's covered |
|---|---|---|
| TestGhasRegistration | 3 | Registry key, catalog metadata, secret=True on token field |
| TestGhasAuthenticate | 5 | Valid auth, 401, 404-org, missing org, missing token |
| TestGhasFetchFindings | 4 | Code scanning, secret, dependabot alerts, unauthenticated error |
| TestGhasNormalize | 9 | Critical/high/medium/rule-fallback severity, secret=always critical, dependabot advisory severity, file-path asset, dep: prefix |
| TestGhasPagination | 4 | Link header parser, no-next case, empty input, pagination follows Link, 1000-cap |
| TestGhasHealthCheck | 3 | Pre-auth ok, post-auth ok, degraded on 5xx |

---

## INV Compliance

- **INV-1 (no dead code)**: GhasConnector is imported in `connector_loader.py`, wired to registry → callable from /api/connectors router.
- **INV-4 (tests must execute)**: `python3 -m pytest tests/test_connectors/ghas/test_connector.py -v` → 29 passed 0 failed.
- **INV-5 (honest results)**: No synthetic data in production code paths. All mocking is test-only via respx.
- **INV-6 (never change tests to pass)**: All 29 tests pass against original source code. No test expectations weakened.
