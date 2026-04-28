# Hoxhunt Connector

Pulls phishing-training engagement + behaviour-change scores from Hoxhunt into
URIP, treating low engagement and failed simulations as compliance findings.

## Compliance mapping

- ISO/IEC 27001:2022 — Annex A.6.3 (Awareness, education and training)
- SOC 2 — Trust Services Criterion CC1.4 (Commitment to competent personnel)

## What this connector pulls

- Per-user training engagement (active / inactive / paused) + behaviour score (0.0–1.0)
- Phishing simulation responses (clicked / reported / ignored)

| Trigger | Severity | URIPRiskRecord.domain |
|---------|----------|------------------------|
| `training_status` ∈ {`inactive`, `paused`, `lapsed`} | low / medium (by score) | identity |
| `outcome == "clicked"` (phishing) | high | identity |

Each finding's description includes the same compliance citation as KnowBe4.

## Setup

See `SETUP_GUIDE` rendered inline in the URIP Tool Catalog. Summary:

1. Hoxhunt → Settings → Integrations → API Tokens → Create token.
2. Select scopes: `read:users`, `read:simulations`.
3. URIP → Tool Catalog → Hoxhunt → paste token → Test Connection → Save.

## Required tier

Hoxhunt **Standard** or **Enterprise** (API access). Trial accounts do not
expose the API.

## Polling

Default 60 minutes; webhooks supported (set up via Hoxhunt console).

## Files

- `connector.py`  — HoxhuntConnector class
- `api_client.py` — Thin httpx wrapper
- `schemas.py`    — Lightweight dataclasses
- `README.md`     — This file
