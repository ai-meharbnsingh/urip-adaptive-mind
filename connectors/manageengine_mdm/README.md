# ManageEngine MDM Connector

## Overview
Pulls mobile security data from ManageEngine MDM:
- **Jailbroken Devices**: iOS/Android root or jailbreak detection
- **Non-Compliant Mobile**: devices violating MDM policy
- **Lost/Stolen Events**: device loss or theft reports

## Required API Permissions
- API Token with read access to:
  - Device Management module
  - Compliance & Events

## Authentication
REST API token authentication:
1. Generate an API token in ManageEngine MDM (Admin → API → API Token)
2. Provide Base URL and API Token

## Sample Finding (Normalized)
```json
{
  "finding": "Jailbroken Device: iPhone-CEO",
  "source": "manageengine_mdm",
  "domain": "mobile",
  "severity": "critical",
  "asset": "iPhone-CEO",
  "owner_team": "Mobile Security",
  "cvss_score": 0.0
}
```

## Rate Limits
- Default: 2,000 requests/hour
