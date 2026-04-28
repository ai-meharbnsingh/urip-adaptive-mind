# CrowdStrike Falcon Connector

Live multi-product connector for the CrowdStrike Falcon platform, covering:

| Product           | URIP module | API path                                          | Domain                     |
|-------------------|-------------|---------------------------------------------------|----------------------------|
| Falcon Spotlight  | VM          | `/spotlight/queries|entities/vulnerabilities/v{1,2}` | `endpoint`              |
| Falcon Surface    | EASM        | `/falcon-surface/queries/external-assets/v1`      | `external_attack_surface`  |
| Falcon CNAPP      | CSPM        | `/cnapp/queries/findings/v1`                      | `cloud`                    |

## Required Falcon API scopes

Create the API client in **Falcon Console → Support → API Clients and Keys**, with these scopes per product:

| Product           | Required scope(s)                                 |
|-------------------|---------------------------------------------------|
| Falcon Spotlight  | `Vulnerabilities (Spotlight) — Read`              |
| Falcon Surface    | `Falcon Surface (External Assets) — Read`         |
| Falcon CNAPP      | `Cloud Posture — Read` and `Cloud IOM — Read`     |

You can scope a single API client to all three; URIP only needs **Read**.

## Falcon cloud / base URL

Pick the matching base URL for your tenant's region:

| Region    | Base URL                                  |
|-----------|-------------------------------------------|
| US-1 (default) | `https://api.crowdstrike.com`        |
| US-2      | `https://api.us-2.crowdstrike.com`        |
| EU-1      | `https://api.eu-1.crowdstrike.com`        |
| GovCloud  | `https://api.laggar.gcw.crowdstrike.com`  |

## ExPRT severity mapping

CrowdStrike scores every finding 0–100 on the ExPRT scale.  We normalize to the
URIP 4-tier severity ladder:

| ExPRT range | URIP severity |
|-------------|---------------|
| 80–100      | critical      |
| 60–79       | high          |
| 30–59       | medium        |
| 0–29        | low           |

For EASM and CNAPP records that lack an `exprt_score`, we fall back to the
vendor's native `risk_severity` / `severity` field if it is one of
`{critical, high, medium, low}`.

## Tenant credential schema

```jsonc
{
  "client_id":      "abcd...",                      // required
  "client_secret":  "xyz...",                       // required, secret
  "base_url":       "https://api.us-2.crowdstrike.com",
  "enabled_products": [
    "falcon_spotlight",
    "falcon_easm",
    "falcon_cnapp"
  ]
}
```

`enabled_products` is a subset filter — leave it out to enable all three.

## Authentication

OAuth2 client-credentials grant against `/oauth2/token`.  The bearer token is
cached in-process (~30-min TTL).  On HTTP 401 from any data endpoint we
refresh once and retry.  HTTP 429 honors `Retry-After`.

## What goes into `URIPRiskRecord`

| Source                    | `domain`                  | `asset`                              |
|---------------------------|---------------------------|--------------------------------------|
| `crowdstrike:falcon_spotlight` | `endpoint`            | `<hostname> (<local_ip>)`            |
| `crowdstrike:falcon_easm`      | `external_attack_surface` | `<asset_value>` (FQDN/IP/IP-range) |
| `crowdstrike:falcon_cnapp`     | `cloud`                | `<resource_id>` (e.g. ARN)             |

`asset_tier` is filled from CrowdStrike's grouping tag
`FalconGroupingTags/Criticality:Critical|High|Medium|Low`.
