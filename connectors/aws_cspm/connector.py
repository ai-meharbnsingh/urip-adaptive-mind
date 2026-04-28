"""
AWS Cloud Security Posture connector for URIP.

Implements BaseConnector:
  authenticate   -> validates AWS credentials via STS GetCallerIdentity
  fetch_findings -> pulls Config rules, SecurityHub, GuardDuty, AccessAnalyzer
  normalize      -> maps AWS findings -> URIPRiskRecord
  health_check   -> returns operational status
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from connectors.base.connector import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorHealth,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.aws_cspm.api_client import AwsCspmApiClient
from connectors.aws_cspm.schemas import (
    AwsConfigRuleCompliance,
    AwsSecurityHubFinding,
    AwsGuardDutyFinding,
    AwsAccessAnalyzerFinding,
)

logger = logging.getLogger(__name__)

AWS_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFORMATIONAL": "low",
}


def _guardduty_severity(level: float) -> str:
    if level >= 7:
        return "high"
    if level >= 4:
        return "medium"
    return "low"


def _config_severity(rule_name: str) -> str:
    critical_keywords = ["root", "mfa", "public", "encryption", "password"]
    if any(k in rule_name.lower() for k in critical_keywords):
        return "high"
    return "medium"


@register_connector("aws_cspm")
class AwsCspmConnector(BaseConnector):
    NAME = "aws_cspm"
    RISK_INDEX_DOMAIN = "security_config"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "AWS Cloud Security Posture"
    CATEGORY = "CSPM"
    SHORT_DESCRIPTION = (
        "Pulls AWS Config, Security Hub, GuardDuty and Access Analyzer findings "
        "and maps them to URIP risks."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.aws.amazon.com/securityhub/latest/userguide/"
    SUPPORTED_PRODUCTS = ["Config", "Security Hub", "GuardDuty", "Access Analyzer"]
    MODULE_CODE = "CSPM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="access_key", label="AWS Access Key ID", type="password",
            required=True, secret=True,
            placeholder="AKIA…",
            help_text="IAM user / role access key with read-only security audit policy.",
        ),
        CredentialFieldSpec(
            name="secret_key", label="AWS Secret Access Key", type="password",
            required=True, secret=True,
            help_text="Paired secret key.",
        ),
        CredentialFieldSpec(
            name="region", label="Region", type="text",
            required=False, default="us-east-1",
            placeholder="us-east-1",
            help_text="Primary AWS region for Security Hub and GuardDuty queries.",
        ),
        CredentialFieldSpec(
            name="session_token", label="Session Token", type="password",
            required=False, secret=True,
            help_text="Optional: STS session token for temporary credentials.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["aws_cspm"]

    def __init__(self) -> None:
        self._client: AwsCspmApiClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        access_key = tenant_credentials.get("access_key") or tenant_credentials.get("aws_access_key_id")
        secret_key = tenant_credentials.get("secret_key") or tenant_credentials.get("aws_secret_access_key")
        region = tenant_credentials.get("region", "us-east-1")
        session_token = tenant_credentials.get("session_token")

        if not access_key or not secret_key:
            raise ConnectorAuthError(
                "AWS CSPM credentials must include 'access_key' and 'secret_key'"
            )

        self._client = AwsCspmApiClient(
            access_key=str(access_key),
            secret_key=str(secret_key),
            region=str(region),
            session_token=session_token,
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "AWS authentication failed: invalid credentials or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"aws-{str(access_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError("Connector not authenticated. Call authenticate() first.")

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            config_rules = self._client.list_config_rules()
            rule_names = [r["ConfigRuleName"] for r in config_rules if "ConfigRuleName" in r]
            compliance = self._client.get_config_compliance(rule_names)
            for item in compliance:
                findings.append(
                    RawFinding(
                        id=f"config:{item.get('ConfigRuleName', 'unknown')}",
                        source=self.NAME,
                        raw_data={"type": "config", "data": item},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            sh_findings = self._client.list_security_hub_findings()
            for f in sh_findings:
                findings.append(
                    RawFinding(
                        id=f"securityhub:{f.get('Id', 'unknown')}",
                        source=self.NAME,
                        raw_data={"type": "securityhub", "data": f},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            gd_findings = self._client.list_guardduty_findings()
            for f in gd_findings:
                findings.append(
                    RawFinding(
                        id=f"guardduty:{f.get('Id', 'unknown')}",
                        source=self.NAME,
                        raw_data={"type": "guardduty", "data": f},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            aa_findings = self._client.list_access_analyzer_findings()
            for f in aa_findings:
                findings.append(
                    RawFinding(
                        id=f"accessanalyzer:{f.get('id', 'unknown')}",
                        source=self.NAME,
                        raw_data={"type": "accessanalyzer", "data": f},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "AWS CSPM: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("AWS CSPM fetch_findings failed")
            raise ConnectorFetchError(f"AWS CSPM fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        data = raw.raw_data
        finding_type = data.get("type", "unknown")
        payload = data.get("data", {})

        if finding_type == "config":
            return self._normalize_config(payload)
        if finding_type == "securityhub":
            return self._normalize_securityhub(payload)
        if finding_type == "guardduty":
            return self._normalize_guardduty(payload)
        if finding_type == "accessanalyzer":
            return self._normalize_accessanalyzer(payload)

        return URIPRiskRecord(
            finding="Unknown AWS finding",
            source=self.NAME,
            domain="cloud",
            cvss_score=0.0,
            severity="medium",
            asset="aws",
            owner_team="Cloud Security",
        )

    def _normalize_config(self, data: dict[str, Any]) -> URIPRiskRecord:
        item = AwsConfigRuleCompliance.model_validate(data)
        is_noncompliant = item.ComplianceType == "NON_COMPLIANT"
        severity = _config_severity(item.ConfigRuleName)
        if is_noncompliant and severity == "medium":
            severity = "high"
        description = (
            f"AWS Config rule '{item.ConfigRuleName}' is {item.ComplianceType}. "
            f"Rule ARN: {item.ConfigRuleArn or 'N/A'}."
        )
        return URIPRiskRecord(
            finding=f"Config: {item.ConfigRuleName}",
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score=7.0 if is_noncompliant else 0.0,
            severity=severity if is_noncompliant else "low",
            asset=item.ConfigRuleArn or "aws",
            owner_team="Cloud Security",
        )

    def _normalize_securityhub(self, data: dict[str, Any]) -> URIPRiskRecord:
        finding = AwsSecurityHubFinding.model_validate(data)
        severity_label = finding.Severity.get("Label", "MEDIUM") if isinstance(finding.Severity, dict) else "MEDIUM"
        severity = AWS_SEVERITY_MAP.get(severity_label.upper(), "medium")
        resource = finding.Resources[0] if finding.Resources else {}
        asset = resource.get("Id", "aws")
        return URIPRiskRecord(
            finding=finding.Title or "SecurityHub Finding",
            description=finding.Description or "No description",
            source=self.NAME,
            domain="cloud",
            cvss_score={"critical": 9.0, "high": 7.5, "medium": 5.0, "low": 2.0}.get(severity, 5.0),
            severity=severity,
            asset=asset,
            owner_team="Cloud Security",
        )

    def _normalize_guardduty(self, data: dict[str, Any]) -> URIPRiskRecord:
        finding = AwsGuardDutyFinding.model_validate(data)
        severity = _guardduty_severity(finding.Severity)
        resource = finding.Resource
        asset = "aws"
        if "ResourceType" in resource:
            asset = resource["ResourceType"]
        return URIPRiskRecord(
            finding=finding.Title or "GuardDuty Finding",
            description=finding.Description or "No description",
            source=self.NAME,
            domain="cloud",
            cvss_score=finding.Severity,
            severity=severity,
            asset=asset,
            owner_team="Cloud Security",
        )

    def _normalize_accessanalyzer(self, data: dict[str, Any]) -> URIPRiskRecord:
        finding = AwsAccessAnalyzerFinding.model_validate(data)
        severity = "high" if finding.isPublic else "medium"
        return URIPRiskRecord(
            finding=f"Access Analyzer: public access to {finding.resourceType}",
            description=(
                f"Resource {finding.resource} is publicly accessible. "
                f"Principal: {finding.principal}. Action: {finding.action}."
            ),
            source=self.NAME,
            domain="cloud",
            cvss_score=8.0 if finding.isPublic else 5.0,
            severity=severity,
            asset=finding.resource or "aws",
            owner_team="Cloud Security",
        )

    def health_check(self) -> ConnectorHealth:
        status = "ok"
        if self._error_count > 0:
            status = "degraded" if self._error_count < 5 else "error"
        return ConnectorHealth(
            connector_name=self.NAME,
            status=status,
            last_run=self._last_run,
            error_count=self._error_count,
            last_error=self._last_error,
        )
