"""
ManageEngine MDM connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API token
  fetch_findings → pulls jailbroken devices, non-compliant mobile, lost/stolen events
  normalize      → maps MDM findings → URIPRiskRecord
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
from connectors.manageengine_mdm.api_client import ManageEngineMDMAPIClient
from connectors.manageengine_mdm.schemas import (
    MEMDevice,
    MEMListResponse,
    MEMLostStolenEvent,
)

logger = logging.getLogger(__name__)


@register_connector("manageengine_mdm")
class ManageEngineMDMConnector(BaseConnector):
    """
    Live connector for ManageEngine MDM (Mobile Device Management).

    Data flow
    ---------
    1. Authenticate with base_url + api_token.
    2. Fetch devices (/api/v1/mdm/devices).
    3. Fetch lost/stolen events (/api/v1/mdm/lost_stolen).
    4. Normalize each to URIPRiskRecord.
    """

    NAME = "manageengine_mdm"
    RISK_INDEX_DOMAIN = "security_config"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ManageEngine MDM"
    CATEGORY = "EDR"
    SHORT_DESCRIPTION = (
        "Jailbroken devices, non-compliant mobile assets, and lost/stolen device events from ManageEngine MDM."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://www.manageengine.com/mobile-device-management/help/api/"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "EDR"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="API Endpoint", type="url",
            required=True,
            placeholder="https://mdm.example.com",
            help_text="ManageEngine MDM server URL.",
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
            help_text="MDM API rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["manageengine_mdm"]

    def __init__(self) -> None:
        self._client: ManageEngineMDMAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate ManageEngine MDM credentials.

        Required credential keys:
            - base_url
            - api_token
        """
        base_url = tenant_credentials.get("base_url")
        api_token = tenant_credentials.get("api_token")

        if not base_url:
            raise ConnectorAuthError("ManageEngine MDM credentials must include 'base_url'")
        if not api_token:
            raise ConnectorAuthError("ManageEngine MDM credentials must include 'api_token'")

        max_requests_per_hour = tenant_credentials.get("max_requests_per_hour", 2000)
        self._client = ManageEngineMDMAPIClient(
            base_url=str(base_url),
            api_token=str(api_token),
            max_requests_per_hour=int(max_requests_per_hour),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "ManageEngine MDM authentication failed: invalid API token or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"memdm-{str(api_token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull mobile device findings.

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
            # ── Devices ─────────────────────────────────────────────────
            devices_resp = self._client.list_devices(limit=100, offset=0)
            devices_data = MEMListResponse.model_validate(devices_resp)
            for item in devices_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "device"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Lost/stolen events ──────────────────────────────────────
            events_resp = self._client.list_lost_stolen_events(limit=100, offset=0)
            events_data = MEMListResponse.model_validate(events_resp)
            for item in events_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "lost_stolen"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "ManageEngine MDM: fetched %d findings for tenant %s",
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
            logger.exception("ManageEngine MDM fetch_findings failed")
            raise ConnectorFetchError(f"ManageEngine MDM fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a ManageEngine MDM RawFinding to URIPRiskRecord.

        Handles two categories:
          1. device       → mobile domain, mobile security owner
          2. lost_stolen  → mobile domain, mobile security owner
        """
        data = raw.raw_data
        category = data.get("category", "device")

        if category == "device":
            device = MEMDevice.model_validate(data)
            if device.is_jailbroken:
                severity = "critical"
                finding = f"Jailbroken Device: {device.device_name or 'Unknown'}"
            elif (device.compliance_status or "").lower() == "non_compliant":
                severity = "high"
                finding = f"Non-Compliant Mobile Device: {device.device_name or 'Unknown'}"
            else:
                severity = "low"
                finding = f"Mobile Device: {device.device_name or 'Unknown'}"
            description = (
                f"Mobile device '{device.device_name or 'Unknown'}' ({device.platform or 'unknown'} "
                f"{device.os_version or ''}) — jailbroken: {device.is_jailbroken}, "
                f"compliance: {device.compliance_status or 'unknown'}."
            )
            asset = device.device_name or device.user_name or device.id or "unknown"

        elif category == "lost_stolen":
            event = MEMLostStolenEvent.model_validate(data)
            event_type = (event.event_type or "").lower()
            if event_type == "stolen":
                severity = "critical"
                finding = f"Stolen Device: {event.device_name or 'Unknown'}"
            elif event_type == "lost":
                severity = "high"
                finding = f"Lost Device: {event.device_name or 'Unknown'}"
            else:
                severity = "medium"
                finding = f"Device Event: {event.device_name or 'Unknown'}"
            description = (
                f"Device '{event.device_name or 'Unknown'}' reported as {event.event_type or 'unknown'} "
                f"by {event.reported_by or 'unknown'} at {event.reported_at or 'N/A'}."
            )
            asset = event.device_name or event.device_id or "unknown"

        else:
            finding = "ManageEngine MDM Finding"
            description = "Unknown ManageEngine MDM finding category."
            severity = "medium"
            asset = "unknown"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="mobile",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Mobile Security",
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
