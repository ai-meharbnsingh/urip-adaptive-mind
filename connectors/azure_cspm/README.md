# Azure CSPM Connector

Azure Cloud Security Posture Management connector for URIP.

## Required Azure AD Permissions

The service principal needs the following **read-only** role assignments (e.g., via *Reader* or a custom role) on the subscriptions to be scanned:

- `Microsoft.PolicyInsights/policyStates/queryResults/read`
- `Microsoft.Security/assessments/read`
- `Microsoft.Security/alerts/read`
- `Microsoft.ResourceGraph/resources/read`
- `Microsoft.Resources/subscriptions/read`

## Credential Fields

| Field           | Type   | Required | Description                        |
|-----------------|--------|----------|------------------------------------|
| `tenant_id`     | string | Yes      | Azure AD tenant ID (Directory ID)  |
| `client_id`     | string | Yes      | Azure AD application (client) ID   |
| `client_secret` | string | Yes      | Azure AD application client secret |

Optional:

- `base_url` — defaults to `https://management.azure.com`

## Data Sources

- **Azure Policy** — non-compliant policy states per subscription
- **Microsoft Defender for Cloud** — security recommendations (assessments)
- **Microsoft Defender for Cloud** — security alerts
- **Azure Resource Graph** — custom KQL queries (exposed via `api_client.query_resource_graph`)
