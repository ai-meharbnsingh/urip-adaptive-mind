# Netskope CASB + DLP Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `client_id` | ✅ | Netskope API client ID |
| `client_secret` | ✅ | Netskope API client secret |
| `base_url` | ✅ | Netskope tenant base URL, e.g. `https://tenant.goskope.com` |
| `tenant_id` | ❌ | URIP tenant identifier |

## What Data Is Pulled

1. **DLP Incidents** — `GET /api/v2/incidents/dlp`
   - Incident ID, name, severity, user, app, policy, timestamp
2. **Cloud Threats** — `GET /api/v2/incidents/threats`
   - Threat ID, name, severity, user, app, malware type, timestamp
3. **Anomalies** — `GET /api/v2/incidents/anomalies`
   - Anomaly ID, name, severity, user, app, anomaly type, timestamp

Each finding normalizes to a `URIPRiskRecord` with domain `cloud`.

## Rate Limit Notes

- Netskope API rate limits vary by tenant tier.
- OAuth2 token is obtained once per poll cycle and cached in memory.
- No explicit throttling is applied; rely on Netskope cloud-side rate limits.

## Sample Normalized Finding

```json
{
  "finding": "DLP: PII Exfiltration",
  "source": "netskope",
  "domain": "cloud",
  "cvss_score": 0.0,
  "severity": "high",
  "asset": "user@example.com",
  "owner_team": "Data Protection",
  "description": "Netskope DLP violation: PII Exfiltration. User: user@example.com. App: Gmail."
}
```

## Out-of-Scope / Follow-up

- Real-time event streaming (Netskope Event Export).
- Netskope Private Access (NPA) tunnel data.
- Bidirectional policy remediation (read-only for now).
