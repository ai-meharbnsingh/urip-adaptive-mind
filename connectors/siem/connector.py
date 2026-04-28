"""
Generic SIEM/SoC connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates per-adapter credentials
  fetch_findings → runs tenant-configured search, returns events
  normalize      → maps SIEM event → URIPRiskRecord
  health_check   → returns operational status

Sub-adapters:
  - Splunk:  /services/search/jobs/export
  - Elastic: /_search with query DSL
  - QRadar:  /api/ariel/searches
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
from connectors.siem.api_client import ElasticAPIClient, QRadarAPIClient, SplunkAPIClient

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "critical": ("critical", 9.0),
    "high": ("high", 7.5),
    "medium": ("medium", 5.0),
    "low": ("low", 3.0),
}


def _map_severity(native: str) -> tuple[str, float]:
    native_lower = (native or "").lower().strip()
    return SEVERITY_MAP.get(native_lower, ("medium", 5.0))


@register_connector("siem")
class SiemConnector(BaseConnector):
    """
    Live connector for Generic SIEM/SoC (Splunk + Elastic + QRadar).

    Data flow
    ---------
    1. authenticate → detect siem_type and validate credentials.
    2. fetch_findings → run saved search / query DSL / Ariel query.
    3. normalize → map each event to URIPRiskRecord.
    """

    NAME = "siem"
    RISK_INDEX_DOMAIN = "attack"

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["siem"]
    DISPLAY_NAME = "Generic SIEM / SoC"
    # CATEGORY must be in CONNECTOR_CATEGORIES (connectors/base/connector.py).
    # SIEM/SOC alerts ship under the SOC bucket in the Tool Catalog filter.
    CATEGORY = "SOC"
    SHORT_DESCRIPTION = (
        "Unified connector for Splunk, Elastic, and IBM QRadar security alerts."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.splunk.com/Documentation/Splunk"
    SUPPORTED_PRODUCTS = ["Splunk Enterprise", "Splunk Cloud", "Elastic Security", "IBM QRadar SIEM"]
    MODULE_CODE = "SOC"
    CREDENTIAL_FIELDS: list[CredentialFieldSpec] = [
        CredentialFieldSpec(
            name="siem_type",
            label="SIEM type",
            type="select",
            required=True,
            options=[
                {"value": "splunk", "label": "Splunk Enterprise / Cloud"},
                {"value": "elastic", "label": "Elastic Security"},
                {"value": "qradar", "label": "IBM QRadar"},
            ],
        ),
        CredentialFieldSpec(name="base_url", label="Base URL", type="url", required=True),
        CredentialFieldSpec(name="auth_token", label="Auth token / HEC token", type="password", required=True, secret=True),
        CredentialFieldSpec(name="search_query", label="Search query (optional)", type="text", required=False),
    ]

    def __init__(self) -> None:
        self._client: SplunkAPIClient | ElasticAPIClient | QRadarAPIClient | None = None
        self._siem_type: str = ""
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate SIEM credentials based on siem_type.

        Required credential keys:
            - siem_type  (splunk | elastic | qradar)
            - base_url
        Per-adapter:
            - Splunk: token OR (username + password)
            - Elastic: api_key
            - QRadar: sec_token
        Optional:
            - tenant_id
        """
        siem_type = (tenant_credentials.get("siem_type") or "").lower()
        if not siem_type:
            raise ConnectorAuthError("SIEM credentials must include 'siem_type'")
        if siem_type not in {"splunk", "elastic", "qradar"}:
            raise ConnectorAuthError(f"Unsupported siem_type: {siem_type}")

        base_url = tenant_credentials.get("base_url")
        if not base_url:
            raise ConnectorAuthError("SIEM credentials must include 'base_url'")

        self._siem_type = siem_type

        if siem_type == "splunk":
            token = tenant_credentials.get("token")
            username = tenant_credentials.get("username")
            password = tenant_credentials.get("password")
            if not token and not (username and password):
                raise ConnectorAuthError("Splunk credentials require 'token' or 'username+password'")
            self._client = SplunkAPIClient(
                base_url=str(base_url),
                auth_token=token,
                username=username,
                password=password,
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("Splunk authentication failed")

        elif siem_type == "elastic":
            api_key = tenant_credentials.get("api_key")
            if not api_key:
                raise ConnectorAuthError("Elastic credentials require 'api_key'")
            self._client = ElasticAPIClient(
                base_url=str(base_url),
                api_key=str(api_key),
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("Elastic authentication failed")

        elif siem_type == "qradar":
            sec_token = tenant_credentials.get("sec_token")
            if not sec_token:
                raise ConnectorAuthError("QRadar credentials require 'sec_token'")
            self._client = QRadarAPIClient(
                base_url=str(base_url),
                sec_token=str(sec_token),
            )
            if not self._client.validate_auth():
                raise ConnectorAuthError("QRadar authentication failed")

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"siem-{siem_type}",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull new/updated SIEM events since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only events after this timestamp.
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
            if self._siem_type == "splunk":
                saved_search = kwargs.get("saved_search") or "security_alerts_last_15m"
                query = f'| savedsearch "{saved_search}"'
                events = self._client.search(query)
                for ev in events:
                    ev["siem_type"] = "splunk"
                    findings.append(
                        RawFinding(
                            id=ev.get("event_id") or ev.get("_cd") or str(hash(str(ev))),
                            source=self.NAME,
                            raw_data=ev,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            elif self._siem_type == "elastic":
                query_dsl_str = kwargs.get("query_dsl") or '{"query": {"match_all": {}}, "size": 100}'
                query_dsl = __import__("json").loads(query_dsl_str)
                hits = self._client.search(query_dsl)
                for hit in hits:
                    hit["siem_type"] = "elastic"
                    findings.append(
                        RawFinding(
                            id=hit.get("_id") or str(hash(str(hit))),
                            source=self.NAME,
                            raw_data=hit,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            elif self._siem_type == "qradar":
                ariel_query = kwargs.get("ariel_query") or "SELECT * FROM events LAST 15 MINUTES"
                events = self._client.search(ariel_query)
                for ev in events:
                    ev["siem_type"] = "qradar"
                    findings.append(
                        RawFinding(
                            id=ev.get("id") or str(hash(str(ev))),
                            source=self.NAME,
                            raw_data=ev,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            logger.info(
                "SIEM (%s): fetched %d findings for tenant %s",
                self._siem_type,
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("SIEM fetch_findings failed")
            raise ConnectorFetchError(f"SIEM fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a SIEM RawFinding to URIPRiskRecord.

        Mappings
        --------
        siem_type          → source suffix
        severity label     → severity + cvss_score
        domain_hint        → domain (network/endpoint/identity/application)
        """
        data = raw.raw_data
        siem_type = data.get("siem_type", "unknown")

        # Extract severity
        severity_label = "medium"
        if siem_type == "splunk":
            severity_label = data.get("severity") or "medium"
        elif siem_type == "elastic":
            src = data.get("_source", {})
            severity_label = src.get("severity_label") or src.get("event.severity") or "medium"
            if isinstance(severity_label, int):
                severity_label = {4: "critical", 3: "high", 2: "medium", 1: "low"}.get(severity_label, "medium")
        elif siem_type == "qradar":
            sev_num = data.get("severity")
            if isinstance(sev_num, int):
                if sev_num >= 9:
                    severity_label = "critical"
                elif sev_num >= 7:
                    severity_label = "high"
                elif sev_num >= 4:
                    severity_label = "medium"
                else:
                    severity_label = "low"

        sev, cvss = _map_severity(severity_label)

        # Extract domain hint
        domain = "network"
        if siem_type == "splunk":
            domain = data.get("domain_hint") or "network"
        elif siem_type == "elastic":
            domain = data.get("_source", {}).get("domain_hint") or "network"
        elif siem_type == "qradar":
            domain = data.get("domain_hint") or "network"

        # Extract message / description
        message = ""
        if siem_type == "splunk":
            message = data.get("message") or "Splunk security alert"
        elif siem_type == "elastic":
            message = data.get("_source", {}).get("message") or "Elastic security alert"
        elif siem_type == "qradar":
            message = data.get("message") or data.get("eventname") or "QRadar security alert"

        # Extract asset
        asset = "unknown"
        if siem_type == "splunk":
            asset = data.get("host") or "unknown"
        elif siem_type == "elastic":
            asset = data.get("_source", {}).get("host.name") or "unknown"
        elif siem_type == "qradar":
            asset = data.get("sourceip") or "unknown"

        return URIPRiskRecord(
            finding=message,
            description=f"SIEM ({siem_type}) alert: {message}",
            source=f"siem:{siem_type}",
            domain=domain,
            cvss_score=cvss,
            severity=sev,
            asset=asset,
            owner_team="SoC",
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
