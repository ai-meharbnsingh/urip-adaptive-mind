# Burp Suite Enterprise Connector

## Overview
Pulls DAST findings from Burp Suite Enterprise:
- **Scan Findings**: XSS, SQLi, CSRF, command injection, etc.
- **Application Targets**: per-URL vulnerability mapping
- **Severity**: critical, high, medium, low, info

## Required API Permissions
- API Key with read access to:
  - Scan results
  - Issue data

## Authentication
REST API key authentication:
1. Generate an API key in Burp Enterprise (Settings → API)
2. Provide Base URL and API Key

## Sample Finding (Normalized)
```json
{
  "finding": "DAST: SQL Injection",
  "source": "burp_enterprise",
  "domain": "application",
  "severity": "critical",
  "asset": "https://app.example.com/login",
  "owner_team": "Application Security",
  "cvss_score": 0.0
}
```

## Rate Limits
- Default: 1,000 requests/hour
