# ManageEngine Endpoint Central Connector

## Overview
Pulls endpoint security data from ManageEngine Endpoint Central:
- **Patch Status**: per-endpoint compliance state
- **Missing Patches**: critical and important patch gaps
- **Compliance Score**: overall endpoint health metric

## Required API Permissions
- API Token with read access to:
  - Patch Management module
  - Computer inventory

## Authentication
REST API token authentication:
1. Generate an API token in Endpoint Central (Admin → API → API Token)
2. Provide Base URL and API Token

## Sample Finding (Normalized)
```json
{
  "finding": "Missing Patch: KB5028185",
  "source": "manageengine_ec",
  "domain": "endpoint",
  "severity": "critical",
  "asset": "WS-DEVELOPER-01",
  "owner_team": "Endpoint Security",
  "cvss_score": 0.0
}
```

## Rate Limits
- Default: 2,000 requests/hour
