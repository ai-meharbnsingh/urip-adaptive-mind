# Zscaler ZIA / ZTA / CASB Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `api_key` | ✅ | Zscaler API key |
| `username` | ✅ | Zscaler admin username |
| `password` | ✅ | Zscaler admin password |
| `cloud` | ✅ | Zscaler cloud name (e.g. `zscalerone`, `zscalertwo`, `zscaler`) |
| `tenant_id` | ❌ | URIP tenant identifier |

## What Data Is Pulled

1. **Web Threats** — `GET /api/v1/threatIntel/threats`
   - Threat ID, name, URL, severity, device, action
2. **Shadow SaaS Apps** — `GET /api/v1/casb/saasApps`
   - App name, category, risk score, user count, sanctioned status
3. **Admin Audit Logs** — `GET /api/v1/users/admin/auditLogs`
   - Admin user, action, resource, severity, timestamp

Each finding normalizes to a `URIPRiskRecord` with domain mapped as:
- `web_threat` → `network`
- `shadow_saas` → `cloud`
- `casb_violation` → `network`

## Rate Limit Notes

- Zscaler API rate limits vary by tenant tier.
- This connector uses a single authenticated session per poll cycle.
- No explicit throttling is applied; rely on Zscaler cloud-side rate limits.

## Sample Normalized Finding

```json
{
  "finding": "Shadow SaaS: UnsanctionedFileShare",
  "source": "zscaler",
  "domain": "cloud",
  "cvss_score": 0.0,
  "severity": "high",
  "asset": "UnsanctionedFileShare",
  "owner_team": "Cloud Security",
  "description": "Zscaler CASB detected unsanctioned SaaS app: UnsanctionedFileShare. Category: Cloud Storage. Users: 12. Risk score: 85."
}
```

## Out-of-Scope / Follow-up

- Real-time log streaming (NSS) instead of polling.
- Zscaler Private Access (ZPA) tunnel health data.
- Bidirectional policy changes (read-only for now).
