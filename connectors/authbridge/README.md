# AuthBridge BGV Connector

Pulls per-employee background verification status from AuthBridge into URIP.
Incomplete BGV is treated as a control failure for:

- HIPAA — 45 CFR § 164.308(a)(1)(ii)(B) (Risk management) and § 164.308(a)(3) (Workforce security).

## What this connector pulls

- Per-employee verification record
- Status: `initiated` / `in_progress` / `completed` / `failed`
- `checks_done` and `checks_pending` (criminal, education, address, …)
- `initiated_at` and `completed_at`

| Trigger | Severity | URIPRiskRecord.domain |
|---------|----------|------------------------|
| `status == "failed"` | high | identity |
| `status` ∈ {`initiated`, `in_progress`} | medium | identity |

## Setup

See `SETUP_GUIDE` rendered inline in the URIP Tool Catalog. Summary:

1. Email AuthBridge account manager → request API token + IP allow-list for URIP.
2. Receive bearer token + base URL via secure channel.
3. URIP → Tool Catalog → AuthBridge → paste token + base URL → Test Connection → Save.

AuthBridge does not yet expose self-serve token generation; account-managed only.

## Polling

Default 120 minutes. Webhooks supported (negotiate with AB account manager).

## Files

- `connector.py`  — AuthBridgeConnector class
- `api_client.py` — Thin httpx wrapper
- `schemas.py`    — Lightweight dataclasses
- `README.md`     — This file
