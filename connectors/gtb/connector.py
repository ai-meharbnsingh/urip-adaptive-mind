"""
GTB Endpoint Protector connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API key
  fetch_findings → pulls DLP policy violations, USB block events, exfil attempts
  normalize      → maps GTB findings → URIPRiskRecord
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
from connectors.gtb.api_client import GTBAPIClient
from connectors.gtb.schemas import (
    GTBExfilEvent,
    GTBListResponse,
    GTBUSBEvent,
    GTBViolation,
)

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _map_severity(raw: str | None) -> str:
    return SEVERITY_MAP.get((raw or "").lower(), "medium")


@register_connector("gtb")
class GTBConnector(BaseConnector):
    """
    Live connector for GTB Endpoint Protector (DLP).

    Data flow
    ---------
    1. Authenticate with base_url + api_key.
    2. Fetch DLP violations (/api/v1/violations).
    3. Fetch USB block events (/api/v1/events/usb).
    4. Fetch exfiltration attempts (/api/v1/events/exfil).
    5. Normalize each to URIPRiskRecord.
    """

    NAME = "gtb"
    RISK_INDEX_DOMAIN = "attack"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "GTB Endpoint Protector"
    CATEGORY = "DLP"
    SHORT_DESCRIPTION = (
        "DLP policy violations, USB block events, and data exfiltration attempts from GTB Endpoint Protector."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://www.gtbtechnologies.com/support/api-documentation"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "DLP"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="API Endpoint", type="url",
            required=True,
            placeholder="https://gtb.example.com",
            help_text="GTB Endpoint Protector server URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_key", label="API Key", type="password",
            required=True, secret=True,
            placeholder="gtb-key-abc123…",
            help_text="GTB API key from Admin → API Integration.",
        ),
        CredentialFieldSpec(
            name="max_requests_per_hour", label="Max requests / hour",
            type="number", required=False, default=3000,
            help_text="GTB API rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["gtb"]

    def __init__(self) -> None:
        self._client: GTBAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate GTB Endpoint Protector credentials.

        Required credential keys:
            - base_url
            - api_key
        """
        base_url = tenant_credentials.get("base_url")
        api_key = tenant_credentials.get("api_key")

        if not base_url:
            raise ConnectorAuthError("GTB credentials must include 'base_url'")
        if not api_key:
            raise ConnectorAuthError("GTB credentials must include 'api_key'")

        max_requests_per_hour = tenant_credentials.get("max_requests_per_hour", 3000)
        self._client = GTBAPIClient(
            base_url=str(base_url),
            api_key=str(api_key),
            max_requests_per_hour=int(max_requests_per_hour),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "GTB authentication failed: invalid API key or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"gtb-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull DLP violations, USB events, and exfiltration attempts.

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
            # ── DLP violations ──────────────────────────────────────────
            violations_resp = self._client.list_violations(limit=100, offset=0)
            violations_data = GTBListResponse.model_validate(violations_resp)
            for item in violations_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "violation"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── USB block events ────────────────────────────────────────
            usb_resp = self._client.list_usb_events(limit=100, offset=0)
            usb_data = GTBListResponse.model_validate(usb_resp)
            for item in usb_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "usb_block"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Exfiltration attempts ───────────────────────────────────
            exfil_resp = self._client.list_exfil_events(limit=100, offset=0)
            exfil_data = GTBListResponse.model_validate(exfil_resp)
            for item in exfil_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "exfil"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "GTB: fetched %d findings for tenant %s",
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
            logger.exception("GTB fetch_findings failed")
            raise ConnectorFetchError(f"GTB fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a GTB RawFinding to URIPRiskRecord.

        Handles three categories:
          1. violation  → dlp domain, data protection owner
          2. usb_block  → dlp domain, data protection owner
          3. exfil      → dlp domain, data protection owner
        """
        data = raw.raw_data
        category = data.get("category", "violation")

        if category == "violation":
            violation = GTBViolation.model_validate(data)
            severity = _map_severity(violation.severity)
            finding = f"DLP Violation: {violation.policy_name or 'Unknown Policy'}"
            description = (
                f"DLP policy '{violation.policy_name or 'Unknown'}' violated via {violation.channel or 'unknown'} "
                f"on endpoint '{violation.endpoint_name or 'unknown'}' by user {violation.user_name or 'unknown'}. "
                f"File: {violation.file_name or 'N/A'}. Action: {violation.action_taken or 'unknown'}."
            )
            asset = violation.endpoint_name or violation.user_name or "unknown"

        elif category == "usb_block":
            event = GTBUSBEvent.model_validate(data)
            if (event.action or "").lower() == "blocked":
                severity = "medium"
                finding = f"USB Device Blocked: {event.device_type or 'Unknown'}"
            else:
                severity = "low"
                finding = f"USB Event: {event.device_type or 'Unknown'}"
            description = (
                f"USB {event.device_type or 'unknown'} device {event.device_id or 'unknown'} "
                f"on endpoint '{event.endpoint_name or 'unknown'}' by user {event.user_name or 'unknown'} "
                f"was {event.action or 'unknown'}."
            )
            asset = event.endpoint_name or event.user_name or "unknown"

        elif category == "exfil":
            event = GTBExfilEvent.model_validate(data)
            severity = "high"
            finding = f"Exfiltration Attempt: {event.destination or 'Unknown'}"
            description = (
                f"Data exfiltration attempt detected on endpoint '{event.endpoint_name or 'unknown'}' "
                f"by user {event.user_name or 'unknown'} to {event.destination or 'unknown'} "
                f"via {event.channel or 'unknown'}. Files: {event.file_count}, Size: {event.total_size_bytes} bytes."
            )
            asset = event.endpoint_name or event.user_name or "unknown"

        else:
            finding = "GTB Finding"
            description = "Unknown GTB finding category."
            severity = "medium"
            asset = "unknown"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="dlp",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Data Protection",
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
