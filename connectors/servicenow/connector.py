"""
ServiceNow ITSM connector for URIP-Adaptive Mind.

Implements the BaseConnector contract:
  authenticate   → Basic Auth (username + password) OR OAuth Bearer Token
  fetch_findings → pulls security incidents (/api/now/table/incident)
  normalize      → maps SN incident → URIPRiskRecord
  health_check   → lightweight ping via sys_user table

Bidirectional:
  create_ticket  → creates a ServiceNow incident from URIP risk data
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

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
from connectors.servicenow.api_client import ServiceNowAPIClient
from connectors.servicenow.schemas import ServiceNowIncident, ServiceNowListResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Severity mapping
# ─────────────────────────────────────────────────────────────────────────────

# ServiceNow urgency/impact scale: 1=High, 2=Medium, 3=Low
# URIP severity: critical | high | medium | low
#
# Combined rule (spec §connector.py → normalize()):
#   urgency=1 AND impact=1   → critical
#   urgency=1 OR  impact=1   → high
#   urgency=2 OR  impact=2   → medium
#   else                     → low


def _map_severity(urgency: Optional[str], impact: Optional[str]) -> str:
    """
    Map ServiceNow urgency + impact integers to URIP severity.

    Parameters
    ----------
    urgency : str | None
        ServiceNow urgency field value ("1", "2", or "3").
    impact  : str | None
        ServiceNow impact field value ("1", "2", or "3").

    Returns
    -------
    str
        One of "critical" | "high" | "medium" | "low".
    """
    u = int(urgency) if urgency and urgency.isdigit() else 3
    i = int(impact) if impact and impact.isdigit() else 3

    if u == 1 and i == 1:
        return "critical"
    if u == 1 or i == 1:
        return "high"
    if u == 2 or i == 2:
        return "medium"
    return "low"


def _severity_to_urgency_impact(severity: str) -> tuple[int, int]:
    """
    Reverse map URIP severity → (urgency, impact) for create_ticket.

    Returns
    -------
    tuple[int, int]
        (urgency, impact) both in ServiceNow scale 1=High, 2=Medium, 3=Low.
    """
    mapping: dict[str, tuple[int, int]] = {
        "critical": (1, 1),
        "high":     (1, 2),
        "medium":   (2, 2),
        "low":      (3, 3),
    }
    return mapping.get(severity.lower(), (3, 3))


# ─────────────────────────────────────────────────────────────────────────────
# Connector class
# ─────────────────────────────────────────────────────────────────────────────


@register_connector("servicenow")
class ServiceNowConnector(BaseConnector):
    """
    Live connector for ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu).

    Data flow
    ---------
    1. Authenticate with Basic Auth (username + password) OR OAuth Bearer Token.
    2. Fetch security incidents from /api/now/table/incident using an encoded query.
    3. Normalize each incident to URIPRiskRecord using urgency + impact → severity.
    4. (Bidirectional) Create ServiceNow incidents from URIP risk data via create_ticket().

    Thread / async safety
    ---------------------
    The underlying ServiceNowAPIClient is async (httpx.AsyncClient).  All methods
    on this connector that call the API are therefore async.  The connector
    scheduler (which is sync) must call these via asyncio.run() or an event loop.
    """

    NAME = "servicenow"
    RISK_INDEX_DOMAIN = None   # ITSM — does not feed the Cyber Risk Index directly.

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "ServiceNow"
    CATEGORY = "ITSM"
    SHORT_DESCRIPTION = (
        "Bidirectional sync — push URIP risks as ServiceNow incidents "
        "and ingest security incidents back as risks."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://developer.servicenow.com/dev.do#!/reference/api/utah/rest/c_TableAPI"
    )
    SUPPORTED_PRODUCTS = [
        "ServiceNow ITSM (Utah / Vancouver / Washington / Xanadu)"
    ]
    MODULE_CODE = "ITSM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="instance_url",
            label="Instance URL",
            type="url",
            required=True,
            placeholder="https://your-tenant.service-now.com",
            help_text="Full URL of your ServiceNow instance — must be HTTPS.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="auth_method",
            label="Auth Method",
            type="select",
            required=True,
            help_text="Basic Auth (username + password) or OAuth Bearer Token.",
            options=[
                {"value": "basic", "label": "Username + Password"},
                {"value": "oauth", "label": "OAuth Bearer Token"},
            ],
        ),
        CredentialFieldSpec(
            name="username",
            label="Username",
            type="text",
            required=False,
            help_text="Required when auth_method=basic. Use a dedicated integration user.",
            placeholder="urip_integration",
        ),
        CredentialFieldSpec(
            name="password",
            label="Password",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=basic.",
            placeholder="••••••••",
        ),
        CredentialFieldSpec(
            name="oauth_token",
            label="OAuth Bearer Token",
            type="password",
            required=False,
            secret=True,
            help_text="Required when auth_method=oauth. Bearer token from your IdP.",
            placeholder="eyJ…",
        ),
        CredentialFieldSpec(
            name="risk_query",
            label="Risk Query",
            type="text",
            required=True,
            placeholder="category=security^state!=7",
            help_text=(
                "ServiceNow encoded query that selects security incidents to ingest. "
                "State 7 = Closed. Default fetches all active security incidents."
            ),
            default="category=security^active=true",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["servicenow"]

    def __init__(self) -> None:
        self._client: Optional[ServiceNowAPIClient] = None
        self._instance_url: str = ""
        self._risk_query: str = "category=security^active=true"
        self._last_run: Optional[datetime] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # authenticate
    # ─────────────────────────────────────────────────────────────────────────

    async def authenticate(self, credentials: dict) -> ConnectorSession:  # type: ignore[override]
        """
        Validate ServiceNow credentials and return a ConnectorSession.

        Parameters
        ----------
        credentials : dict
            Must contain:
              - instance_url  (str)
              - auth_method   ("basic" or "oauth")
            If auth_method == "basic":
              - username (str)
              - password (str)
            If auth_method == "oauth":
              - oauth_token (str)
            Optional:
              - risk_query (str) — encoded query for security incidents
              - tenant_id  (str) — URIP tenant scoping

        Raises
        ------
        ConnectorAuthError
            If credentials are missing required fields or the API rejects them.
        """
        instance_url = credentials.get("instance_url", "").strip().rstrip("/")
        auth_method = str(credentials.get("auth_method", "")).lower()
        risk_query = credentials.get("risk_query", "category=security^active=true")

        if not instance_url:
            raise ConnectorAuthError(
                "ServiceNow credentials must include 'instance_url'."
            )
        if auth_method not in ("basic", "oauth"):
            raise ConnectorAuthError(
                f"Unsupported auth_method: {auth_method!r}. Use 'basic' or 'oauth'."
            )

        if auth_method == "basic":
            username = credentials.get("username", "").strip()
            password = credentials.get("password", "")
            if not username or not password:
                raise ConnectorAuthError(
                    "Basic Auth requires 'username' and 'password'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                username=username,
                password=password,
            )
        else:  # oauth
            oauth_token = credentials.get("oauth_token", "").strip()
            if not oauth_token:
                raise ConnectorAuthError(
                    "OAuth mode requires 'oauth_token'."
                )
            self._client = ServiceNowAPIClient(
                instance_url=instance_url,
                oauth_token=oauth_token,
            )

        # Verify connectivity — raises ConnectorAuthError on 401/403.
        try:
            await self._client.healthcheck()
        except ConnectorAuthError:
            raise
        except Exception as exc:
            raise ConnectorAuthError(
                f"ServiceNow connectivity check failed: {exc}"
            ) from exc

        self._instance_url = instance_url
        self._risk_query = risk_query or "category=security^active=true"

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=credentials.get("tenant_id", "unknown"),
            token=f"sn-{auth_method}-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # fetch_findings
    # ─────────────────────────────────────────────────────────────────────────

    async def fetch_findings(  # type: ignore[override]
        self,
        session: ConnectorSession,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[RawFinding]:
        """
        Pull security incidents from ServiceNow.

        Parameters
        ----------
        session : ConnectorSession
            Session returned by authenticate().
        since : datetime, optional
            Fetch incidents updated after this timestamp (encoded into query).
        limit : int
            Maximum incidents to return (default 100).

        Returns
        -------
        list[RawFinding]
            Zero or more raw incident findings.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        query = self._risk_query
        if since:
            ts = since.strftime("%Y-%m-%d %H:%M:%S")
            query = f"{query}^sys_updated_on>{ts}"

        findings: list[RawFinding] = []
        tenant_id = session.tenant_id

        try:
            raw_list = await self._client.list_incidents(query=query, limit=limit)
            # Validate through Pydantic to normalize nested-object fields.
            response = ServiceNowListResponse(result=raw_list)

            for incident in response.result:
                findings.append(
                    RawFinding(
                        id=incident.sys_id,
                        source=self.NAME,
                        raw_data=incident.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "ServiceNow: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("ServiceNow fetch_findings failed")
            raise ConnectorFetchError(
                f"ServiceNow fetch failed: {exc}"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────────
    # normalize
    # ─────────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:  # type: ignore[override]
        """
        Map a ServiceNow RawFinding to a URIPRiskRecord.

        Severity logic (urgency=1=High, 2=Medium, 3=Low; same for impact):
          - urgency=1 AND impact=1  → critical
          - urgency=1 OR  impact=1  → high
          - urgency=2 OR  impact=2  → medium
          - else                    → low

        External ID = sys_id.
        Source URL  = instance_url + /nav_to.do?uri=incident.do?sys_id={sys_id}
        """
        data = raw.raw_data
        incident = ServiceNowIncident.model_validate(data)

        severity = _map_severity(incident.urgency, incident.impact)

        finding = f"SN Incident: {incident.short_description or 'Unknown'}"
        description = (
            f"ServiceNow incident {incident.number or incident.sys_id}: "
            f"{incident.short_description or 'N/A'}. "
            f"State: {incident.state or 'unknown'}. "
            f"Urgency: {incident.urgency or 'unknown'}, "
            f"Impact: {incident.impact or 'unknown'}. "
            f"Detail: {incident.description or 'N/A'}."
        )

        source_url = (
            f"{self._instance_url}/nav_to.do?uri=incident.do?sys_id={incident.sys_id}"
        )

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="application",
            cvss_score=0.0,
            severity=severity,
            asset=incident.assigned_to or incident.caller_id or "unknown",
            owner_team="IT Service Management",
            cve_id=None,
            exploit_status=None,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # health_check
    # ─────────────────────────────────────────────────────────────────────────

    async def health_check(  # type: ignore[override]
        self,
        session: ConnectorSession,
    ) -> ConnectorHealth:
        """
        Return connector operational status.

        Makes a lightweight GET /api/now/table/sys_user?sysparm_limit=1 call.
        Returns status="ok" on success, "degraded" or "error" on failure.
        Never raises — returns ConnectorHealth with status="error" instead.
        """
        try:
            if self._client is None:
                return ConnectorHealth(
                    connector_name=self.NAME,
                    status="error",
                    last_run=self._last_run,
                    error_count=self._error_count,
                    last_error="Client not initialised — call authenticate() first.",
                )
            await self._client.healthcheck()
            return ConnectorHealth(
                connector_name=self.NAME,
                status="ok",
                last_run=self._last_run,
                error_count=self._error_count,
                last_error=self._last_error,
            )
        except Exception as exc:
            err = str(exc)
            self._error_count += 1
            self._last_error = err
            logger.warning("ServiceNow health_check failed: %s", err)
            return ConnectorHealth(
                connector_name=self.NAME,
                status="degraded",
                last_run=self._last_run,
                error_count=self._error_count,
                last_error=err,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # create_ticket (bidirectional)
    # ─────────────────────────────────────────────────────────────────────────

    async def create_ticket(
        self,
        session: ConnectorSession,
        risk: URIPRiskRecord,
    ) -> dict[str, Any]:
        """
        Create a ServiceNow incident from a URIP risk record.

        Maps URIP severity → urgency + impact using the reverse of _map_severity:
          critical → (1, 1)
          high     → (1, 2)
          medium   → (2, 2)
          low      → (3, 3)

        Parameters
        ----------
        session : ConnectorSession
            Active session (used for tenant scoping in logs).
        risk : URIPRiskRecord
            Normalized URIP risk to push as an incident.

        Returns
        -------
        dict
            {"sys_id": str, "number": str, "url": str}
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        urgency, impact = _severity_to_urgency_impact(risk.severity)

        short_description = risk.finding[:160] if risk.finding else "URIP Auto-Created Incident"
        description = risk.description or "Auto-created by URIP risk intelligence platform."

        try:
            result = await self._client.create_incident(
                short_description=short_description,
                description=description,
                urgency=urgency,
                impact=impact,
                category="security",
            )
            sys_id = result.get("sys_id", "")
            number = result.get("number", "")
            url = (
                f"{self._instance_url}/nav_to.do?uri=incident.do?sys_id={sys_id}"
                if sys_id
                else ""
            )
            logger.info(
                "ServiceNow: created incident %s (sys_id=%s) for tenant %s",
                number,
                sys_id,
                session.tenant_id,
            )
            return {"sys_id": sys_id, "number": number, "url": url}

        except (ConnectorAuthError, ConnectorFetchError):
            raise
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("ServiceNow create_ticket failed")
            raise ConnectorFetchError(
                f"ServiceNow create_ticket failed: {exc}"
            ) from exc
