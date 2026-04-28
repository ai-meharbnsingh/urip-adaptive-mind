"""
Tenable.io Vulnerability Manager connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates Access Key + Secret Key via /scans
  fetch_findings → pulls per-asset vulnerabilities from workbenches
  normalize      → maps Tenable plugin output → URIPRiskRecord
  health_check   → returns operational status
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
from connectors.tenable.api_client import TenableAPIClient
from connectors.tenable.schemas import (
    TenableAsset,
    TenableAssetsResponse,
    TenableVulnerabilitiesResponse,
    TenableVulnerability,
)

logger = logging.getLogger(__name__)

# Tenable severity: 0=info, 1=low, 2=medium, 3=high, 4=critical
SEVERITY_MAP = {
    0: "low",
    1: "low",
    2: "medium",
    3: "high",
    4: "critical",
}


@register_connector("tenable")
class TenableConnector(BaseConnector):
    """
    Live connector for Tenable.io Vulnerability Management.

    Data flow
    ---------
    1. Authenticate with Access Key + Secret Key.
    2. Fetch asset inventory (/workbenches/assets).
    3. For each asset, fetch vulnerabilities (/workbenches/assets/{uuid}/vulnerabilities).
    4. Normalize each (asset, vulnerability) pair to URIPRiskRecord.
    """

    NAME = "tenable"
    RISK_INDEX_DOMAIN = "exposure"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Tenable Vulnerability Manager"
    CATEGORY = "VM"
    SHORT_DESCRIPTION = (
        "Pulls CVE inventory, CVSS, EPSS, exploit availability for every scanned asset."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developer.tenable.com/reference/navigate"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "VM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="API Endpoint", type="url",
            required=False, default="https://cloud.tenable.com",
            placeholder="https://cloud.tenable.com",
            help_text="Tenable.io cloud URL — keep default unless on a regional pod.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="access_key", label="Access Key", type="password",
            required=True, secret=True,
            placeholder="abcd1234efgh5678…",
            help_text="Settings → My Account → API Keys → Access Key.",
        ),
        CredentialFieldSpec(
            name="secret_key", label="Secret Key", type="password",
            required=True, secret=True,
            placeholder="wxyz9876mnop5432…",
            help_text="Settings → My Account → API Keys → Secret Key.",
        ),
        CredentialFieldSpec(
            name="max_requests_per_hour", label="Max requests / hour",
            type="number", required=False, default=1000,
            help_text="Tenable global rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["tenable"]

    def __init__(self) -> None:
        self._client: TenableAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Tenable.io API keys.

        Required credential keys:
            - access_key  (or tenable_access_key)
            - secret_key  (or tenable_secret_key)
        Optional:
            - base_url    (default https://cloud.tenable.com)
            - tenant_id
        """
        access_key = (
            tenant_credentials.get("access_key")
            or tenant_credentials.get("tenable_access_key")
        )
        secret_key = (
            tenant_credentials.get("secret_key")
            or tenant_credentials.get("tenable_secret_key")
        )

        if not access_key or not secret_key:
            raise ConnectorAuthError(
                "Tenable credentials must include 'access_key' and 'secret_key'"
            )

        base_url = tenant_credentials.get("base_url", "https://cloud.tenable.com")
        max_requests_per_hour = tenant_credentials.get(
            "max_requests_per_hour", 1000
        )
        self._client = TenableAPIClient(
            access_key=str(access_key),
            secret_key=str(secret_key),
            base_url=str(base_url),
            max_requests_per_hour=int(max_requests_per_hour),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "Tenable authentication failed: invalid API keys or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"tenable-ak-{str(access_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull vulnerabilities since `since`.

        Because Tenable workbenches expose per-asset vulnerabilities, we:
          1. List assets (respecting max_assets limit for rate-limit safety).
          2. For each asset, list its vulnerabilities.

        Parameters
        ----------
        since : datetime
            Only findings discovered/updated after this time are relevant.
            (Currently used as a filter hint; full incremental sync requires
            tracking last_seen per asset in production.)
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        max_assets : int, optional
            Cap the number of assets inspected per tick (default 50).
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        max_assets: int = kwargs.get("max_assets", 50)
        findings: list[RawFinding] = []

        try:
            # Step 1 — asset inventory
            assets_resp = self._client.list_assets(limit=max_assets, offset=0)
            assets_data = TenableAssetsResponse.model_validate(assets_resp)

            if not assets_data.assets:
                logger.info("Tenable: no assets returned for tenant %s", tenant_id)
                self._last_run = datetime.now(timezone.utc)
                return findings

            # Step 2 — per-asset vulnerabilities
            for asset in assets_data.assets:
                if not asset.uuid:
                    continue

                vulns_resp = self._client.list_asset_vulnerabilities(
                    asset_uuid=asset.uuid
                )
                vulns_data = TenableVulnerabilitiesResponse.model_validate(vulns_resp)

                for vuln in vulns_data.vulnerabilities:
                    # Attach asset context so normalize() can map hostname
                    vuln.asset = asset
                    raw_id = f"{asset.uuid}:{vuln.plugin_id}"
                    findings.append(
                        RawFinding(
                            id=raw_id,
                            source=self.NAME,
                            raw_data=vuln.model_dump(mode="json"),
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            logger.info(
                "Tenable: fetched %d findings from %d assets for tenant %s",
                len(findings),
                len(assets_data.assets),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Tenable fetch_findings failed")
            raise ConnectorFetchError(f"Tenable fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Tenable RawFinding to URIPRiskRecord.

        Mappings
        --------
        plugin_name      → finding
        severity (0-4)   → severity (low/medium/high/critical)
        cvss3_base_score → cvss_score (falls back to cvss_base_score)
        asset.hostname   → asset
        cve[0]           → cve_id
        plugin_id        → included in description
        """
        data = raw.raw_data
        vuln = TenableVulnerability.model_validate(data)

        severity = SEVERITY_MAP.get(vuln.severity, "medium")

        # Asset identifier priority: hostname → ipv4[0] → uuid → "unknown"
        asset_name = "unknown"
        if vuln.asset:
            asset_name = (
                vuln.asset.hostname
                or (vuln.asset.ipv4[0] if vuln.asset.ipv4 else None)
                or vuln.asset.uuid
                or "unknown"
            )

        cve_id = vuln.cve[0] if vuln.cve else None
        cvss = vuln.cvss3_base_score or vuln.cvss_base_score or 0.0

        description = (
            f"Tenable plugin {vuln.plugin_id}: {vuln.plugin_name}. "
            f"State: {vuln.vulnerability_state or 'unknown'}. "
            f"Affected asset: {asset_name}."
        )
        if vuln.synopsis:
            description += f" Synopsis: {vuln.synopsis}"

        return URIPRiskRecord(
            finding=vuln.plugin_name,
            description=description,
            source=self.NAME,
            domain="network",  # VM findings default to network; refine later if needed
            cvss_score=cvss,
            severity=severity,
            asset=asset_name,
            owner_team="Vulnerability Management",
            cve_id=cve_id,
            exploit_status=None,
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
