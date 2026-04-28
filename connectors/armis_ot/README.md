# Armis OT Connector (URIP)

## What it pulls
- OT asset inventory (industrial/manufacturing devices)
- Vulnerabilities (CVEs / CVSS where present)
- Risk events (unsafe protocols, anomalous behavior, etc.)

## Auth
- Armis cloud REST API
- API token via `Authorization: Bearer <token>`

## Credentials
Required:
- `base_url` (tenant API root)
- `api_token`

Optional (test-only):
- `_transport` (httpx transport injection for unit tests)

## Output
Each upstream object is emitted as a `RawFinding` with `raw_data.record_type`:
- `asset`
- `vulnerability`
- `risk_event`

Normalization returns `URIPRiskRecord` with:
- `domain="ot"`
- `owner_team="OT Security"`

