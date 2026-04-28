# CloudSEK Connector

Live connector for CloudSEK (XVigil + BeVigil + SVigil) → URIP.

## Required Credentials

| Key | Type | Required | Description |
|---|---|---|---|
| `api_key` | string | ✅ | CloudSEK API key (Authorization: Bearer) |
| `org_id` | string | ✅ | CloudSEK organization ID (X-Org-Id header) |
| `api_base` | string | ❌ | Base URL for white-label deployments (default: `https://api.cloudsek.com`) |
| `enabled_products` | list[str] | ❌ | Subset of products to poll: `["xvigil", "bevigil", "svigil"]` (default: all three) |
| `max_requests_per_minute` | int | ❌ | Rate-limit override (default: unset → falls back to 200 req/hour) |
| `tenant_id` | string | ❌ | Scoped into findings and session metadata |

## Data Pulled Per Product

### XVigil — External Threat Intelligence
- Dark web forum mentions
- Leaked credential detections
- Brand abuse / phishing site alerts
- Fake mobile app impersonation

### BeVigil — Attack Surface Monitoring
- Hardcoded secrets in mobile/web apps
- Exposed S3 buckets / unauthenticated endpoints
- Public API exposure
- Mobile app store scanning results

### SVigil — Supply Chain Risk
- Vendor critical CVEs
- Expired vendor certifications (SOC2, ISO27001, etc.)
- Third-party risk score changes

## Rate Limits

CloudSEK API ceiling is approximately **200 requests/hour** for most tenants.
The connector defaults to this conservative limit. You can raise or lower it
via `tenant_credentials['max_requests_per_minute']` if your CloudSEK contract
allows a higher tier.

## Sample Normalized Findings

### XVigil — Leaked Credentials
```json
{
  "finding": "Acme employee credentials found in BreachForums dump",
  "source": "cloudsek",
  "domain": "external_threat",
  "severity": "critical",
  "asset": "user@acme.in",
  "cvss_score": 0.0,
  "owner_team": "Threat Intelligence",
  "exploit_status": "active"
}
```

### BeVigil — Hardcoded Secret
```json
{
  "finding": "AWS access key hardcoded in Android APK",
  "source": "cloudsek",
  "domain": "mobile",
  "severity": "critical",
  "asset": "com.acme.mobile",
  "cvss_score": 0.0,
  "owner_team": "Threat Intelligence",
  "exploit_status": null
}
```

### SVigil — Vendor Certification Expired
```json
{
  "finding": "Vendor SOC2 certification expired",
  "source": "cloudsek",
  "domain": "supply_chain",
  "severity": "medium",
  "asset": "Acme Cloud",
  "cvss_score": 0.0,
  "owner_team": "Threat Intelligence",
  "exploit_status": null
}
```

## Notes

- **White-label customers:** Set `api_base` to your custom CloudSEK gateway URL.
- **Polling only:** This connector polls CloudSEK's REST API. Webhook ingest from
  CloudSEK is not implemented.
- **Cost:** Acme keeps its CloudSEK subscription. URIP only connects to it.
- **Retry behavior:** HTTP 429 responses are retried once after honoring the
  `Retry-After` header.
