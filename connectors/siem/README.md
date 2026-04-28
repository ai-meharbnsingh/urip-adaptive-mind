# Generic SIEM / SoC Connector

**Registered name:** `siem`

Unified connector for Splunk, Elastic, and IBM QRadar. Runs tenant-configured saved searches or queries and normalizes returned security events into URIP risk records.

---

## Sub-Adapters

| SIEM Type | Auth Method | Validation Endpoint |
|-----------|-------------|---------------------|
| `splunk` | Bearer token **or** Basic auth (username + password) | `GET /services/server/info` |
| `elastic` | API Key (`Authorization: ApiKey <key>`) | `GET /_cluster/health` |
| `qradar` | SEC token header | `GET /api/system/about` |

## Authentication

### Splunk

```json
{
  "siem_type": "splunk",
  "base_url": "https://splunk.example.com",
  "token": "splunk-hec-token-123",
  "tenant_id": "tenant-abc"
}
```

Or with basic auth:

```json
{
  "siem_type": "splunk",
  "base_url": "https://splunk.example.com",
  "username": "admin",
  "password": "changeme",
  "tenant_id": "tenant-abc"
}
```

### Elastic

```json
{
  "siem_type": "elastic",
  "base_url": "https://elastic.example.com",
  "api_key": "elastic-api-key-456",
  "tenant_id": "tenant-abc"
}
```

### QRadar

```json
{
  "siem_type": "qradar",
  "base_url": "https://qradar.example.com",
  "sec_token": "qradar-sec-token-789",
  "tenant_id": "tenant-abc"
}
```

## Fetch Findings

Each adapter executes the tenant's configured search at poll time:

- **Splunk:** `POST /services/search/jobs/export` with `search | savedsearch "<saved_search>"`
- **Elastic:** `POST /<index>/_search` with the provided Query DSL
- **QRadar:** `POST /api/ariel/searches` → poll for completion → `GET /results`

## Severity Mapping

| Native Severity | URIP Severity | CVSS Score |
|-----------------|---------------|------------|
| critical | critical | 9.0 |
| high | high | 7.5 |
| medium | medium | 5.0 |
| low | low | 3.0 |
| unknown / missing | medium | 5.0 |

### QRadar Numeric Severity
- ≥ 9 → critical
- 7–8 → high
- 4–6 → medium
- < 4 → low

## Domain Inference

The connector reads `domain_hint` from the raw event when available:
- `network` (default)
- `endpoint`
- `identity`
- `application`

## Files

- `connector.py` — `SiemConnector(BaseConnector)` with sub-adapter dispatch
- `api_client.py` — `SplunkAPIClient`, `ElasticAPIClient`, `QRadarAPIClient`
- `schemas.py` — Pydantic v2 per-adapter raw shapes + common event wrapper
