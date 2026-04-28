"""
CyberArk PAM (Privileged Access) connector for URIP.

Pulls:
- Shared credentials usage events
- Privileged session anomalies
- Vault access logs
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
from connectors.cyberark_pam.api_client import CyberArkAPIClient
from connectors.cyberark_pam.schemas import CyberArkEvent, CyberArkEventsResponse

logger = logging.getLogger(__name__)


def _severity(label: str | None) -> str:
    if not label:
        return "medium"
    label = str(label).lower()
    if label in {"critical", "high", "medium", "low"}:
        return label
    return "low"


@register_connector("cyberark_pam")
class CyberArkPAMConnector(BaseConnector):
    NAME = "cyberark_pam"
    # PAM feeds the Accounts domain bucket but is NOT in one of the 3
    # Cyber Risk Index sub-indexes per task spec (only ms_entra-risky-signins
    # is listed for the attack sub-index in the identity space).
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "CyberArk Privileged Access"
    CATEGORY = "PAM"
    SHORT_DESCRIPTION = "Vault access logs, privileged session anomalies, and shared credential usage."
    STATUS = "live"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "IDENTITY"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url",
            label="PVWA Base URL",
            type="url",
            required=True,
            placeholder="https://pvwa.example",
            help_text="CyberArk PVWA root URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_key",
            label="API Key",
            type="password",
            required=True,
            secret=True,
            placeholder="cak_***",
            help_text="API key used for APIKey/Logon. Ensure read permissions for audit feeds.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["cyberark_pam"]

    def __init__(self) -> None:
        self._client: CyberArkAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        base_url = tenant_credentials.get("base_url")
        api_key = tenant_credentials.get("api_key")
        if not base_url or not api_key:
            raise ConnectorAuthError(
                "CyberArk credentials must include 'base_url' and 'api_key'"
            )

        transport = tenant_credentials.get("_transport")
        self._client = CyberArkAPIClient(
            base_url=str(base_url),
            api_key=str(api_key),
            transport=transport,
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError("CyberArk authentication failed: invalid API key or URL")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"cyberark-apikey-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError("Connector not authenticated. Call authenticate() first.")

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            with self._client.session():
                vault = CyberArkEventsResponse.model_validate(self._client.list_vault_access())
                sessions = CyberArkEventsResponse.model_validate(self._client.list_privileged_sessions())
                usage = CyberArkEventsResponse.model_validate(self._client.list_credentials_usage())

                def _emit(record_type: str, event_dict: dict[str, Any]):
                    event = CyberArkEvent.model_validate(event_dict)
                    findings.append(
                        RawFinding(
                            id=event.id,
                            source=self.NAME,
                            raw_data={"record_type": record_type, "event": event.model_dump(mode="json")},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

                for e in vault.data:
                    _emit("vault_access", e)
                for e in sessions.data:
                    _emit("session_anomaly", e)
                for e in usage.data:
                    _emit("credential_usage", e)

            self._last_run = datetime.now(timezone.utc)
            if not findings:
                return []
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("CyberArk fetch_findings failed")
            raise ConnectorFetchError(f"CyberArk fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        try:
            record_type = raw.raw_data.get("record_type")
            if record_type not in {"vault_access", "session_anomaly", "credential_usage"}:
                raise ConnectorNormalizeError(f"Unsupported CyberArk record_type: {record_type}")

            event = CyberArkEvent.model_validate(raw.raw_data.get("event") or {})
            severity = _severity(event.severity)
            asset = event.asset or "unknown"
            user = event.user or "unknown"
            description = event.message or f"CyberArk event {event.event_type} by {user}"
            finding = {
                "vault_access": "Vault Access",
                "session_anomaly": "Privileged Session Anomaly",
                "credential_usage": "Shared Credential Usage",
            }[record_type]

            return URIPRiskRecord(
                finding=finding,
                source=self.NAME,
                domain="identity",
                cvss_score=0.0,
                severity=severity,
                asset=asset,
                owner_team="Identity & Access",
                description=description,
            )

        except ConnectorNormalizeError:
            raise
        except Exception as exc:
            raise ConnectorNormalizeError(f"CyberArk normalize failed: {exc}") from exc

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

