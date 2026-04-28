# Bug Bounty Connector

**Registered name:** `bug_bounty`

Ingests vulnerability reports from HackerOne and Bugcrowd. Supports both API polling and real-time webhook ingestion.

---

## Sub-Adapters

| Platform | API Endpoint | Auth |
|----------|--------------|------|
| `hackerone` | `GET /v1/reports` | Bearer token (`Authorization: Bearer <token>`) |
| `bugcrowd` | `GET /submissions` | Token auth (`Authorization: Token <token>`) |

## Authentication

### HackerOne

1. Generate an **API token** in your HackerOne program settings.
2. Optionally scope to a `program_handle`.
3. Configure:

```json
{
  "platform": "hackerone",
  "api_token": "h1-api-token-123",
  "program_handle": "acme-corp",
  "tenant_id": "tenant-abc"
}
```

### Bugcrowd

1. Generate an **API token** from Bugcrowd → User Settings → API.
2. Configure:

```json
{
  "platform": "bugcrowd",
  "api_token": "bc-api-token-456",
  "tenant_id": "tenant-abc"
}
```

## Webhook Ingest

Expose a POST endpoint in your API layer (e.g., `/api/bug-bounty/webhook`) and forward payloads to:

```python
connector = BugBountyConnector()
record = connector.ingest_webhook(payload, tenant_id="tenant-abc")
# record is a URIPRiskRecord — persist directly to the Risk table
```

**Expected payload shape:**

```json
{
  "platform": "hackerone",
  "report": { ...raw HackerOne report object... }
}
```

Or for Bugcrowd:

```json
{
  "platform": "bugcrowd",
  "report": { ...raw Bugcrowd submission object... }
}
```

## Severity Mapping

| HackerOne | Bugcrowd | URIP Severity | CVSS Score |
|-----------|----------|---------------|------------|
| critical | P1 (priority 1) | critical | 9.0 |
| high | P2 | high | 7.0 |
| medium | P3 | medium | 5.0 |
| low | P4 | low | 3.0 |

## Normalized Output

- `source`: `bug_bounty:hackerone` or `bug_bounty:bugcrowd`
- `domain`: `application`
- `description`: Includes researcher `remediation_recommendation` when available
- `asset`: Target URL / scope identifier

## Files

- `connector.py` — `BugBountyConnector(BaseConnector)` + `ingest_webhook()`
- `api_client.py` — `HackerOneAPIClient`, `BugcrowdAPIClient`
- `schemas.py` — Pydantic v2 report models
