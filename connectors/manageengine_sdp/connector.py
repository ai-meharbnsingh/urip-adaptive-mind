"""
ManageEngine ServiceDesk Plus connector for URIP.

Implements the BaseConnector contract:
  authenticate   → OAuth or Auth Token
  fetch_findings → pulls security tickets (/api/v3/requests)
  normalize      → maps SDP ticket → URIPRiskRecord
  health_check   → returns operational status

Bidirectional:
  create_ticket  → creates a ticket in SDP from risk data
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
from connectors.manageengine_sdp.api_client import ManageEngineSdpAPIClient
from connectors.manageengine_sdp.schemas import (
    ManageEngineSdpCreateTicketResponse,
    ManageEngineSdpRequestsResponse,
    ManageEngineSdpTicket,
)

logger = logging.getLogger(__name__)

# SDP priority → URIP severity
PRIORITY_SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _map_priority(priority: str | None) -> str:
    return PRIORITY_SEVERITY_MAP.get((priority or "").lower(), "medium")


@register_connector("manageengine_sdp")
class ManageEngineSdpConnector(BaseConnector):
    """
    Live connector for ManageEngine ServiceDesk Plus.

    Data flow
    ---------
    1. Authenticate with OAuth (client_id + client_secret + refresh_token)
       OR Auth Token (auth_token).
    2. Fetch tickets (/api/v3/requests).
    3. Normalize each to URIPRiskRecord.
    4. (Bidirectional) Create tickets from risk data via create_ticket().
    """

    NAME = "manageengine_sdp"
    # ITSM ticketing connector — no risk-index contribution.
    RISK_INDEX_DOMAIN = None

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ManageEngine ServiceDesk Plus"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync of risks → tickets and ticket status updates back to URIP."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://www.manageengine.com/products/service-desk/sdpod-v3-api/"
    )
    SUPPORTED_PRODUCTS = ["ServiceDesk Plus Cloud", "ServiceDesk Plus On-Premises"]
    MODULE_CODE = "ITSM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="SDP Base URL", type="url", required=True,
            placeholder="https://sdpondemand.manageengine.com",
            help_text="SDP cloud or on-prem URL — must be HTTPS.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method", label="Auth Method", type="select", required=True,
            help_text="OAuth (recommended) or static auth token.",
            options=[
                {"value": "oauth", "label": "OAuth 2.0"},
                {"value": "token", "label": "Static Auth Token"},
            ],
        ),
        CredentialFieldSpec(
            name="client_id", label="Client ID (OAuth)", type="text",
            required=False,
            help_text="Required when auth_method=oauth.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="Client Secret (OAuth)", type="password",
            required=False, secret=True,
            help_text="Required when auth_method=oauth.",
        ),
        CredentialFieldSpec(
            name="refresh_token", label="Refresh Token (OAuth)", type="password",
            required=False, secret=True,
            help_text="Required when auth_method=oauth.",
        ),
        CredentialFieldSpec(
            name="auth_token", label="Auth Token (Static)", type="password",
            required=False, secret=True,
            help_text="Required when auth_method=token.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["manageengine_sdp"]

    def __init__(self) -> None:
        self._client: ManageEngineSdpAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate ManageEngine SDP credentials.

        Required credential keys:
            - auth_method   ("oauth" or "token")
            - base_url
        If auth_method == "oauth":
            - client_id
            - client_secret
            - refresh_token
        If auth_method == "token":
            - auth_token
        Optional:
            - tenant_id
        """
        auth_method = tenant_credentials.get("auth_method")
        base_url = tenant_credentials.get("base_url")

        if not auth_method:
            raise ConnectorAuthError(
                "ManageEngine SDP credentials must include 'auth_method' (oauth or token)"
            )
        if not base_url:
            raise ConnectorAuthError(
                "ManageEngine SDP credentials must include 'base_url'"
            )

        auth_method = str(auth_method).lower()

        if auth_method == "oauth":
            client_id = tenant_credentials.get("client_id")
            client_secret = tenant_credentials.get("client_secret")
            refresh_token = tenant_credentials.get("refresh_token")
            if not client_id or not client_secret or not refresh_token:
                raise ConnectorAuthError(
                    "OAuth mode requires 'client_id', 'client_secret', and 'refresh_token'"
                )
            self._client = ManageEngineSdpAPIClient(
                auth_method=auth_method,
                base_url=str(base_url),
                client_id=str(client_id),
                client_secret=str(client_secret),
                refresh_token=str(refresh_token),
            )
        elif auth_method == "token":
            auth_token = tenant_credentials.get("auth_token")
            if not auth_token:
                raise ConnectorAuthError(
                    "Token mode requires 'auth_token'"
                )
            self._client = ManageEngineSdpAPIClient(
                auth_method=auth_method,
                base_url=str(base_url),
                auth_token=str(auth_token),
            )
        else:
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method}. Use 'oauth' or 'token'."
            )

        if not self._client.authenticate():
            raise ConnectorAuthError(
                "ManageEngine SDP authentication failed"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"sdp-{auth_method}-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull security tickets from SDP.

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
            resp = self._client.list_requests()
            data = ManageEngineSdpRequestsResponse.model_validate(resp)

            for ticket in data.requests:
                # Filter by security category if present
                category = (ticket.category or "").lower()
                if category in ("security", ""):
                    findings.append(
                        RawFinding(
                            id=ticket.id,
                            source=self.NAME,
                            raw_data=ticket.model_dump(mode="json"),
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            logger.info(
                "ManageEngine SDP: fetched %d findings for tenant %s",
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
            logger.exception("ManageEngine SDP fetch_findings failed")
            raise ConnectorFetchError(f"ManageEngine SDP fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """Map an SDP RawFinding to URIPRiskRecord."""
        data = raw.raw_data
        ticket = ManageEngineSdpTicket.model_validate(data)

        severity = _map_priority(ticket.priority)
        finding = f"SDP Ticket: {ticket.subject or 'Unknown'}"
        description = (
            f"ManageEngine SDP ticket #{ticket.id}: {ticket.subject or 'N/A'}. "
            f"Status: {ticket.status or 'unknown'}. "
            f"Priority: {ticket.priority or 'unknown'}. "
            f"Description: {ticket.description or 'N/A'}."
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=ticket.requester or "unknown-requester",
            owner_team="IT Service Management",
            cve_id=None,
            exploit_status=None,
        )

    def create_ticket(self, risk_data: dict[str, Any]) -> str:
        """
        Create a ticket in ManageEngine SDP from risk data.

        Parameters
        ----------
        risk_data : dict
            Must contain at least 'subject' and 'description'.
            Optional: 'priority', 'requester', 'category'.

        Returns
        -------
        str
            The created ticket ID.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        payload = {
            "subject": risk_data.get("subject", "URIP Auto-Created Ticket"),
            "description": risk_data.get(
                "description", "Auto-created by URIP risk intelligence platform."
            ),
            "priority": risk_data.get("priority", "Medium"),
            "category": risk_data.get("category", "Security"),
            "requester": risk_data.get("requester", "urip@example.com"),
        }

        try:
            resp = self._client.create_request(payload)
            data = ManageEngineSdpCreateTicketResponse.model_validate(resp)
            ticket_id = data.request.get("id", "unknown")
            logger.info("ManageEngine SDP: created ticket %s", ticket_id)
            return ticket_id
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
            logger.exception("ManageEngine SDP create_ticket failed")
            raise ConnectorFetchError(f"ManageEngine SDP create_ticket failed: {msg}") from exc

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
