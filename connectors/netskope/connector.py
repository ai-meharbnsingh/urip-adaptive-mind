"""
Netskope CASB + DLP connector for URIP.

Implements the BaseConnector contract:
  authenticate   → OAuth2 client credentials flow
  fetch_findings → pulls DLP incidents, cloud threats, anomalies
  normalize      → maps Netskope findings → URIPRiskRecord
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
from connectors.netskope.api_client import NetskopeAPIClient
from connectors.netskope.schemas import NetskopeIncidentsResponse

logger = logging.getLogger(__name__)

# Severity normalization
SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _map_severity(raw: str) -> str:
    return SEVERITY_MAP.get(raw.lower(), "medium")


@register_connector("netskope")
class NetskopeConnector(BaseConnector):
    """
    Live connector for Netskope CASB + DLP.

    Data flow
    ---------
    1. Authenticate with client_id + client_secret (OAuth2).
    2. Fetch DLP incidents (/incidents/dlp).
    3. Fetch cloud threats (/incidents/threats).
    4. Fetch anomalies (/incidents/anomalies).
    5. Normalize each to URIPRiskRecord.
    """

    NAME = "netskope"
    # Netskope is DLP — same connector category as gtb-dlp listed in the
    # task spec under ATTACK.  Treat the same.
    RISK_INDEX_DOMAIN = "attack"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "Netskope CASB + DLP"
    CATEGORY = "DLP"
    SHORT_DESCRIPTION = (
        "DLP incidents, cloud threats, anomalies, and shadow-IT visibility from Netskope SASE."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.netskope.com/en/rest-api-v2-overview-312207.html"
    SUPPORTED_PRODUCTS = ["CASB", "DLP", "SWG"]
    MODULE_CODE = "DLP"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="Tenant URL", type="url", required=True,
            placeholder="https://tenant.goskope.com",
            help_text="Your Netskope tenant URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="client_id", label="Client ID", type="text", required=True,
            help_text="OAuth2 client ID from the Netskope REST API v2 token page.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="Client Secret", type="password",
            required=True, secret=True,
            help_text="OAuth2 client secret — issued once, store securely.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["netskope"]

    def __init__(self) -> None:
        self._client: NetskopeAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Netskope OAuth2 credentials.

        Required credential keys:
            - client_id
            - client_secret
            - base_url    (e.g. https://tenant.goskope.com)
        Optional:
            - tenant_id
        """
        client_id = tenant_credentials.get("client_id")
        client_secret = tenant_credentials.get("client_secret")
        base_url = tenant_credentials.get("base_url")

        if not client_id:
            raise ConnectorAuthError("Netskope credentials must include 'client_id'")
        if not client_secret:
            raise ConnectorAuthError("Netskope credentials must include 'client_secret'")
        if not base_url:
            raise ConnectorAuthError("Netskope credentials must include 'base_url'")

        self._client = NetskopeAPIClient(
            client_id=str(client_id),
            client_secret=str(client_secret),
            base_url=str(base_url),
        )

        if not self._client.authenticate():
            raise ConnectorAuthError(
                "Netskope authentication failed: invalid client_id or client_secret"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"netskope-{str(client_id)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull DLP incidents, cloud threats, and anomalies.

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
            # ── DLP incidents ───────────────────────────────────────────
            dlp_resp = self._client.list_dlp_incidents()
            dlp_data = NetskopeIncidentsResponse.model_validate(dlp_resp)
            for item in dlp_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "dlp"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Cloud threats ───────────────────────────────────────────
            threats_resp = self._client.list_threats()
            threats_data = NetskopeIncidentsResponse.model_validate(threats_resp)
            for item in threats_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "threat"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # ── Anomalies ───────────────────────────────────────────────
            anomalies_resp = self._client.list_anomalies()
            anomalies_data = NetskopeIncidentsResponse.model_validate(anomalies_resp)
            for item in anomalies_data.data:
                findings.append(
                    RawFinding(
                        id=item.get("id", "unknown"),
                        source=self.NAME,
                        raw_data={**item, "category": "anomaly"},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Netskope: fetched %d findings for tenant %s",
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
            logger.exception("Netskope fetch_findings failed")
            raise ConnectorFetchError(f"Netskope fetch failed: {msg}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a Netskope RawFinding to URIPRiskRecord.

        Handles three categories:
          1. dlp      → Data Protection
          2. threat   → Cloud Security
          3. anomaly  → Cloud Security
        """
        data = raw.raw_data
        category = data.get("category", "dlp")
        severity = _map_severity(data.get("severity", "medium"))
        user = data.get("user") or data.get("user_id") or "unknown-user"
        app = data.get("app") or data.get("application") or "unknown-app"

        if category == "dlp":
            name = data.get("incident_name") or "Unknown DLP Incident"
            finding = f"DLP: {name}"
            description = (
                f"Netskope DLP violation: {name}. User: {user}. App: {app}."
            )
            owner_team = "Data Protection"

        elif category == "threat":
            name = data.get("threat_name") or "Unknown Cloud Threat"
            finding = f"Cloud Threat: {name}"
            description = (
                f"Netskope cloud threat: {name}. User: {user}. App: {app}."
            )
            owner_team = "Cloud Security"

        elif category == "anomaly":
            name = data.get("anomaly_name") or "Unknown Anomaly"
            finding = f"Anomaly: {name}"
            description = (
                f"Netskope anomaly: {name}. User: {user}. App: {app}."
            )
            owner_team = "Cloud Security"

        else:
            finding = "Netskope Finding"
            description = "Unknown Netskope finding category."
            owner_team = "Cloud Security"

        return URIPRiskRecord(
            finding=finding,
            description=description,
            source=self.NAME,
            domain="cloud",
            cvss_score=0.0,
            severity=severity,
            asset=user,
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
