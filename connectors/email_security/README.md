# Email Security Connector

**Registered name:** `email_security`

Pulls phishing, BEC, malicious attachment, and email-hygiene alerts from Google Workspace (Alert Center API) and Microsoft 365 Defender (Graph Security API).

---

## Sub-Adapters

| Provider | APIs Used | Auth Flow |
|----------|-----------|-----------|
| `google_workspace` | Alert Center API (`v1beta1/alerts`) | OAuth2 service-account JWT bearer |
| `m365_defender` | Microsoft Graph Security API (`v1.0/security/alerts`) | OAuth2 client credentials |

## Authentication

### Google Workspace — OAuth2 Setup

1. Create a **Service Account** in Google Cloud Console.
2. Enable the **Google Workspace Alert Center API**.
3. Download the JSON key — this is `service_account_json`.
4. In Google Workspace Admin Console, grant the service account **domain-wide delegation** for the scope:
   ```
   https://www.googleapis.com/auth/apps.alerts
   ```
5. Configure connector credentials:

```json
{
  "provider": "google_workspace",
  "service_account_json": "{\"type\":\"service_account\",...}",
  "admin_email": "admin@example.com",
  "tenant_id": "tenant-abc"
}
```

### M365 Defender — OAuth2 Setup

1. Register an application in **Azure AD**.
2. Grant application permissions:
   ```
   SecurityEvents.Read.All
   SecurityAlert.Read.All
   ```
3. Create a client secret.
4. Configure connector credentials:

```json
{
  "provider": "m365_defender",
  "client_id": "your-azure-app-client-id",
  "client_secret": "your-client-secret",
  "tenant_id": "your-azure-tenant-id"
}
```

## Alert Types Ingested

- Phishing (user-reported + auto-detected)
- Business Email Compromise (BEC)
- Malicious attachments
- Suspicious sign-ins / impossible travel
- DMARC / SPF / DKIM failures (hygiene)

## Severity Mapping

| Alert Class | URIP Severity | CVSS Score |
|-------------|---------------|------------|
| Confirmed BEC, malware | critical | 9.0 |
| Confirmed phishing | high | 7.5 |
| Suspicious login / travel | medium | 5.0 |
| DMARC / SPF / DKIM gaps | low | 3.0 |

## Normalized Output

- `source`: `email_security:google_workspace` or `email_security:m365_defender`
- `domain`: `email`
- `asset`: `Email Infrastructure`

## Files

- `connector.py` — `EmailSecurityConnector(BaseConnector)`
- `api_client.py` — `GoogleWorkspaceAPIClient`, `M365DefenderAPIClient`
- `schemas.py` — Pydantic v2 alert models
