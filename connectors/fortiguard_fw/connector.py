"""
Fortinet Fortiguard firewall connector for URIP.

Supports:
- Syslog ingest: CEF parser for firewall / IPS events
- Optional REST API fetch: blocked threats (baseline)
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
from connectors.fortiguard_fw.api_client import FortiGuardAPIClient, parse_cef_line
from connectors.fortiguard_fw.schemas import CEFEvent, FortiBlockedThreat, FortiBlockedThreatsResponse

logger = logging.getLogger(__name__)


def _severity_from_cef(sev: int) -> str:
    if sev >= 9:
        return "critical"
    if sev >= 7:
        return "high"
    if sev >= 4:
        return "medium"
    return "low"


def _severity_from_label(label: str | None) -> str:
    if not label:
        return "medium"
    label = str(label).lower()
    if label in {"critical", "high", "medium", "low"}:
        return label
    return "low"


@register_connector("fortiguard_fw")
class FortiguardFirewallConnector(BaseConnector):
    NAME = "fortiguard_fw"
    RISK_INDEX_DOMAIN = "security_config"

    DISPLAY_NAME = "Fortinet Fortiguard"
    CATEGORY = "FIREWALL"
    SHORT_DESCRIPTION = "Parses CEF syslog for blocked threats/IPS events and optionally fetches REST blocked threats."
    STATUS = "live"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = ["FortiGate", "FortiAnalyzer (optional)"]
    MODULE_CODE = "NETWORK"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="ingest_mode",
            label="Ingest Mode",
            type="select",
            required=True,
            default="syslog",
            options=[
                {"value": "syslog", "label": "Syslog (CEF)"},
                {"value": "api", "label": "REST API (FortiGate)"},
            ],
            help_text="Use syslog when a SIEM/collector forwards Fortinet CEF logs. Use API for blocked-threat polling.",
        ),
        CredentialFieldSpec(
            name="base_url",
            label="FortiGate Base URL (API mode)",
            type="url",
            required=False,
            placeholder="https://fortigate.example",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token (API mode)",
            type="password",
            required=False,
            secret=True,
            help_text="Required when ingest_mode=api.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["fortiguard_fw"]

    def __init__(self) -> None:
        self._client: FortiGuardAPIClient | None = None
        self._ingest_mode: str | None = None
        self._authenticated: bool = False
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        ingest_mode = tenant_credentials.get("ingest_mode", "syslog")
        if ingest_mode not in {"syslog", "api"}:
            raise ConnectorAuthError("ingest_mode must be one of: 'syslog', 'api'")
        self._ingest_mode = str(ingest_mode)

        if self._ingest_mode == "syslog":
            self._authenticated = True
            return ConnectorSession(
                connector_name=self.NAME,
                tenant_id=tenant_credentials.get("tenant_id", "unknown"),
                token="fortinet-syslog",
                expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
                extra={"ingest_mode": "syslog"},
            )

        base_url = tenant_credentials.get("base_url")
        api_token = tenant_credentials.get("api_token")
        if not base_url or not api_token:
            raise ConnectorAuthError("API mode requires 'base_url' and 'api_token'")

        transport = tenant_credentials.get("_transport")
        self._client = FortiGuardAPIClient(
            base_url=str(base_url),
            api_token=str(api_token),
            transport=transport,
        )
        if not self._client.validate_auth():
            raise ConnectorAuthError("Fortinet authentication failed: invalid token or URL")
        self._authenticated = True
        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"fortinet-token-{str(api_token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"ingest_mode": "api"},
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if not self._authenticated or not self._ingest_mode:
            raise ConnectorFetchError("Connector not authenticated. Call authenticate() first.")

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            if self._ingest_mode == "syslog":
                lines: list[str] = kwargs.get("syslog_lines", []) or []
                for line in lines:
                    parsed = parse_cef_line(line)
                    if not parsed:
                        continue
                    event = CEFEvent.model_validate(parsed)
                    findings.append(
                        RawFinding(
                            id=f"cef:{event.signature_id}",
                            source=self.NAME,
                            raw_data={"record_type": "cef", "event": event.model_dump(mode="json")},
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                self._last_run = datetime.now(timezone.utc)
                return findings

            if self._client is None:
                raise ConnectorFetchError("API client not initialized for api ingest_mode")
            resp = FortiBlockedThreatsResponse.model_validate(self._client.list_blocked_threats())
            for t in resp.results:
                threat = FortiBlockedThreat.model_validate(t)
                findings.append(
                    RawFinding(
                        id=threat.id,
                        source=self.NAME,
                        raw_data={"record_type": "blocked_threat", "threat": threat.model_dump(mode="json")},
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Fortinet fetch_findings failed")
            raise ConnectorFetchError(f"Fortinet fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        try:
            record_type = raw.raw_data.get("record_type")
            if record_type == "cef":
                event = CEFEvent.model_validate(raw.raw_data.get("event") or {})
                sev = _severity_from_cef(int(event.severity or 0))
                src = event.extensions.get("src") or "unknown"
                dst = event.extensions.get("dst")
                action = event.extensions.get("act")
                category = event.extensions.get("cat")
                desc = f"Fortinet CEF {event.name} ({event.signature_id})"
                if category:
                    desc += f" category={category}."
                if action:
                    desc += f" action={action}."
                if dst:
                    desc += f" dst={dst}."
                return URIPRiskRecord(
                    finding=event.name,
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity=sev,
                    asset=str(src),
                    owner_team="Network Security",
                    description=desc,
                )

            if record_type == "blocked_threat":
                threat = FortiBlockedThreat.model_validate(raw.raw_data.get("threat") or {})
                sev = _severity_from_label(threat.severity)
                asset = threat.srcip or threat.id
                desc = "Fortinet blocked threat"
                if threat.dstip:
                    desc += f" dst={threat.dstip}."
                if threat.action:
                    desc += f" action={threat.action}."
                return URIPRiskRecord(
                    finding="Blocked Threat",
                    source=self.NAME,
                    domain="network",
                    cvss_score=0.0,
                    severity=sev,
                    asset=str(asset),
                    owner_team="Network Security",
                    description=desc,
                )

            raise ConnectorNormalizeError(f"Unsupported Fortinet record_type: {record_type}")

        except ConnectorNormalizeError:
            raise
        except Exception as exc:
            raise ConnectorNormalizeError(f"Fortinet normalize failed: {exc}") from exc

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

