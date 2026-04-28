# Tenable.io Vulnerability Manager Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `access_key` | ✅ | Tenable.io Access Key |
| `secret_key` | ✅ | Tenable.io Secret Key |
| `base_url` | ❌ | API base URL (default: `https://cloud.tenable.com`) |
| `tenant_id` | ❌ | URIP tenant identifier |

## What Data Is Pulled

1. **Asset inventory** — `GET /workbenches/assets`
   - Hostname, IPv4, OS, UUID
2. **Per-asset vulnerabilities** — `GET /workbenches/assets/{uuid}/vulnerabilities`
   - Plugin ID, plugin name, severity, CVSS v2/v3, CVE list, vulnerability state

Each `(asset, vulnerability)` pair becomes one `RawFinding` and normalizes to a `URIPRiskRecord`.

## Rate Limit Notes

- Tenable.io default: **1,500 requests/hour**.
- This connector throttles to **1,000 requests/hour** (3.6 s between requests) to leave headroom for other tools and burst traffic.
- The `max_assets` parameter (default 50) caps how many assets are inspected per tick. Increase with caution.

## Out-of-Scope / Follow-up

- Webhook-based push (Tenable.ot/TSC) instead of polling.
- Export-chunked APIs (`/vulns/export`, `/assets/export`) for very large estates.
- WAS (web-app scanning) findings — separate connector recommended.
- Full incremental sync with `last_found` / `first_found` filtering (currently fetches current state).
