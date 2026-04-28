"""
GCP Cloud Security Posture Management connector for URIP.

Implements BaseConnector:
  authenticate   -> validates GCP credentials via OAuth2 JWT or ADC
  fetch_findings -> pulls SCC findings, Cloud Asset Inventory, Recommender
  normalize      -> maps GCP findings -> URIPRiskRecord
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
from connectors.gcp_cspm.api_client import GcpCspmApiClient
from connectors.gcp_cspm.schemas import (
    GcpAsset,
    GcpRecommenderRecommendation,
    GcpSccFinding,
)

logger = logging.getLogger(__name__)

SCC_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}

RECOMMENDER_PRIORITY_MAP = {
    "P1": "critical",
    "P2": "high",
    "P3": "medium",
    "P4": "low",
}


@register_connector("gcp_cspm")
class GcpCspmConnector(BaseConnector):
    """
    Live connector for GCP Cloud Security Posture Management.

    Data flow
    ---------
    1. Authenticate with service account JSON or ADC.
    2. Fetch SCC findings.
    3. Fetch Cloud Asset Inventory.
    4. Fetch Recommender recommendations.
    5. Normalize each result to URIPRiskRecord.
    """

    NAME = "gcp_cspm"
    RISK_INDEX_DOMAIN = "security_config"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "GCP Cloud Security Posture"
    CATEGORY = "CSPM"
    SHORT_DESCRIPTION = (
        "Pulls Security Command Center findings, Cloud Asset Inventory, and "
        "Recommender posture issues."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://cloud.google.com/security-command-center/docs"
    SUPPORTED_PRODUCTS = ["Security Command Center", "Cloud Asset Inventory", "Recommender"]
    MODULE_CODE = "CSPM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="project_id", label="GCP Project ID", type="text",
            required=True,
            placeholder="my-prod-project",
            help_text="GCP project to scan (used for ADC and SCC organization lookup).",
        ),
        CredentialFieldSpec(
            name="organization_id", label="Organization ID", type="text",
            required=False,
            placeholder="123456789012",
            help_text="GCP organization ID (required for org-level SCC).",
        ),
        CredentialFieldSpec(
            name="service_account_json", label="Service Account JSON", type="textarea",
            required=False, secret=True,
            help_text=(
                "Optional: paste the service account key JSON. Leave empty to "
                "use Application Default Credentials (ADC) on the host."
            ),
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["gcp_cspm"]

    def __init__(self) -> None:
        self._client: GcpCspmApiClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate GCP credentials.

        Required credential keys (one of):
            - service_account_json: dict with GCP service account key
            - project_id: for Application Default Credentials (ADC)
        Optional:
            - tenant_id
            - org_id (for org-level SCC when project_id is absent)
        """
        service_account_json = tenant_credentials.get("service_account_json")
        project_id = tenant_credentials.get("project_id")

        if service_account_json and not project_id:
            project_id = service_account_json.get("project_id")

        if not service_account_json and not project_id:
            raise ConnectorAuthError(
                "GCP CSPM credentials must include 'service_account_json' or 'project_id' for ADC"
            )

        self._client = GcpCspmApiClient(
            service_account_json=service_account_json,
            project_id=project_id,
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "GCP authentication failed: invalid credentials or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token="gcp-token-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull findings from GCP SCC, Asset Inventory, and Recommender.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this time.
            (Currently used as a filter hint; full incremental sync requires
            tracking last_seen in production.)
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        org_id : str, optional
            GCP organization identifier for org-level SCC sources.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        project_id = self._client.project_id
        findings: list[RawFinding] = []

        try:
            # --- SCC findings ---
            if project_id:
                parent = f"projects/{project_id}/sources/-"
            else:
                org_id = kwargs.get("org_id")
                if org_id:
                    parent = f"organizations/{org_id}/sources/-"
                else:
                    parent = ""

            if parent:
                scc_findings = self._client.list_scc_findings(parent)
                for f in scc_findings:
                    finding_name = f.get("name", "unknown")
                    findings.append(
                        RawFinding(
                            id=f"scc:{finding_name}",
                            source=self.NAME,
                            raw_data={"type": "scc", "data": f},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                logger.info(
                    "GCP CSPM: fetched %d SCC findings for %s",
                    len(scc_findings),
                    parent,
                )

            # --- Cloud Asset Inventory ---
            if project_id:
                assets = self._client.list_assets(project_id)
                for a in assets:
                    asset_name = a.get("name", "unknown")
                    findings.append(
                        RawFinding(
                            id=f"asset:{asset_name}",
                            source=self.NAME,
                            raw_data={"type": "asset", "data": a},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                logger.info(
                    "GCP CSPM: fetched %d assets for project %s",
                    len(assets),
                    project_id,
                )

            # --- Recommender recommendations ---
            if project_id:
                recommendations = self._client.list_recommender_recommendations(
                    project_id
                )
                for r in recommendations:
                    rec_name = r.get("name", "unknown")
                    findings.append(
                        RawFinding(
                            id=f"recommender:{rec_name}",
                            source=self.NAME,
                            raw_data={"type": "recommender", "data": r},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                logger.info(
                    "GCP CSPM: fetched %d recommendations for project %s",
                    len(recommendations),
                    project_id,
                )

            logger.info(
                "GCP CSPM: fetched %d total findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("GCP CSPM fetch_findings failed")
            raise ConnectorFetchError(f"GCP CSPM fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a GCP RawFinding to URIPRiskRecord.

        Dispatches by finding type (scc, asset, recommender).
        """
        data = raw.raw_data
        finding_type = data.get("type", "unknown")
        payload = data.get("data", {})

        if finding_type == "scc":
            return self._normalize_scc(payload)
        if finding_type == "asset":
            return self._normalize_asset(payload)
        if finding_type == "recommender":
            return self._normalize_recommender(payload)

        return URIPRiskRecord(
            finding="Unknown GCP finding",
            source=self.NAME,
            domain="cloud",
            cvss_score=0.0,
            severity="medium",
            asset="gcp",
            owner_team="Cloud Security",
        )

    def _normalize_scc(self, data: dict[str, Any]) -> URIPRiskRecord:
        finding = GcpSccFinding.model_validate(data)
        severity = SCC_SEVERITY_MAP.get(
            (finding.severity or "").upper(), "medium"
        )
        asset = finding.resourceName or "gcp"
        return URIPRiskRecord(
            finding=finding.category or "SCC Finding",
            description=finding.description or "No description",
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

    def _normalize_asset(self, data: dict[str, Any]) -> URIPRiskRecord:
        asset = GcpAsset.model_validate(data)
        asset_name = asset.name
        asset_type = asset.assetType or "unknown"
        # Heuristic: presence of an IAM policy suggests a reviewable misconfiguration
        has_misconfig = asset.iamPolicy is not None
        severity = "medium" if has_misconfig else "low"
        description = f"GCP asset {asset_name} of type {asset_type}."
        if has_misconfig:
            description += " IAM policy attached; review permissions."
        return URIPRiskRecord(
            finding=f"Asset: {asset_type}",
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score=5.0 if has_misconfig else 0.0,
            severity=severity,
            asset=asset_name,
            owner_team="Cloud Security",
        )

    def _normalize_recommender(self, data: dict[str, Any]) -> URIPRiskRecord:
        rec = GcpRecommenderRecommendation.model_validate(data)
        severity = RECOMMENDER_PRIORITY_MAP.get(
            (rec.priority or "").upper(), "medium"
        )
        asset = "gcp"
        if rec.content:
            overview = rec.content.get("overview", {})
            if isinstance(overview, dict):
                resource = overview.get("resourceName") or overview.get("resource")
                if resource:
                    asset = str(resource)
        return URIPRiskRecord(
            finding=rec.recommenderSubtype or "Recommender Finding",
            description=rec.description or "No description",
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
