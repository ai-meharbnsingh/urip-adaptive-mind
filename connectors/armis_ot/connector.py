"""
Armis OT (Operational Technology) connector for URIP.

Pulls:
- OT asset inventory
- Vulnerabilities (CVEs / CVSS)
- Risk events (unsafe protocol, anomalous behavior, etc.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from connectors.armis_ot.api_client import ArmisOTAPIClient
from connectors.armis_ot.schemas import ArmisAsset, ArmisListResponse, ArmisRiskEvent, ArmisVulnerability
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

logger = logging.getLogger(__name__)


def _severity_from_label(label: str | None) -> str:
    if not label:
        return "medium"
    label = str(label).lower()
    if label in {"critical", "high", "medium", "low"}:
        return label
    if label in {"sev1", "p1"}:
        return "critical"
    if label in {"sev2", "p2"}:
        return "high"
    if label in {"sev3", "p3"}:
        return "medium"
    return "low"


@register_connector("armis_ot")
class ArmisOTConnector(BaseConnector):
    NAME = "armis_ot"
    # OT is its own category — not part of the 3 Cyber Risk Index sub-indexes.
    RISK_INDEX_DOMAIN = None

    DISPLAY_NAME = "Armis OT"
    CATEGORY = "OT"
    SHORT_DESCRIPTION = "OT asset inventory, vulnerabilities, and risk events for industrial devices."
    STATUS = "live"
    VENDOR_DOCS_URL = None
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "OT"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url",
            label="Armis API Base URL",
            type="url",
            required=True,
            placeholder="https://api.armis.example",
            help_text="Armis cloud API base URL for your tenant.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_token",
            label="API Token",
            type="password",
            required=True,
            secret=True,
            placeholder="armis_***",
            help_text="Armis API token with read permissions for assets/vulnerabilities/events.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["armis_ot"]

    def __init__(self) -> None:
        self._client: ArmisOTAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        base_url = tenant_credentials.get("base_url")
        api_token = tenant_credentials.get("api_token") or tenant_credentials.get("token")
        if not base_url or not api_token:
            raise ConnectorAuthError(
                "Armis OT credentials must include 'base_url' and 'api_token'"
            )

        transport = tenant_credentials.get("_transport")
        self._client = ArmisOTAPIClient(
            base_url=str(base_url),
            api_token=str(api_token),
            transport=transport,
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError("Armis OT authentication failed: invalid token or URL")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"armis-token-{str(api_token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError("Connector not authenticated. Call authenticate() first.")

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            assets_raw = ArmisListResponse.model_validate(self._client.list_assets())
            vulns_raw = ArmisListResponse.model_validate(self._client.list_vulnerabilities())
            events_raw = ArmisListResponse.model_validate(self._client.list_risk_events())

            assets: list[ArmisAsset] = [
                ArmisAsset.model_validate(a) for a in assets_raw.data
            ]
            assets_by_id = {a.id: a for a in assets}

            for asset in assets:
                findings.append(
                    RawFinding(
                        id=asset.id,
                        source=self.NAME,
                        raw_data={
                            "record_type": "asset",
                            "asset": asset.model_dump(mode="json"),
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            for v in vulns_raw.data:
                vuln = ArmisVulnerability.model_validate(v)
                asset = assets_by_id.get(vuln.asset_id)
                findings.append(
                    RawFinding(
                        id=vuln.id,
                        source=self.NAME,
                        raw_data={
                            "record_type": "vulnerability",
                            "vulnerability": vuln.model_dump(mode="json"),
                            "asset": asset.model_dump(mode="json") if asset else None,
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            for e in events_raw.data:
                event = ArmisRiskEvent.model_validate(e)
                asset = assets_by_id.get(event.asset_id)
                findings.append(
                    RawFinding(
                        id=event.id,
                        source=self.NAME,
                        raw_data={
                            "record_type": "risk_event",
                            "risk_event": event.model_dump(mode="json"),
                            "asset": asset.model_dump(mode="json") if asset else None,
                        },
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            # Baseline incremental: `since` is accepted for future server-side filters,
            # but we do not rely on it in the RE baseline.
            self._last_run = datetime.now(timezone.utc)

            # The test suite expects [] when the vendor returns empty lists.
            if not assets and not vulns_raw.data and not events_raw.data:
                return []
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("Armis OT fetch_findings failed")
            raise ConnectorFetchError(f"Armis OT fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        try:
            record_type = raw.raw_data.get("record_type")
            if record_type == "asset":
                asset = ArmisAsset.model_validate(raw.raw_data.get("asset") or {})
                sev = "low"
                if asset.criticality is not None and int(asset.criticality) >= 4:
                    sev = "medium"
                asset_name = asset.name or asset.ip or asset.mac or asset.id
                return URIPRiskRecord(
                    finding="OT Asset Inventory",
                    source=self.NAME,
                    domain="ot",
                    cvss_score=0.0,
                    severity=sev,
                    asset=asset_name,
                    owner_team="OT Security",
                    description=f"Discovered OT asset {asset_name} at site {asset.site or 'unknown'}.",
                )

            if record_type == "vulnerability":
                vuln = ArmisVulnerability.model_validate(raw.raw_data.get("vulnerability") or {})
                asset_payload = raw.raw_data.get("asset") or {}
                asset = ArmisAsset.model_validate(asset_payload) if asset_payload else None
                asset_name = (
                    (asset.name if asset else None)
                    or (asset.ip if asset else None)
                    or vuln.asset_id
                )
                cvss = float(vuln.cvss or 0.0)
                severity = _severity_from_label(vuln.severity)
                description = f"Armis vulnerability {vuln.id} on {asset_name}: {vuln.title}."
                if vuln.cve:
                    description += f" CVE: {vuln.cve}."
                return URIPRiskRecord(
                    finding=vuln.title,
                    source=self.NAME,
                    domain="ot",
                    cvss_score=cvss,
                    severity=severity,
                    asset=asset_name,
                    owner_team="OT Security",
                    description=description,
                    cve_id=vuln.cve,
                )

            if record_type == "risk_event":
                event = ArmisRiskEvent.model_validate(raw.raw_data.get("risk_event") or {})
                asset_payload = raw.raw_data.get("asset") or {}
                asset = ArmisAsset.model_validate(asset_payload) if asset_payload else None
                asset_name = (
                    (asset.name if asset else None)
                    or (asset.ip if asset else None)
                    or event.asset_id
                )
                severity = _severity_from_label(event.risk_level)
                description = event.message or f"Armis OT risk event {event.event_type}"
                return URIPRiskRecord(
                    finding=f"OT Risk Event: {event.event_type}",
                    source=self.NAME,
                    domain="ot",
                    cvss_score=0.0,
                    severity=severity,
                    asset=asset_name,
                    owner_team="OT Security",
                    description=description,
                )

            raise ConnectorNormalizeError(f"Unsupported Armis OT record_type: {record_type}")

        except ConnectorNormalizeError:
            raise
        except Exception as exc:
            raise ConnectorNormalizeError(f"Armis OT normalize failed: {exc}") from exc

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

