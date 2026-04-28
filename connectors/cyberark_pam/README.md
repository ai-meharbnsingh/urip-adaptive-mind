# CyberArk PAM Connector (URIP)

## What it pulls
- Shared credentials usage events
- Privileged session anomalies
- Vault access logs

## Auth
- CyberArk PVWA REST API
- API key logon (`/PasswordVault/API/Auth/APIKey/Logon`)
- Refcounted session: one logon + one logoff per fetch cycle (safe for multiple upstream calls)

## Credentials
Required:
- `base_url`
- `api_key`

Optional (test-only):
- `_transport` (httpx transport injection for unit tests)

## Output
Raw findings are emitted with `raw_data.record_type`:
- `vault_access`
- `session_anomaly`
- `credential_usage`

Normalization outputs `URIPRiskRecord` with:
- `domain="identity"`
- `owner_team="Identity & Access"`

