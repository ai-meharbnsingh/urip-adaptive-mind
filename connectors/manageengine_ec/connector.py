"""
ManageEngine Endpoint Central connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API token
  fetch_findings → pulls patch status, missing critical patches, compliance score
  normalize      → maps Endpoint Central findings → URIPRiskRecord
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
from connectors.manageengine_ec.api_client import ManageEngineECAPIClient
from connectors.manageengine_ec.schemas import (
    MECComputer,
    MECComplianceRecord,
    MECListResponse,
    MECMissingPatch,
)

logger = logging.getLogger(__name__)

PATCH_SEVERITY_MAP = {
    "critical": "critical",
    "important": "high",
    "moderate": "medium",
    "low": "low",
}


def _map_patch_severity(raw: str | None) -> str:
    return PATCH_SEVERITY_MAP.get((raw or "").lower(), "medium")


@register_connector("manageengine_ec")
class ManageEngineECConnector(BaseConnector):
    """
    Live connector for ManageEngine Endpoint Central (UEM).

    Data flow
    ---------
    1. Authenticate with base_url + api_token.
    2. Fetch computers (/api/v1/sdp/Computers).
    3. Fetch missing patches (/api/v1/patch/missing_patches).
    4. Normalize each to URIPRiskRecord.
    """

    NAME = "manageengine_ec"
    RISK_INDEX_DOMAIN = "security_config"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ManageEngine Endpoint Central"
    CATEGORY = "EDR"
    SHORT_DESCRIPTION = (
        "Patch status per endpoint, missing critical patches, and compliance score from ManageEngine Endpoint Central."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://www.manageengine.com/products/desktop-central/api/"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "EDR"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="API Endpoint", type="url",
            required=True,
            placeholder="https://endpointcentral.example.com",
            help_text="ManageEngine Endpoint Central server URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_token", label="API Token", type="password",
            required=True, secret=True,
            placeholder="abc123…",
            help_text="Generate under Admin → API → API Token.",
        ),
        CredentialFieldSpec(
            name="max_requests_per_hour", label="Max requests / hour",
            type="number", required=False, default=2000,
            help_text="Endpoint Central API rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["manageengine_ec"]

    def __init__(self) -> None:
        self._client: ManageEngineECAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate ManageEngine Endpoint Central credentials.

        Required credential keys:
            - base_url
            - api_token
        """
        base_url = tenant_credentials.get("base_url")
        api_token = tenant_credentials.get("api_token")

        if not base_url:
            raise ConnectorAuthError("ManageEngine EC credentials must include 'base_url'")
        if not api_token:
            raise ConnectorAuthError("ManageEngine EC credentials must include 'api_token'")

        max_requests_per_hour = tenant_credentials.get("max_requests_per_hour", 2000)
        self._client = ManageEngineECAPIClient(
            base_url=str(base_url),
            api_token=str(api_token),
            max_requests_per_hour=int(max_requests_per_hour),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "ManageEngine EC authentication failed: invalid API token or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"meec-{str(api_token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull patch and compliance findings.

        Parameters
        ----------
        since : datetime
            Fetch only findings created/updated after this time.
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
            # ── Computers ───────────────────────────────────────────────
            computers_resp = self._client.list_computers(limit=100, offset=0)
            computers_data = MECListResponse.model_validate(computers_resp)
            for item in computers_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "computer"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Missing patches ─────────────────────────────────────────
            patches_resp = self._client.list_missing_patches(limit=100, offset=0)
            patches_data = MECListResponse.model_validate(patches_resp)
            for item in patches_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "missing_patch"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "ManageEngine EC: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    body = exc.response.json()
                    if isinstance(body, dict) and "error" in body:
                        msg = f"{msg} — {body['error']}"
                except Exception:
                    pass
            self._last_error = msg
            logger.exception("ManageEngine EC fetch_findings failed")
            raise ConnectorFetchError(f"ManageEngine EC fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a ManageEngine EC RawFinding to URIPRiskRecord.

        Handles two categories:
          1. computer      → endpoint domain, endpoint owner
          2. missing_patch → endpoint domain, endpoint owner
        """
        data = raw.raw_data
        category = data.get("category", "computer")

        if category == "computer":
            computer = MECComputer.model_validate(data)
            patch_status = (computer.patch_status or "").lower()
            if patch_status == "non_compliant":
                severity = "high"
                finding = f"Non-Compliant Endpoint: {computer.name or 'Unknown'}"
            elif patch_status == "unknown":
                severity = "medium"
                finding = f"Unknown Patch Status: {computer.name or 'Unknown'}"
            else:
                severity = "low"
                finding = f"Endpoint Patch Status: {computer.name or 'Unknown'}"
            description = (
                f"Endpoint '{computer.name or 'Unknown'}' ({computer.os or 'unknown OS'}) "
                f"has patch status '{computer.patch_status or 'unknown'}'. "
                f"Compliance score: {computer.compliance_score or 'N/A'}."
            )
            asset = computer.name or computer.ip_address or computer.id or "unknown"

        elif category == "missing_patch":
            patch = MECMissingPatch.model_validate(data)
            severity = _map_patch_severity(patch.severity)
            finding = f"Missing Patch: {patch.patch_name or patch.patch_id or 'Unknown'}"
            description = (
                f"Critical patch '{patch.patch_name or patch.patch_id or 'Unknown'}' is missing "
                f"on endpoint '{patch.computer_name or patch.computer_id or 'Unknown'}'. "
                f"Severity: {patch.severity or 'unknown'}."
            )
            asset = patch.computer_name or patch.computer_id or "unknown"

        else:
            finding = "ManageEngine EC Finding"
            description = "Unknown ManageEngine EC finding category."
            severity = "medium"
            asset = "unknown"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="endpoint",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Endpoint Security",
            cve_id=None,
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
