# OnGrid BGV Connector

Alternative BGV provider to AuthBridge. OnGrid offers Aadhaar / PAN / address /
criminal verification for Indian employees.

## Compliance mapping

- HIPAA — 45 CFR § 164.308(a)(1)(ii)(B) (Risk management) and § 164.308(a)(3) (Workforce security).

## What this connector pulls

- Per-candidate verification record
- `verification_status`: `pending` / `verified` / `rejected`
- `checks_completed` and `checks_remaining`
- `rejection_reason` where applicable

| Trigger | Severity | URIPRiskRecord.domain |
|---------|----------|------------------------|
| `verification_status == "rejected"` | high | identity |
| `verification_status == "pending"` | medium | identity |

## Setup

See `SETUP_GUIDE` rendered inline in the URIP Tool Catalog. Summary:

1. OnGrid console → Settings → API → Generate new key.
2. URIP → Tool Catalog → OnGrid → paste key → Test Connection → Save.

## Required tier

OnGrid **Business** plan or above (API tier).

## Polling

Default 120 minutes; webhooks supported.

## Files

- `connector.py`  — OnGridConnector class
- `api_client.py` — Thin httpx wrapper
- `schemas.py`    — Lightweight dataclasses
- `README.md`     — This file
