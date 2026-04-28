"""
Network Access Control connector for URIP.

Sub-adapter pattern:
- tenant_credentials['nac_type'] in {'forescout', 'cisco_ise'}
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
    ConnectorNormalizeError,
    ConnectorSession,
    CredentialFieldSpec,
    RawFinding,
    URIPRiskRecord,
)
from connectors.base.registry import register_connector
from connectors.base.setup_guides_data import SETUP_GUIDES
from connectors.forescout_nac.api_client import CiscoISEAPIClient, ForescoutAPIClient
from connectors.forescout_nac.schemas import (
    CiscoISEEndpointSearchResult,
    ForescoutAlert,
    ForescoutDevice,
    ForescoutEvent,
    ForescoutListResponse,
    ForescoutOAuthToken,
)

logger = logging.getLogger(__name__)


def _severity(label: str | None) -> str:
    if not label:
        return "medium"
    label = str(label).lower()
    if label in {"critical", "high", "medium", "low"}:
        return label
    if label in {"warn", "warning"}:
        return "medium"
    return "low"


@register_connector("forescout_nac")
class ForescoutNACConnector(BaseConnector):
    NAME = "forescout_nac"
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "Network Access Control"
    CATEGORY = "NAC"
    SHORT_DESCRIPTION = "Rogue device alerts, NAC events, and device classification (Forescout/Cisco ISE)."
    STATUS = "live"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = ["Forescout eyeSight", "Cisco ISE"]
    MODULE_CODE = "NETWORK"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="nac_type",
            label="NAC Vendor",
            type="select",
            required=True,
            options=[
                {"value": "forescout", "label": "Forescout eyeSight"},
                {"value": "cisco_ise", "label": "Cisco ISE (ERS API)"},
            ],
            help_text="Select which NAC system to connect for this tenant.",
        ),
        CredentialFieldSpec(
            name="base_url",
            label="Base URL",
            type="url",
            required=True,
            placeholder="https://nac.example",
            pattern=r"^https://[^\s]+$",
        ),
        # Forescout OAuth2
        CredentialFieldSpec(
            name="client_id",
            label="OAuth Client ID (Forescout)",
            type="text",
            required=False,
            help_text="Required when nac_type=forescout.",
        ),
        CredentialFieldSpec(
            name="client_secret",
            label="OAuth Client Secret (Forescout)",
            type="password",
            required=False,
            secret=True,
            help_text="Required when nac_type=forescout.",
        ),
        # Cisco ISE ERS
        CredentialFieldSpec(
            name="username",
            label="Username (Cisco ISE)",
            type="text",
            required=False,
            help_text="Required when nac_type=cisco_ise.",
        ),
        CredentialFieldSpec(
            name="password",
            label="Password (Cisco ISE)",
            type="password",
            required=False,
            secret=True,
            help_text="Required when nac_type=cisco_ise.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["forescout_nac"]

    def __init__(self) -> None:
        self._client: ForescoutAPIClient | CiscoISEAPIClient | None = None
        self._nac_type: str | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        nac_type = tenant_credentials.get("nac_type")
        if not nac_type:
            raise ConnectorAuthError("NAC credentials must include 'nac_type'")
        if nac_type not in {"forescout", "cisco_ise"}:
            raise ConnectorAuthError("nac_type must be one of: 'forescout', 'cisco_ise'")

        base_url = tenant_credentials.get("base_url")
        if not base_url:
            raise ConnectorAuthError("NAC credentials must include 'base_url'")

        transport = tenant_credentials.get("_transport")
        self._nac_type = str(nac_type)

        if self._nac_type == "forescout":
            client_id = tenant_credentials.get("client_id")
            client_secret = tenant_credentials.get("client_secret")
            if not client_id or not client_secret:
                raise ConnectorAuthError(
                    "Forescout credentials must include 'client_id' and 'client_secret'"
                )
            self._client = ForescoutAPIClient(
                base_url=str(base_url),
                client_id=str(client_id),
                client_secret=str(client_secret),
                transport=transport,
            )
            token_json = self._client.fetch_token()
            ForescoutOAuthToken.model_validate(token_json)
            if not self._client.validate_auth():
                raise ConnectorAuthError("Forescout authentication failed: token rejected")

        else:
            username = tenant_credentials.get("username")
            password = tenant_credentials.get("password")
            if not username or not password:
                raise ConnectorAuthError(
                    "Cisco ISE credentials must include 'username' and 'password'"
                )
            self._client = CiscoISEAPIClient(
                base_url=str(base_url),
                username=str(username),
                password=str(password),
                transport=transport,
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("Cisco ISE authentication failed: invalid credentials or URL")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"nac-{self._nac_type}-session",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"nac_type": self._nac_type},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None or not self._nac_type:
            raise ConnectorFetchError("Connector not authenticated. Call authenticate() first.")

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            if self._nac_type == "forescout":
                alerts = ForescoutListResponse.model_validate(self._client.list_alerts())
                events = ForescoutListResponse.model_validate(self._client.list_events())
                devices = ForescoutListResponse.model_validate(self._client.list_devices())

                for a in alerts.data:
                    alert = ForescoutAlert.model_validate(a)
                    findings.append(
                        RawFinding(
                            id=alert.id,
                            source=self.NAME,
                            raw_data={
                                "record_type": "alert",
                                "alert": alert.model_dump(mode="json"),
                            },
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

                for e in events.data:
                    event = ForescoutEvent.model_validate(e)
                    findings.append(
                        RawFinding(
                            id=event.id,
                            source=self.NAME,
                            raw_data={
                                "record_type": "event",
                                "event": event.model_dump(mode="json"),
                            },
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

                for d in devices.data:
                    device = ForescoutDevice.model_validate(d)
                    findings.append(
                        RawFinding(
                            id=device.id,
                            source=self.NAME,
                            raw_data={
                                "record_type": "device",
                                "device": device.model_dump(mode="json"),
                            },
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

                self._last_run = datetime.now(timezone.utc)
                if not alerts.data and not events.data and not devices.data:
                    return []
                return findings

            # Cisco ISE: baseline uses endpoint inventory as NAC device feed.
            resp = self._client.list_endpoints(size=50, page=1)
            CiscoISEEndpointSearchResult.model_validate(resp)
            resources = resp.get("SearchResult", {}).get("resources", []) or []
            for r in resources:
                endpoint_id = r.get("id") or r.get("name") or "unknown"
                findings.append(
                    RawFinding(
                        id=str(endpoint_id),
                        source=self.NAME,
                        raw_data={
                            "record_type": "ise_endpoint",
                            "endpoint": r,
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("NAC fetch_findings failed")
            raise ConnectorFetchError(f"NAC fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        try:
            record_type = raw.raw_data.get("record_type")
            if record_type == "alert":
                alert = ForescoutAlert.model_validate(raw.raw_data.get("alert") or {})
                asset = alert.device or alert.id
                severity = _severity(alert.severity)
                return URIPRiskRecord(
                    finding=f"NAC Alert: {alert.type}",
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity=severity,
                    asset=asset,
                    owner_team="Network Security",
                    description=f"NAC alert {alert.id}: {alert.type} on device {asset}.",
                )

            if record_type == "event":
                event = ForescoutEvent.model_validate(raw.raw_data.get("event") or {})
                asset = event.device or event.id
                severity = _severity(event.severity)
                return URIPRiskRecord(
                    finding=f"NAC Event: {event.event_type}",
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity=severity,
                    asset=asset,
                    owner_team="Network Security",
                    description=f"NAC event {event.id}: {event.event_type} on device {asset}.",
                )

            if record_type == "device":
                device = ForescoutDevice.model_validate(raw.raw_data.get("device") or {})
                asset = device.mac or device.id
                return URIPRiskRecord(
                    finding="NAC Device Classification",
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity="low",
                    asset=asset,
                    owner_team="Network Security",
                    description=f"Device {asset} classified as {device.classification or 'unknown'}.",
                )

            if record_type == "ise_endpoint":
                endpoint = raw.raw_data.get("endpoint") or {}
                asset = str(endpoint.get("name") or endpoint.get("id") or raw.id)
                return URIPRiskRecord(
                    finding="Cisco ISE Endpoint Inventory",
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity="low",
                    asset=asset,
                    owner_team="Network Security",
                    description="Cisco ISE endpoint inventory record.",
                )

            raise ConnectorNormalizeError(f"Unsupported NAC record_type: {record_type}")

        except ConnectorNormalizeError:
            raise
        except Exception as exc:
            raise ConnectorNormalizeError(f"NAC normalize failed: {exc}") from exc

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

