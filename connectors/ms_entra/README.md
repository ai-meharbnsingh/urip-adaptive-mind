# Microsoft Entra ID Connector

## Required Credential Keys

| Key | Required | Description |
|---|---|---|
| `tenant_id` | ✅ | Microsoft Entra tenant ID (directory ID) |
| `client_id` | ✅ | App registration client ID |
| `client_secret` | ✅ | App registration client secret |

## What Data Is Pulled

1. **Risky Users** — `GET /v1.0/identityProtection/riskyUsers`
   - User ID, UPN, risk state, risk level
2. **Risk Detections** — `GET /v1.0/identityProtection/riskDetections`
   - Detection ID, UPN, riskEventType, risk level, detected date
3. **Risky Sign-Ins** — `GET /v1.0/auditLogs/signIns?$filter=riskLevelDuringSignIn ne 'none'`
   - Sign-in ID, UPN, risk level during sign-in, risk state
4. **CA Policy Results** — `GET /v1.0/identityProtection/conditionalAccessPolicyResults`
   - Policy ID, policy name, result, UPN

## Identity Risk Severity Mapping

Per `MASTER_BLUEPRINT.md` Identity Risk carry-forward:

| Entra riskEventType | URIP Severity |
|---|---|
| `leakedCredentials` | **critical** |
| `maliciousIPAddress` | **critical** |
| `mfaFatigue` | **high** |
| `atypicalTravel` | **high** |
| `anonymizedIPAddress` | **medium** |
| `suspiciousAPITraffic` | **medium** |
| (other / unknown) | **medium** |

All other categories (riskyUser, riskySignIn, caPolicy) use their native
`riskLevel` / `riskLevelDuringSignIn` fields mapped directly.

## Rate Limit Notes

- Microsoft Graph API rate limits: ~10,000 requests per 10 minutes per app.
- This connector handles HTTP 429 throttling by reading the `Retry-After` header
  and sleeping before retrying once.
- Pagination via `@odata.nextLink` is automatically followed for all list endpoints.

## Sample Normalized Finding

```json
{
  "finding": "Risk Detection: leakedCredentials",
  "source": "ms_entra",
  "domain": "identity",
  "cvss_score": 0.0,
  "severity": "critical",
  "asset": "alice@example.com",
  "owner_team": "IAM",
  "description": "Microsoft Entra risk detection: leakedCredentials for user alice@example.com. Detected: 2024-01-15T10:30:00Z."
}
```

## Out-of-Scope / Follow-up

- Privileged Identity Management (PIM) role activation logs.
- Entitlement management access package assignments.
- Real-time sign-in log streaming (Event Hubs).
