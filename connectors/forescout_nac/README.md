# Network Access Control Connector (URIP)

## What it pulls
- Rogue device alerts
- NAC events (quarantine, policy violations, etc.)
- Device classification / inventory

## Sub-adapters
This connector selects an adapter via `tenant_credentials["nac_type"]`:
- `forescout` → Forescout eyeSight REST API (OAuth2 client credentials)
- `cisco_ise` → Cisco ISE ERS API (basic auth)

## Credentials
Common:
- `nac_type` (`forescout` or `cisco_ise`)
- `base_url`

Forescout:
- `client_id`
- `client_secret`

Cisco ISE:
- `username`
- `password`

Optional (test-only):
- `_transport` (httpx transport injection for unit tests)

## Output
Produces `RawFinding` records:
- `alert`, `event`, `device` (Forescout)
- `ise_endpoint` (Cisco ISE baseline)

Normalization outputs `URIPRiskRecord` with `domain="network"` and `owner_team="Network Security"`.

