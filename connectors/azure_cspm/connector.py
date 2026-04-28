"""
Azure Cloud Security Posture Management connector for URIP.

Implements BaseConnector:
  authenticate   -> validates Azure AD service principal credentials
  fetch_findings -> pulls Azure Policy, Defender recommendations, Defender alerts
  normalize      -> maps Azure findings -> URIPRiskRecord
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
from connectors.azure_cspm.api_client import AzureCspmApiClient
from connectors.azure_cspm.schemas import (
    AzureDefenderAlert,
    AzureDefenderRecommendation,
    AzurePolicyCompliance,
)

logger = logging.getLogger(__name__)

# Keywords that indicate a business-critical Azure resource type
_CRITICAL_RESOURCE_KEYWORDS = (
    "storage",
    "sql",
    "keyvault",
    "kubernetes",
    "container",
    "vm",
    "virtualmachine",
    "database",
    "cosmos",
    "redis",
    "app",
    "function",
    "logic",
)


def _is_critical_resource(resource_type: str | None) -> bool:
    if not resource_type:
        return False
    return any(k in resource_type.lower() for k in _CRITICAL_RESOURCE_KEYWORDS)


def _map_defender_alert_severity(severity: str | None) -> str:
    if not severity:
        return "medium"
    mapping = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "informational": "low",
    }
    return mapping.get(severity.lower(), "medium")


def _map_defender_rec_severity(status_code: str | None) -> str:
    if status_code and status_code.lower() == "unhealthy":
        return "high"
    return "medium"


@register_connector("azure_cspm")
class AzureCspmConnector(BaseConnector):
    """
    Live connector for Azure Cloud Security Posture Management.

    Data flow
    ---------
    1. Authenticate with Azure AD (client_credentials).
    2. Fetch non-compliant Azure Policy states.
    3. Fetch Defender for Cloud recommendations.
    4. Fetch Defender for Cloud alerts.
    5. Normalize each finding to URIPRiskRecord.
    """

    NAME = "azure_cspm"
    RISK_INDEX_DOMAIN = "security_config"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Azure Cloud Security Posture"
    CATEGORY = "CSPM"
    SHORT_DESCRIPTION = (
        "Pulls Azure Policy non-compliance, Defender for Cloud recommendations, "
        "and Defender alerts into URIP."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://learn.microsoft.com/en-us/azure/defender-for-cloud/"
    SUPPORTED_PRODUCTS = ["Azure Policy", "Defender for Cloud"]
    MODULE_CODE = "CSPM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="tenant_id_azure", label="Azure Tenant ID", type="text",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="Azure AD tenant (directory) ID.",
        ),
        CredentialFieldSpec(
            name="subscription_id", label="Subscription ID", type="text",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="Azure subscription ID containing the resources to assess.",
        ),
        CredentialFieldSpec(
            name="client_id", label="Client ID", type="text",
            required=True,
            help_text="Service principal application (client) ID with Reader + Security Reader roles.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="Client Secret", type="password",
            required=True, secret=True,
            help_text="Service principal client secret.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["azure_cspm"]

    def __init__(self) -> None:
        self._client: AzureCspmApiClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Azure AD service principal credentials.

        Required credential keys:
            - tenant_id
            - client_id
            - client_secret
        Optional:
            - base_url (default https://management.azure.com)
        """
        tenant_id = tenant_credentials.get("tenant_id")
        client_id = tenant_credentials.get("client_id")
        client_secret = tenant_credentials.get("client_secret")

        if not tenant_id or not client_id or not client_secret:
            raise ConnectorAuthError(
                "Azure CSPM credentials must include 'tenant_id', 'client_id', and 'client_secret'"
            )

        base_url = tenant_credentials.get("base_url", "https://management.azure.com")

        self._client = AzureCspmApiClient(
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            client_secret=str(client_secret),
            base_url=str(base_url),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "Azure authentication failed: invalid credentials or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"azure-{str(client_id)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull findings from Azure Policy, Defender recommendations, and Defender alerts.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this timestamp.
            Used as a filter hint; full incremental sync would require
            timestamp filtering per API.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            # 1. Azure Policy non-compliance
            policy_items = self._client.list_policy_compliance()
            for item in policy_items:
                name = (
                    item.get("policyDefinitionName")
                    or item.get("policyAssignmentName")
                    or item.get("policyDefinitionId", "unknown")
                )
                findings.append(
                    RawFinding(
                        id=f"policy:{name}",
                        source=self.NAME,
                        raw_data={"type": "policy", "data": item},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # 2. Defender recommendations
            rec_items = self._client.list_defender_recommendations()
            for item in rec_items:
                rec_id = item.get("name") or item.get("id", "unknown")
                findings.append(
                    RawFinding(
                        id=f"defender-rec:{rec_id}",
                        source=self.NAME,
                        raw_data={"type": "defender-rec", "data": item},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # 3. Defender alerts
            alert_items = self._client.list_defender_alerts()
            for item in alert_items:
                alert_id = item.get("name") or item.get("id", "unknown")
                findings.append(
                    RawFinding(
                        id=f"defender-alert:{alert_id}",
                        source=self.NAME,
                        raw_data={"type": "defender-alert", "data": item},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Azure CSPM: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Azure CSPM fetch_findings failed")
            raise ConnectorFetchError(f"Azure CSPM fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map an Azure CSPM RawFinding to URIPRiskRecord.

        Dispatches by finding type stored in raw_data.
        """
        data = raw.raw_data
        finding_type = data.get("type", "unknown")
        payload = data.get("data", {})

        if finding_type == "policy":
            return self._normalize_policy(payload)
        if finding_type == "defender-rec":
            return self._normalize_defender_rec(payload)
        if finding_type == "defender-alert":
            return self._normalize_defender_alert(payload)

        return URIPRiskRecord(
            finding="Unknown Azure finding",
            source=self.NAME,
            domain="cloud",
            cvss_score=0.0,
            severity="medium",
            asset="azure",
            owner_team="Cloud Security",
        )

    def _normalize_policy(self, data: dict[str, Any]) -> URIPRiskRecord:
        item = AzurePolicyCompliance.model_validate(data)
        is_critical = _is_critical_resource(item.resourceType)
        severity = "high" if is_critical else "medium"
        asset = item.resourceId or item.resourceGroup or "azure"
        description = (
            f"Azure Policy '{item.policyDefinitionName or item.policyAssignmentName or 'unknown'}' "
            f"is {item.complianceState or 'NonCompliant'} on resource {asset}."
        )
        return URIPRiskRecord(
            finding=f"Policy: {item.policyDefinitionName or item.policyAssignmentName or 'unknown'}",
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score=7.5 if severity == "high" else 5.0,
            severity=severity,
            asset=asset,
            owner_team="Cloud Security",
        )

    def _normalize_defender_rec(self, data: dict[str, Any]) -> URIPRiskRecord:
        rec = AzureDefenderRecommendation.model_validate(data)
        props = rec.properties or {}
        status = props.get("status", {})
        status_code = status.get("code") if isinstance(status, dict) else None
        display_name = props.get("displayName") or rec.name
        severity = _map_defender_rec_severity(status_code)
        resource_details = props.get("resourceDetails", {})
        asset = resource_details.get("id") or rec.id or "azure"
        description = (
            f"Defender recommendation '{display_name or 'unknown'}' is {status_code or 'unknown'}. "
            f"Resource: {asset}."
        )
        return URIPRiskRecord(
            finding=f"Defender Rec: {display_name or rec.name or 'unknown'}",
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score=7.5 if severity == "high" else 5.0,
            severity=severity,
            asset=asset,
            owner_team="Cloud Security",
        )

    def _normalize_defender_alert(self, data: dict[str, Any]) -> URIPRiskRecord:
        alert = AzureDefenderAlert.model_validate(data)
        props = alert.properties or {}
        severity = _map_defender_alert_severity(props.get("severity"))
        asset = (
            props.get("compromisedEntity")
            or props.get("alertDisplayName")
            or alert.id
            or "azure"
        )
        description = (
            props.get("description")
            or f"Defender alert '{props.get('alertDisplayName') or alert.name or 'unknown'}'."
        )
        return URIPRiskRecord(
            finding=props.get("alertDisplayName") or alert.name or "Defender Alert",
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score={
                "critical": 9.0,
                "high": 7.5,
                "medium": 5.0,
                "low": 2.0,
            }.get(severity, 5.0),
            severity=severity,
            asset=asset,
            owner_team="Cloud Security",
        )

    def health_check(self) -> ConnectorHealth:
        """Return connector operational status."""
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
