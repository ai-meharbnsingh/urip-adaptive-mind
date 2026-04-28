# Snyk Connector — URIP

**Category:** DAST  
**Module:** DAST  
**Status:** Live  
**API Version:** Snyk REST API v2024-10-15  
**Vendor docs:** https://docs.snyk.io/snyk-api/snyk-rest-api

## What it does

Pulls vulnerability findings from Snyk-monitored projects into the URIP risk register.

Supported scan types:
- **Snyk Open Source** — dependency vulnerabilities in npm, pip, Maven, Gradle, etc.
- **Snyk Container** — container image SCA (Docker, apk, deb, rpm)
- **Snyk IaC** — infrastructure-as-code misconfiguration (Terraform, K8s, Helm, CloudFormation)
- **Snyk Code** — static analysis findings (Standard / Enterprise)

## Prerequisites

1. A Snyk account with at least one organization and monitored projects.
2. The org must have projects already imported (via SCM integration, CLI, or CI).
3. API token from **Account Settings → API Token** (not OAuth — token auth).

## Credentials

| Field | Description |
|---|---|
| `org_id` | Snyk Organization UUID — Snyk → Settings → General → Organization ID |
| `api_token` | API token — Snyk → Account Settings → API Token |
| `api_url` | Base URL (default `https://api.snyk.io`). Override for EU (`https://api.eu.snyk.io`) or AU (`https://api.au.snyk.io`) |
| `severity_filter` | Comma-separated minimum severities to ingest (default `critical,high`) |

## Data ingested

- Issue title and effective severity level (critical / high / medium / low)
- CVE IDs from `attributes.problems[].id`
- Package name and version from `attributes.coordinates[].representations[].dependency`
- Issue created/updated timestamps
- Deep-link URL to the issue in the Snyk app UI

## Not collected

- Issue history, comments, or audit logs
- EPSS scores (not provided by Snyk REST API directly)
- Private project details not accessible with the configured token

## Authentication

The connector uses Snyk's token-based auth:

```
Authorization: token {api_token}
```

The `api_url` field supports regional overrides:
- Global: `https://api.snyk.io`
- EU: `https://api.eu.snyk.io`
- AU: `https://api.au.snyk.io`

## Pagination

Snyk REST API paginates via cursor in `links.next`. The connector follows all pages automatically, capped at 1,000 results per fetch cycle.

## Severity mapping

| Snyk `effective_severity_level` | URIP severity |
|---|---|
| `critical` | `critical` |
| `high` | `high` |
| `medium` | `medium` |
| `low` | `low` |

## Source tagging

The `source` field on each `URIPRiskRecord` reflects the Snyk scan type:

| Snyk type | URIP source |
|---|---|
| npm, pip, maven, ... | `snyk:open_source` |
| docker, apk, deb, rpm, ... | `snyk:container` |
| k8sconfig, terraformconfig, ... | `snyk:iac` |
| sast, code | `snyk:code` |

## Troubleshooting

**401 Unauthorized** — Token is invalid or expired. Regenerate at Snyk → Account Settings → API Token.

**404 on org** — The `org_id` is wrong. Verify in Snyk → Settings → General → Organization ID. Note: it is the UUID, not the org slug.

**No issues returned** — Check that projects are imported and monitored in the org. Also verify the `severity_filter` includes the severity levels you expect.

## Testing

```bash
cd /path/to/project_33a
pytest tests/test_connectors/snyk/ -v
```
