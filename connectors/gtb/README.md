# GTB Endpoint Protector Connector

## Overview
Pulls data loss prevention events from GTB Endpoint Protector:
- **DLP Policy Violations**: sensitive data movement across channels
- **USB Block Events**: unauthorized removable media usage
- **Exfiltration Attempts**: bulk data transfer to external destinations

## Required API Permissions
- API Key with read access to:
  - Violations module
  - Events module

## Authentication
REST API key authentication:
1. Generate an API key in GTB Admin Console (Admin → API Integration)
2. Provide Base URL and API Key

## Sample Finding (Normalized)
```json
{
  "finding": "Exfiltration Attempt: personal-dropbox.com",
  "source": "gtb",
  "domain": "dlp",
  "severity": "high",
  "asset": "WS-FINANCE-03",
  "owner_team": "Data Protection",
  "cvss_score": 0.0
}
```

## Rate Limits
- Default: 3,000 requests/hour
