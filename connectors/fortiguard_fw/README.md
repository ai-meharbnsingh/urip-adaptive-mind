# Fortinet Fortiguard Firewall Connector (URIP)

## What it pulls
- Blocked threats, IPS events (from syslog CEF)
- Blocked threats (optional REST polling)

## Modes
Set `ingest_mode`:
- `syslog`: parse Fortinet CEF log lines provided to `fetch_findings(..., syslog_lines=[...])`
- `api`: poll FortiGate REST endpoints for blocked threats

## Credentials
Syslog mode:
- `ingest_mode="syslog"` (no API credentials required)

API mode:
- `ingest_mode="api"`
- `base_url`
- `api_token`

Optional (test-only):
- `_transport` (httpx transport injection for unit tests)

## Output
Raw findings emitted with `raw_data.record_type`:
- `cef`
- `blocked_threat`

Normalization outputs `URIPRiskRecord` with `domain="network"` and `owner_team="Network Security"`.

