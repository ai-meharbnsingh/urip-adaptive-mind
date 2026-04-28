# GCP Cloud Security Posture Management Connector

## Required GCP Permissions (Read-Only)

The service account needs the following granular permissions:

| API | Permission |
|---|---|
| Security Command Center | `securitycenter.findings.list` |
| Cloud Asset Inventory | `cloudasset.assets.list` |
| Recommender | `recommender.recommendations.list` |

Recommended IAM roles: `Security Center Findings Viewer`, `Cloud Asset Viewer`, `Recommender Viewer`.

## Credential Fields

| Key | Required | Description |
|---|---|---|
| `service_account_json` | ✅ (or `project_id` + ADC) | GCP service account key JSON contents (dict) |
| `project_id` | ✅ (for ADC) | GCP project identifier |
| `tenant_id` | ❌ | URIP tenant identifier |
| `org_id` | ❌ | GCP organization identifier (for org-level SCC sources) |

## Data Sources

1. **Security Command Center Findings** — `GET /v1/{parent}/findings`
   - Severity, category, description, resource name, event time
2. **Cloud Asset Inventory** — `GET /v1/projects/{project_id}/assets`
   - Asset name, type, resource data, IAM policy, ancestors
3. **Security Recommender** — `GET /v1/projects/{project_id}/locations/-/recommenders/{recommender}/recommendations`
   - Priority, subtype, description, content overview

Each result becomes one `RawFinding` and normalizes to a `URIPRiskRecord`.

## Notes

- The connector uses **synchronous HTTPX** and implements a simple exponential-backoff retry for HTTP 429.
- Authentication supports the **service-account JWT flow** or **Application Default Credentials (ADC)** via the GCE metadata server.
- `fetch_findings` pulls the current state; full incremental sync with `since` filtering is left to the scheduler in production.
