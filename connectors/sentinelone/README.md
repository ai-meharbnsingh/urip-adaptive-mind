# SentinelOne Singularity Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `api_token` | ✅ | SentinelOne API Token (ApiToken scheme) |
| `base_url` | ✅ | Management console base URL, e.g. `https://tenant.sentinelone.net` |
| `tenant_id` | ❌ | URIP tenant identifier |

## What Data Is Pulled

1. **Threats** — `GET /web/api/v2.1/threats?createdAt__gte={since}`
   - Threat ID, classification, mitigated status, agent hostname, agent OS, threat name, file info
2. **Agents** — `GET /web/api/v2.1/agents`
   - Agent ID, computer name, OS name, active/inactive status

Inactive agents are surfaced as medium-severity findings so URIP can track endpoint coverage gaps.

## Rate Limit Notes

- SentinelOne rate limits vary by tenant tier (typically 100–300 req/min).
- This connector throttles to **200 requests/minute** (300 ms between requests) as a safe default.
- Cursor pagination is used for both threats and agents.

## Out-of-Scope / Follow-up

- SentinelOne **Deep Visibility** raw-event queries.
- SentinelOne **Ranger** network-discovery data.
- SentinelOne ** Vigilance / MDR** case data.
- Agent-level vulnerability data from the SentinelOne Vulnerability module (requires separate API scope).
- Bidirectional mitigation (quarantine, rollback) — read-only for now.
