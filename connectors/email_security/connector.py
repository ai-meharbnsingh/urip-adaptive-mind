"""
Email Security connector for URIP (Google Workspace + Microsoft Defender for O365).

Implements the BaseConnector contract:
  authenticate   → OAuth2 per provider
  fetch_findings → phishing/BEC/malicious attachment/DMARC/SPF/DKIM alerts
  normalize      → maps alert → URIPRiskRecord
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
from connectors.email_security.api_client import GoogleWorkspaceAPIClient, M365DefenderAPIClient

logger = logging.getLogger(__name__)

# Google severity may be HIGH / MEDIUM / LOW; M365 uses high / medium / low
# We also heuristically bump confirmed phishing/BEC to critical
SEVERITY_MAP = {
    "critical": ("critical", 9.0),
    "high": ("high", 7.5),
    "medium": ("medium", 5.0),
    "low": ("low", 3.0),
}

HIGH_ALERT_TYPES = {
    "phishing",
    "user reported phishing",
}

CRITICAL_ALERT_TYPES = {
    "business email compromise",
    "bec",
    "malware",
    "suspicious email",
}

SUSPICIOUS_ALERT_TYPES = {
    "suspicious login",
    "suspicious sign-in",
    "impossible travel",
    "anomalous activity",
}

HYGIENE_ALERT_TYPES = {
    "dmarc failure",
    "spf failure",
    "dkim failure",
    "dmarc",
    "spf",
    "dkim",
    "spfrecord",
    "dmarcrecord",
    "dkimrecord",
}


def _classify_email_alert(alert_type: str | None, native_severity: str | None) -> tuple[str, float]:
    alert_lower = (alert_type or "").lower()
    native_lower = (native_severity or "").lower()

    if any(t in alert_lower for t in CRITICAL_ALERT_TYPES):
        return SEVERITY_MAP["critical"]
    if any(t in alert_lower for t in HIGH_ALERT_TYPES):
        return SEVERITY_MAP["high"]
    if any(t in alert_lower for t in SUSPICIOUS_ALERT_TYPES):
        return SEVERITY_MAP["medium"]
    if any(t in alert_lower for t in HYGIENE_ALERT_TYPES):
        return SEVERITY_MAP["low"]

    return SEVERITY_MAP.get(native_lower, ("medium", 5.0))


@register_connector("email_security")
class EmailSecurityConnector(BaseConnector):
    """
    Live connector for Email Security (Google Workspace + M365 Defender).

    Data flow
    ---------
    1. authenticate → OAuth2 flow per provider.
    2. fetch_findings → pull alerts from Alert Center API or Graph Security API.
    3. normalize → map each alert to URIPRiskRecord.
    """

    NAME = "email_security"
    RISK_INDEX_DOMAIN = None

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["email_security"]
    DISPLAY_NAME = "Email Security"
    # CATEGORY must be in CONNECTOR_CATEGORIES (connectors/base/connector.py).
    # Allow-list spelling is uppercase EMAIL (matches the Tool Catalog filter chip).
    CATEGORY = "EMAIL"
    SHORT_DESCRIPTION = (
        "Pulls phishing, BEC, and hygiene alerts from Google Workspace and M365 Defender."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://developers.google.com/workspace/admin/reports/v1/reference"
    SUPPORTED_PRODUCTS = ["Google Workspace Admin Reports", "Microsoft Defender for Office 365"]
    MODULE_CODE = "EMAIL_COLLAB"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = [
        CredentialFieldSpec(
            name="provider",
            label="Email provider",
            type="select",
            required=True,
            options=[
                {"value": "google_workspace", "label": "Google Workspace"},
                {"value": "m365_defender", "label": "Microsoft Defender for O365"},
            ],
        ),
        CredentialFieldSpec(name="tenant_domain", label="Tenant domain (Google) / Tenant ID (M365)", type="text", required=True),
        CredentialFieldSpec(name="service_account_json", label="Service-account JSON (Google)", type="password", required=False, secret=True),
        CredentialFieldSpec(name="client_id", label="Client ID (M365)", type="text", required=False),
        CredentialFieldSpec(name="client_secret", label="Client secret (M365)", type="password", required=False, secret=True),
    ]

    def __init__(self) -> None:
        self._client: GoogleWorkspaceAPIClient | M365DefenderAPIClient | None = None
        self._provider: str = ""
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate Email Security credentials based on provider.

        Required credential keys:
            - provider  (google_workspace | m365_defender)
        Per-provider:
            - Google Workspace: service_account_json + admin_email
            - M365 Defender: client_id + client_secret + tenant_id
        """
        provider = (tenant_credentials.get("provider") or "").lower()
        if not provider:
            raise ConnectorAuthError("Email Security credentials must include 'provider'")
        if provider not in {"google_workspace", "m365_defender"}:
            raise ConnectorAuthError(f"Unsupported email_security provider: {provider}")

        self._provider = provider

        if provider == "google_workspace":
            sa_json = tenant_credentials.get("service_account_json")
            admin_email = tenant_credentials.get("admin_email")
            if not sa_json or not admin_email:
                raise ConnectorAuthError("Google Workspace credentials require 'service_account_json' and 'admin_email'")
            self._client = GoogleWorkspaceAPIClient(
                service_account_json=str(sa_json),
                admin_email=str(admin_email),
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("Google Workspace authentication failed")

        elif provider == "m365_defender":
            client_id = tenant_credentials.get("client_id")
            client_secret = tenant_credentials.get("client_secret")
            tenant_id = tenant_credentials.get("tenant_id")
            if not client_id or not client_secret or not tenant_id:
                raise ConnectorAuthError("M365 Defender credentials require 'client_id', 'client_secret', and 'tenant_id'")
            self._client = M365DefenderAPIClient(
                client_id=str(client_id),
                client_secret=str(client_secret),
                tenant_id=str(tenant_id),
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("M365 Defender authentication failed")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"email_security-{provider}",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull email security alerts since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only alerts created after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        since_iso = since.isoformat() if since else None
        findings: list[RawFinding] = []

        try:
            alerts = self._client.list_alerts(since=since_iso)
            for alert in alerts:
                alert["provider"] = self._provider
                alert_id = alert.get("alertId") or alert.get("id") or str(hash(str(alert)))
                findings.append(
                    RawFinding(
                        id=alert_id,
                        source=self.NAME,
                        raw_data=alert,
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            logger.info(
                "Email Security (%s): fetched %d alerts for tenant %s",
                self._provider,
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Email Security fetch_findings failed")
            raise ConnectorFetchError(f"Email Security fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map an Email Security RawFinding to URIPRiskRecord.

        Mappings
        --------
        provider           → source suffix
        alert type         → severity (confirmed phishing/BEC → critical)
        domain             → 'email'
        """
        data = raw.raw_data
        provider = data.get("provider", "unknown")

        if provider == "google_workspace":
            alert_type = data.get("type") or "Unknown"
            native_severity = data.get("severity") or "MEDIUM"
            title = f"Google Workspace Alert: {alert_type}"
            description = f"Alert type: {alert_type}. Source: {data.get('source', 'Gmail security')}"
        elif provider == "m365_defender":
            alert_type = data.get("category") or data.get("title") or "Unknown"
            native_severity = data.get("severity") or "medium"
            title = data.get("title") or f"M365 Defender Alert: {alert_type}"
            description = data.get("description") or f"Category: {alert_type}"
            if data.get("recommendedActions"):
                description += f"\nRecommended actions: {data['recommendedActions']}"
        else:
            alert_type = "Unknown"
            native_severity = "medium"
            title = "Email Security Alert"
            description = "Unknown provider alert"

        sev, cvss = _classify_email_alert(alert_type, native_severity)

        return URIPRiskRecord(
            finding=title,
            description=description,
            source=f"email_security:{provider}",
            domain="email",
            cvss_score=cvss,
            severity=sev,
            asset="Email Infrastructure",
            owner_team="Email Security",
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
