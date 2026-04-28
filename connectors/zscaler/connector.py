"""
Zscaler ZIA / ZTA / CASB connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API key + username + password + cloud
  fetch_findings → pulls web threats, shadow SaaS apps, admin audit logs
  normalize      → maps Zscaler findings → URIPRiskRecord
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
from connectors.zscaler.api_client import ZscalerAPIClient
from connectors.zscaler.schemas import (
    ZscalerAdminAuditLog,
    ZscalerAuditLogsResponse,
    ZscalerSaasAppsResponse,
    ZscalerShadowSaaS,
    ZscalerThreatsResponse,
    ZscalerWebThreat,
)

logger = logging.getLogger(__name__)

# Severity normalization — Zscaler uses same labels, but we guard against unexpected values
SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _map_severity(raw: str) -> str:
    return SEVERITY_MAP.get(raw.lower(), "medium")


@register_connector("zscaler")
class ZscalerConnector(BaseConnector):
    """
    Live connector for Zscaler ZIA / ZTA / CASB.

    Data flow
    ---------
    1. Authenticate with API key + username + password + cloud name.
    2. Fetch web threats (/threatIntel/threats).
    3. Fetch shadow SaaS apps (/casb/saasApps).
    4. Fetch admin audit logs (/users/admin/auditLogs).
    5. Normalize each to URIPRiskRecord.
    """

    NAME = "zscaler"
    # NETWORK / SASE — not in any of the 3 sub-indexes per task spec.
    RISK_INDEX_DOMAIN = None

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Zscaler ZIA / ZTA / CASB"
    CATEGORY = "NETWORK"
    SHORT_DESCRIPTION = (
        "Blocked URLs, shadow SaaS detections, malicious downloads from the secure web gateway."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://help.zscaler.com/zia/api"
    SUPPORTED_PRODUCTS = ["ZIA", "ZTA", "CASB"]
    MODULE_CODE = "NETWORK"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="cloud", label="Cloud", type="select", required=True,
            help_text="Your Zscaler cloud — visible in the admin URL.",
            options=[
                {"value": "zscaler", "label": "zscaler.net"},
                {"value": "zscalerone", "label": "zscalerone.net"},
                {"value": "zscalertwo", "label": "zscalertwo.net"},
                {"value": "zscalerthree", "label": "zscalerthree.net"},
                {"value": "zscloud", "label": "zscloud.net"},
            ],
        ),
        CredentialFieldSpec(
            name="api_key", label="API Key", type="password",
            required=True, secret=True,
            help_text="Administration → API Management → API Key.",
        ),
        CredentialFieldSpec(
            name="username", label="Username", type="text", required=True,
            help_text="Admin user used for the API session.",
        ),
        CredentialFieldSpec(
            name="password", label="Password", type="password",
            required=True, secret=True,
            help_text="Password of the admin user above.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["zscaler"]

    def __init__(self) -> None:
        self._client: ZscalerAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Zscaler credentials.

        Required credential keys:
            - api_key
            - username
            - password
            - cloud         (e.g. zscalerone, zscalertwo, zscaler)
        Optional:
            - tenant_id
        """
        api_key = tenant_credentials.get("api_key")
        username = tenant_credentials.get("username")
        password = tenant_credentials.get("password")
        cloud = tenant_credentials.get("cloud")

        if not api_key:
            raise ConnectorAuthError("Zscaler credentials must include 'api_key'")
        if not username:
            raise ConnectorAuthError("Zscaler credentials must include 'username'")
        if not password:
            raise ConnectorAuthError("Zscaler credentials must include 'password'")
        if not cloud:
            raise ConnectorAuthError("Zscaler credentials must include 'cloud'")

        self._client = ZscalerAPIClient(
            api_key=str(api_key),
            username=str(username),
            password=str(password),
            cloud=str(cloud),
        )

        if not self._client.authenticate():
            raise ConnectorAuthError(
                "Zscaler authentication failed: invalid credentials or cloud"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"zscaler-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull web threats, shadow SaaS apps, and admin audit logs.

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
            # ── Web threats ─────────────────────────────────────────────
            threats_resp = self._client.list_web_threats()
            threats_data = ZscalerThreatsResponse.model_validate(threats_resp)
            for threat in threats_data.threats:
                findings.append(
                    RawFinding(
                        id=threat.id,
                        source=self.NAME,
                        raw_data={
                            **threat.model_dump(mode="json"),
                            "category": "web_threat",
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Shadow SaaS ─────────────────────────────────────────────
            saas_resp = self._client.list_saas_apps()
            saas_data = ZscalerSaasAppsResponse.model_validate(saas_resp)
            for app in saas_data.saasApps:
                if not app.sanctioned:
                    findings.append(
                        RawFinding(
                            id=app.id,
                            source=self.NAME,
                            raw_data={
                                **app.model_dump(mode="json"),
                                "category": "shadow_saas",
                            },
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            # ── Admin audit logs ────────────────────────────────────────
            audit_resp = self._client.list_admin_audit_logs()
            audit_data = ZscalerAuditLogsResponse.model_validate(audit_resp)
            for log in audit_data.auditLogs:
                findings.append(
                    RawFinding(
                        id=log.id,
                        source=self.NAME,
                        raw_data={
                            **log.model_dump(mode="json"),
                            "category": "casb_violation",
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Zscaler: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            msg = str(exc)
            # Attempt to surface the upstream JSON error body if available
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    body = exc.response.json()
                    if isinstance(body, dict) and "error" in body:
                        msg = f"{msg} — {body['error']}"
                except Exception:
                    pass
            self._last_error = msg
            logger.exception("Zscaler fetch_findings failed")
            raise ConnectorFetchError(f"Zscaler fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Zscaler RawFinding to URIPRiskRecord.

        Handles three categories:
          1. web_threat    → network domain
          2. shadow_saas   → cloud domain
          3. casb_violation → network domain
        """
        data = raw.raw_data
        category = data.get("category", "web_threat")
        severity = _map_severity(data.get("severity", "medium"))

        if category == "web_threat":
            threat = ZscalerWebThreat.model_validate(data)
            asset = threat.device or "unknown-device"
            finding = threat.threat_name or "Unknown Web Threat"
            description = (
                f"Zscaler blocked web threat: {finding}. "
                f"URL: {threat.url or 'N/A'}. Asset: {asset}."
            )
            domain = "network"
            owner_team = "Network Security"

        elif category == "shadow_saas":
            app = ZscalerShadowSaaS.model_validate(data)
            asset = app.name or "unknown-app"
            finding = f"Shadow SaaS: {asset}"
            risk_score = app.risk_score or 50
            # Derive severity from risk score if not explicitly set
            if severity == "medium" and risk_score >= 80:
                severity = "high"
            elif severity == "medium" and risk_score <= 30:
                severity = "low"
            description = (
                f"Zscaler CASB detected unsanctioned SaaS app: {asset}. "
                f"Category: {app.category or 'Unknown'}. "
                f"Users: {app.users}. Risk score: {risk_score}."
            )
            domain = "cloud"
            owner_team = "Cloud Security"

        elif category == "casb_violation":
            log = ZscalerAdminAuditLog.model_validate(data)
            asset = log.admin_user or "unknown-admin"
            finding = f"Admin Action: {log.action or 'Unknown'}"
            description = (
                f"Zscaler admin audit log: {log.action} by {asset} "
                f"on resource '{log.resource or 'N/A'}'."
            )
            domain = "network"
            owner_team = "Network Security"

        else:
            finding = "Zscaler Finding"
            description = "Unknown Zscaler finding category."
            asset = "unknown"
            domain = "network"
            owner_team = "Network Security"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain=domain,
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team=owner_team,
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
