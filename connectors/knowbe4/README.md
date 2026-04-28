# KnowBe4 Connector

Pulls security awareness training completion + phishing simulation results from
KnowBe4 into URIP, treating incomplete training as a control failure for:

- ISO/IEC 27001:2022 — Annex A.6.3 (Awareness, education and training)
- SOC 2 — Trust Services Criterion CC1.4 (Commitment to competent personnel)

## What this connector pulls

- Training enrollments per user (module name, due date, status)
- Phishing simulation per-recipient outcomes (clicked / reported / no action)

Findings emitted:

| Trigger | Severity | URIPRiskRecord.domain |
|---------|----------|------------------------|
| `status` ∈ {`in_progress`,`past_due`,`not_started`,`enrolled`} | medium | identity |
| `clicked = true && reported = false` (phishing) | high | identity |

Each finding's `description` includes a **compliance citation** string the
compliance module uses to cross-link the URIP risk to the right control:

> Maps to compliance controls: ISO 27001:2022 A.6.3 (Awareness, education and
> training); SOC 2 CC1.4 (Demonstrate commitment to competent personnel).

## Setup

See `SETUP_GUIDE` rendered inline in the URIP Tool Catalog. Summary:

1. KnowBe4 console → Account Settings → API Access → Generate New Token.
2. Copy token (shown ONCE).
3. URIP → Tool Catalog → KnowBe4 → Configure → paste token + (optional) regional API base.
4. Test Connection → Save.

## Required tier

KnowBe4 **Diamond** or **Platinum** (Reporting API access). Silver/Gold do not
expose the Reporting API.

## Polling

Default 60 minutes. First sync ~10 minutes for an average tenant.

## Files

- `connector.py`     — KnowBe4Connector class (auth, fetch, normalize, health)
- `api_client.py`    — Thin httpx wrapper for the Reporting API
- `schemas.py`       — Lightweight dataclasses (TrainingEnrollment, PhishingRecipient)
- `README.md`        — This file
