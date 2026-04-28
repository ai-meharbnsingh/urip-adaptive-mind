# ManageEngine ServiceDesk Plus Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `auth_method` | ✅ | Authentication method: `oauth` or `token` |
| `base_url` | ✅ | SDP instance base URL, e.g. `https://sdp.example.com` |
| `client_id` | ✅ (OAuth) | OAuth client ID |
| `client_secret` | ✅ (OAuth) | OAuth client secret |
| `refresh_token` | ✅ (OAuth) | OAuth refresh token |
| `auth_token` | ✅ (Token) | Legacy auth token |
| `tenant_id` | ❌ | URIP tenant identifier |

## What Data Is Pulled

1. **Tickets (Requests)** — `GET /api/v3/requests`
   - Ticket ID, subject, description, priority, category, requester, status, created time
   - Only tickets with `category == "Security"` (or empty category) are normalized

## Priority → Severity Mapping

| SDP Priority | URIP Severity |
|---|---|
| `Critical` | **critical** |
| `High` | **high** |
| `Medium` | **medium** |
| `Low` | **low** |
| (other / missing) | **medium** |

## Bidirectional Capability

`create_ticket(risk_data: dict) -> str`

Creates a new ticket in SDP from URIP risk data.

Required keys in `risk_data`:
- `subject` — Ticket title
- `description` — Ticket body

Optional keys:
- `priority` — Defaults to `Medium`
- `requester` — Defaults to `urip@example.com`
- `category` — Defaults to `Security`

Returns the created SDP ticket ID.

## Sample Normalized Finding

```json
{
  "finding": "SDP Ticket: Suspicious Login Detected",
  "source": "manageengine_sdp",
  "domain": "application",
  "cvss_score": 0.0,
  "severity": "high",
  "asset": "security@example.com",
  "owner_team": "IT Service Management",
  "description": "ManageEngine SDP ticket #ticket-001: Suspicious Login Detected. Status: Open. Priority: High. Description: Multiple failed login attempts from unknown IP."
}
```

## Out-of-Scope / Follow-up

- Change management (CMDB) integration.
- Asset auto-discovery from SDP CMDB.
- SLA breach alerting (read-only for now).
