"""
AWS API client for CSPM.

Uses boto3 with sync calls (matches BaseConnector contract).
Handles rate limits via boto3's built-in retry logic.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class AwsCspmApiClient:
    """
    Thin wrapper around boto3 for AWS Config, SecurityHub, GuardDuty, IAM, STS.
    Credentials are passed directly to each boto3.client call to avoid global state.
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str,
        session_token: Optional[str] = None,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session_token = session_token

    def _client(self, service: str) -> Any:
        kwargs: dict[str, Any] = {
            "service_name": service,
            "region_name": self.region,
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
        }
        if self.session_token:
            kwargs["aws_session_token"] = self.session_token
        return boto3.client(**kwargs)

    def validate_auth(self) -> bool:
        """Call sts:GetCallerIdentity to validate credentials."""
        try:
            client = self._client("sts")
            client.get_caller_identity()
            return True
        except (ClientError, NoCredentialsError) as exc:
            logger.warning("AWS auth validation failed: %s", exc)
            return False
        except Exception:
            logger.exception("AWS auth validation error")
            return False

    def list_config_rules(self) -> list[dict[str, Any]]:
        """Fetch all AWS Config rules with compliance state."""
        client = self._client("config")
        rules: list[dict[str, Any]] = []
        paginator = client.get_paginator("describe_config_rules")
        for page in paginator.paginate():
            rules.extend(page.get("ConfigRules", []))
        return rules

    def get_config_compliance(self, rule_names: list[str]) -> list[dict[str, Any]]:
        """Fetch compliance details for given config rule names."""
        if not rule_names:
            return []
        client = self._client("config")
        results: list[dict[str, Any]] = []
        paginator = client.get_paginator("describe_compliance_by_config_rule")
        for page in paginator.paginate(ConfigRuleNames=rule_names):
            results.extend(page.get("ComplianceByConfigRules", []))
        return results

    def list_security_hub_findings(self) -> list[dict[str, Any]]:
        """Fetch active Security Hub findings."""
        client = self._client("securityhub")
        findings: list[dict[str, Any]] = []
        paginator = client.get_paginator("get_findings")
        filters = {
            "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
            "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}],
        }
        for page in paginator.paginate(Filters=filters):
            findings.extend(page.get("Findings", []))
        return findings

    def list_guardduty_findings(self) -> list[dict[str, Any]]:
        """Fetch active GuardDuty findings."""
        client = self._client("guardduty")
        try:
            detectors = client.list_detectors().get("DetectorIds", [])
        except ClientError as exc:
            logger.warning("GuardDuty list_detectors failed: %s", exc)
            return []

        findings: list[dict[str, Any]] = []
        for detector_id in detectors:
            paginator = client.get_paginator("list_findings")
            for page in paginator.paginate(
                DetectorId=detector_id,
                FindingCriteria={
                    "Criterion": {
                        "service.archived": {"Eq": ["false"]}
                    }
                },
            ):
                finding_ids = page.get("FindingIds", [])
                if finding_ids:
                    detail_resp = client.get_findings(
                        DetectorId=detector_id, FindingIds=finding_ids
                    )
                    findings.extend(detail_resp.get("Findings", []))
        return findings

    def list_access_analyzer_findings(self) -> list[dict[str, Any]]:
        """Fetch active Access Analyzer findings."""
        client = self._client("accessanalyzer")
        findings: list[dict[str, Any]] = []
        try:
            analyzers = client.list_analyzers().get("analyzers", [])
        except ClientError as exc:
            logger.warning("AccessAnalyzer list_analyzers failed: %s", exc)
            return []

        for analyzer in analyzers:
            analyzer_arn = analyzer.get("arn")
            if not analyzer_arn:
                continue
            paginator = client.get_paginator("list_findings")
            for page in paginator.paginate(
                analyzerArn=analyzer_arn,
                status="ACTIVE",
            ):
                findings.extend(page.get("findings", []))
        return findings
