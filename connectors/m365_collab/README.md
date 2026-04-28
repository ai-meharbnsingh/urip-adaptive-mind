# Microsoft 365 Collaboration Connector

## Overview
Pulls collaboration risk data from Microsoft 365 via Microsoft Graph API:
- **SharePoint**: anonymous link sharing, external sharing audit logs, sensitive label violations
- **OneDrive**: external sharing events
- **Teams**: data exposure events (public teams)

## Required Graph API Scopes
- `Sites.Read.All` — SharePoint site enumeration
- `User.Read.All` — User and OneDrive access
- `Team.Read.All` — Teams enumeration
- `AuditLog.Read.All` — Audit log access (future enhancement)

## Authentication
OAuth2 client credentials flow:
1. Register an application in Azure AD
2. Grant admin consent for the scopes above
3. Provide Tenant ID, Client ID, and Client Secret

## Sample Finding (Normalized)
```json
{
  "finding": "Public Teams Exposure: Engineering",
  "source": "m365_collab:teams",
  "domain": "collaboration",
  "severity": "high",
  "asset": "Engineering",
  "owner_team": "IT",
  "cvss_score": 0.0
}
```

## Rate Limits
- Default: 10,000 requests/hour
- Microsoft Graph throttling applies per tenant
