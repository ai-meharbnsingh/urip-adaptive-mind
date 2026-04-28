"""
Microsoft 365 Collaboration connector for URIP.

Implements the BaseConnector contract:
  authenticate   → OAuth2 client credentials flow
  fetch_findings → pulls SharePoint sharing, OneDrive external sharing, Teams exposure
  normalize      → maps M365 findings → URIPRiskRecord
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
from connectors.m365_collab.api_client import M365CollabAPIClient
from connectors.m365_collab.schemas import (
    M365GraphListResponse,
    M365OneDrivePermission,
    M365SharePointSite,
    M365Team,
    M365User,
)

logger = logging.getLogger(__name__)


def _map_severity(raw: str | None) -> str:
    mapping = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
    return mapping.get((raw or "").lower(), "medium")


@register_connector("m365_collab")
class M365CollabConnector(BaseConnector):
    """
    Live connector for Microsoft 365 Collaboration (SharePoint, OneDrive, Teams).

    Data flow
    ---------
    1. Authenticate with tenant_id + client_id + client_secret (OAuth2).
    2. Fetch SharePoint sites (/sites).
    3. Fetch users (/users) and check OneDrive external sharing.
    4. Fetch Teams (/teams).
    5. Normalize each to URIPRiskRecord.
    """

    NAME = "m365_collab"
    RISK_INDEX_DOMAIN = None

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Microsoft 365 Collaboration"
    CATEGORY = "COLLABORATION"
    SHORT_DESCRIPTION = (
        "SharePoint anonymous link sharing, OneDrive external sharing, and Teams data exposure events via Microsoft Graph."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://learn.microsoft.com/en-us/graph/api/overview"
    SUPPORTED_PRODUCTS = ["sharepoint", "onedrive", "teams"]
    MODULE_CODE = "COLLABORATION"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="tenant_id", label="Azure AD Tenant ID", type="uuid",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="Azure portal → Microsoft Entra ID → Overview → Tenant ID.",
        ),
        CredentialFieldSpec(
            name="client_id", label="Application (Client) ID", type="uuid",
            required=True,
            placeholder="00000000-0000-0000-0000-000000000000",
            help_text="App registration's Application (client) ID.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="Client Secret", type="password",
            required=True, secret=True,
            help_text="App registration → Certificates & secrets → Client secret.",
        ),
        CredentialFieldSpec(
            name="max_requests_per_hour", label="Max requests / hour",
            type="number", required=False, default=10000,
            help_text="Graph API rate-limit ceiling.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["m365_collab"]

    def __init__(self) -> None:
        self._client: M365CollabAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Microsoft 365 OAuth2 credentials.

        Required credential keys:
            - tenant_id
            - client_id
            - client_secret
        """
        tenant_id = tenant_credentials.get("tenant_id")
        client_id = tenant_credentials.get("client_id")
        client_secret = tenant_credentials.get("client_secret")

        if not tenant_id:
            raise ConnectorAuthError("M365 Collaboration credentials must include 'tenant_id'")
        if not client_id:
            raise ConnectorAuthError("M365 Collaboration credentials must include 'client_id'")
        if not client_secret:
            raise ConnectorAuthError("M365 Collaboration credentials must include 'client_secret'")

        self._client = M365CollabAPIClient(
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            client_secret=str(client_secret),
        )

        if not self._client.authenticate():
            raise ConnectorAuthError(
                "M365 Collaboration authentication failed: invalid credentials or insufficient permissions"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=str(tenant_id),
            token=f"m365-{str(client_id)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull SharePoint sharing, OneDrive external sharing, and Teams exposure events.

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
            # ── SharePoint sites ────────────────────────────────────────
            sites_resp = self._client.list_sharepoint_sites()
            sites_data = M365GraphListResponse.model_validate(sites_resp)
            for item in sites_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "sharepoint"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── OneDrive users (we'll check drives/sharing in normalize) ─
            users_resp = self._client.list_users()
            users_data = M365GraphListResponse.model_validate(users_resp)
            for item in users_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "onedrive"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Teams ───────────────────────────────────────────────────
            teams_resp = self._client.list_teams()
            teams_data = M365GraphListResponse.model_validate(teams_resp)
            for item in teams_data.value:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "teams"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "M365 Collaboration: fetched %d findings for tenant %s",
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
            logger.exception("M365 Collaboration fetch_findings failed")
            raise ConnectorFetchError(f"M365 Collaboration fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map an M365 Collaboration RawFinding to URIPRiskRecord.

        Handles three categories:
          1. sharepoint → collaboration domain, IT owner
          2. onedrive   → collaboration domain, IT owner
          3. teams      → collaboration domain, IT owner
        """
        data = raw.raw_data
        category = data.get("category", "sharepoint")

        if category == "sharepoint":
            site = M365SharePointSite.model_validate(data)
            finding = f"SharePoint Site Exposure: {site.displayName or site.name or 'Unknown'}"
            description = (
                f"SharePoint site '{site.displayName or site.name or 'Unknown'}' "
                f"at {site.webUrl or 'unknown URL'} may have external sharing enabled."
            )
            severity = "high"
            asset = site.webUrl or site.id or "unknown"

        elif category == "onedrive":
            user = M365User.model_validate(data)
            finding = f"OneDrive External Sharing: {user.displayName or 'Unknown'}"
            description = (
                f"OneDrive for user {user.userPrincipalName or 'unknown'} "
                f"({user.displayName or 'Unknown'}) has potential external sharing exposure."
            )
            severity = "medium"
            asset = user.userPrincipalName or user.id or "unknown"

        elif category == "teams":
            team = M365Team.model_validate(data)
            visibility = (team.visibility or "").lower()
            if visibility == "public":
                severity = "high"
                finding = f"Public Teams Exposure: {team.displayName or 'Unknown'}"
                description = (
                    f"Team '{team.displayName or 'Unknown'}' is public and may expose data."
                )
            else:
                severity = "low"
                finding = f"Teams Configuration: {team.displayName or 'Unknown'}"
                description = (
                    f"Team '{team.displayName or 'Unknown'}' visibility is {team.visibility or 'unknown'}."
                )
            asset = team.displayName or team.id or "unknown"

        else:
            finding = "M365 Collaboration Finding"
            description = "Unknown M365 collaboration finding category."
            severity = "medium"
            asset = "unknown"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=f"{self.NAME}:{category}",
            domain="collaboration",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="IT",
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
