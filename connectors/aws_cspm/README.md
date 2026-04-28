# AWS CSPM Connector

Cloud Security Posture Management connector for Amazon Web Services.

## Required IAM Permissions (Read-Only)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "config:DescribeConfigRules",
        "config:DescribeComplianceByConfigRule",
        "securityhub:GetFindings",
        "guardduty:ListDetectors",
        "guardduty:ListFindings",
        "guardduty:GetFindings",
        "access-analyzer:ListAnalyzers",
        "access-analyzer:ListFindings"
      ],
      "Resource": "*"
    }
  ]
}
```

## Credential Fields

- `access_key` — AWS Access Key ID
- `secret_key` — AWS Secret Access Key
- `region` — AWS region (default: `us-east-1`)
- `session_token` — Optional session token for temporary credentials

## Data Sources

| Service | Finding Type |
|---------|-------------|
| AWS Config | Non-compliant config rules |
| Security Hub | Active findings (NEW workflow) |
| GuardDuty | Threat detections |
| IAM Access Analyzer | Public / cross-account resource access |
