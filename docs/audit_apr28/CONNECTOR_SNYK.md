# Snyk Connector — Build Summary (Apr 28, 2026)

## Status: COMPLETE — 49/49 tests GREEN

## Files Delivered

| File | Purpose |
|---|---|
| `connectors/snyk/__init__.py` | Package init — re-exports SnykConnector, SnykAPIClient, SnykIssue, SnykProject |
| `connectors/snyk/api_client.py` | Async HTTPX client for Snyk REST API v2024-10-15 |
| `connectors/snyk/schemas.py` | Pydantic v2 models — SnykIssue, SnykProject (JSON:API shape) |
| `connectors/snyk/connector.py` | SnykConnector — BaseConnector impl, @register_connector("snyk") |
| `connectors/snyk/README.md` | Operator reference |
| `connectors/base/setup_guides_data.py` | Added `_SNYK` SetupGuideSpec + registered in SETUP_GUIDES dict |
| `frontend/js/connector-schemas.js` | Added snyk entry (DAST category, 4 fields, logoUrl, statusPill=Live) |
| `backend/connector_loader.py` | Added `import connectors.snyk.connector  # noqa: F401` in DAST section |
| `tests/test_connectors/snyk/__init__.py` | Empty package marker |
| `tests/test_connectors/snyk/test_connector.py` | 49 tests — all green |

## API Details

- **API:** Snyk REST API v2024-10-15 (`https://api.snyk.io`)
- **Auth:** `Authorization: token {api_token}` header
- **Pagination:** cursor via `links.next` (JSON:API), capped at 1000 results
- **Healthcheck:** `GET /rest/orgs/{org_id}?version=2024-10-15`
- **Issues:** `GET /rest/orgs/{org_id}/issues?version=2024-10-15&effective_severity_level=critical,high&starting_after={iso8601}&limit=100`
- **Projects:** `GET /rest/orgs/{org_id}/projects?version=2024-10-15`

## Severity Mapping

| Snyk | URIP |
|---|---|
| critical | critical |
| high | high |
| medium | medium |
| low | low |

## Source Tagging

| Snyk type | URIP source |
|---|---|
| npm/pip/maven/gradle/... | `snyk:open_source` |
| docker/apk/deb/rpm/... | `snyk:container` |
| k8sconfig/terraformconfig/... | `snyk:iac` |
| sast/code | `snyk:code` |

## Test Coverage (49 tests)

- Registration + metadata (2)
- authenticate: valid token (header assertion), 401, 404 wrong org, missing fields (5)
- fetch_findings: severity filter in URL, starting_after ISO8601, 5xx error, unauthenticated guard (4)
- pagination: follows links.next cursor, caps at 1000 results (2)
- normalize: critical/high/medium severity, CVE extraction, no-CVE, source format for all 4 scan types, title in finding (10)
- mapping functions: severity map 9 variants, source type map 10 variants (parametrized, 19)
- health_check: ok before auth, ok after auth, degraded on 503 (3)
- credential fields: secret flag, required fields, CredentialFieldSpec instances, password type (4)

## INV-1 Compliance

SnykConnector is imported in `backend/connector_loader.py`, which is imported by `backend/main.py`. The `@register_connector("snyk")` decorator fires at process start — the connector is reachable through the global registry, scheduler, and `/api/connectors` router.

## Non-overlapping scope

Only touched files in the designated scope:
- `connectors/snyk/*` (new)
- `tests/test_connectors/snyk/*` (new)
- `frontend/js/connector-schemas.js` (snyk entry added after burpsuite)
- `connectors/base/setup_guides_data.py` (`_SNYK` + registry entry)
- `backend/connector_loader.py` (1 line in DAST section)

Did NOT touch: okta, ghas, hashicorp_vault, or any other connector files.
