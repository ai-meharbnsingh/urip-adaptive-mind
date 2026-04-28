"""
SentinelOne Singularity connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates ApiToken via /system/info
  fetch_findings → pulls threats (cursor pagination) + agents for endpoint context
  normalize      → maps SentinelOne threat → URIPRiskRecord
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
from connectors.sentinelone.api_client import SentinelOneAPIClient
from connectors.sentinelone.schemas import (
    SentinelOneAgent,
    SentinelOneAgentsResponse,
    SentinelOneThreat,
    SentinelOneThreatsResponse,
)

logger = logging.getLogger(__name__)

# Map SentinelOne classification to URIP domain (all endpoint for now)
CLASSIFICATION_DOMAIN_MAP = {
    "Malware": "endpoint",
    "Exploit": "endpoint",
    "PUP": "endpoint",
    "Ransomware": "endpoint",
    "Trojan": "endpoint",
    "Spyware": "endpoint",
    "Adware": "endpoint",
    "Rootkit": "endpoint",
    "HackTool": "endpoint",
    "Behavioral": "endpoint",
    "Inbound MTA": "network",
    "Cloud": "cloud",
}

# Classifications that imply critical severity
CRITICAL_CLASSIFICATIONS = {"Ransomware", "Exploit", "Rootkit"}


@register_connector("sentinelone")
class SentinelOneConnector(BaseConnector):
    """
    Live connector for SentinelOne Singularity.

    Data flow
    ---------
    1. Authenticate with ApiToken + base URL.
    2. Fetch threats since `since` (cursor pagination).
    3. Fetch agents (cursor pagination) for endpoint-health context.
    4. Normalize both threat and agent findings to URIPRiskRecord.
    """

    NAME = "sentinelone"
    RISK_INDEX_DOMAIN = "attack"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "SentinelOne Singularity"
    CATEGORY = "EDR"
    SHORT_DESCRIPTION = (
        "Endpoint telemetry, threat detections, agent health, IoC matches."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://usea1-partners.sentinelone.net/api-doc/overview"
    SUPPORTED_PRODUCTS = None
    MODULE_CODE = "EDR"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="base_url", label="Console URL", type="url",
            required=True,
            placeholder="https://usea1-xxxx.sentinelone.net",
            help_text="Your SentinelOne console root URL.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="api_token", label="API Token", type="password",
            required=True, secret=True,
            placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…",
            help_text="Settings → Users → Service Users → generate API token (read-only is enough).",
        ),
        CredentialFieldSpec(
            name="max_requests_per_minute", label="Max requests / min",
            type="number", required=False, default=200,
            help_text="SentinelOne enforces 200 req/min per token by default.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["sentinelone"]

    def __init__(self) -> None:
        self._client: SentinelOneAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate SentinelOne API token.

        Required credential keys:
            - api_token  (or sentinelone_api_token)
            - base_url   (or sentinelone_base_url), e.g. https://tenant.sentinelone.net
        Optional:
            - tenant_id
        """
        api_token = (
            tenant_credentials.get("api_token")
            or tenant_credentials.get("sentinelone_api_token")
        )
        base_url = (
            tenant_credentials.get("base_url")
            or tenant_credentials.get("sentinelone_base_url")
        )

        if not api_token:
            raise ConnectorAuthError(
                "SentinelOne credentials must include 'api_token'"
            )
        if not base_url:
            raise ConnectorAuthError(
                "SentinelOne credentials must include 'base_url'"
            )

        max_requests_per_minute = tenant_credentials.get(
            "max_requests_per_minute", 200
        )
        self._client = SentinelOneAPIClient(
            api_token=str(api_token),
            base_url=str(base_url),
            max_requests_per_minute=int(max_requests_per_minute),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "SentinelOne authentication failed: invalid API token or URL"
            )

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"s1-token-{str(api_token)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull threats and agent health findings since `since`.

        Parameters
        ----------
        since : datetime
            Fetch threats created after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        max_threats : int, optional
            Cap threat volume per tick (default 200).
        max_agents : int, optional
            Cap agent volume per tick (default 50).
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        max_threats: int = kwargs.get("max_threats", 200)
        max_agents: int = kwargs.get("max_agents", 50)
        findings: list[RawFinding] = []

        try:
            # ── Threats (cursor pagination) ─────────────────────────────
            since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            cursor: str | None = None
            threats_fetched = 0

            while threats_fetched < max_threats:
                limit = min(100, max_threats - threats_fetched)
                resp = self._client.list_threats(
                    since=since_iso, limit=limit, cursor=cursor
                )
                threats_data = SentinelOneThreatsResponse.model_validate(resp)

                for threat in threats_data.data:
                    findings.append(
                        RawFinding(
                            id=threat.id,
                            source=self.NAME,
                            raw_data=threat.model_dump(mode="json"),
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                    threats_fetched += 1

                cursor = threats_data.pagination.next_cursor
                if not cursor:
                    break

            # ── Agents (cursor pagination) ──────────────────────────────
            # We pull agents to surface endpoint-health gaps (inactive agents,
            # missing agents, etc.).  In production this can be enriched with
            # SentinelOne's vulnerabilities module if licensed.
            cursor = None
            agents_fetched = 0

            while agents_fetched < max_agents:
                limit = min(100, max_agents - agents_fetched)
                resp = self._client.list_agents(limit=limit, cursor=cursor)
                agents_data = SentinelOneAgentsResponse.model_validate(resp)

                for agent in agents_data.data:
                    # Flag inactive agents as a finding
                    if not agent.is_active:
                        findings.append(
                            RawFinding(
                                id=f"agent:{agent.id}",
                                source=self.NAME,
                                raw_data={
                                    "agent_id": agent.id,
                                    "agent_name": agent.computer_name,
                                    "agent_os": agent.os_name,
                                    "classification": "Inactive Agent",
                                    "mitigated_status": "not_mitigated",
                                    "is_agent_finding": True,
                                },
                                fetched_at=datetime.now(timezone.utc),
                                tenant_id=tenant_id,
                            )
                        )
                    agents_fetched += 1

                cursor = agents_data.pagination.next_cursor
                if not cursor:
                    break

            logger.info(
                "SentinelOne: fetched %d findings for tenant %s",
                len(findings),
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("SentinelOne fetch_findings failed")
            raise ConnectorFetchError(f"SentinelOne fetch failed: {exc}") from exc

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a SentinelOne RawFinding to URIPRiskRecord.

        Handles two shapes:
          1. Threat findings (from /threats)
          2. Agent-health findings (inactive agents)
        """
        data = raw.raw_data
        is_agent_finding = data.get("is_agent_finding", False)

        if is_agent_finding:
            return self._normalize_agent(data)

        threat = SentinelOneThreat.model_validate(data)

        domain = CLASSIFICATION_DOMAIN_MAP.get(
            threat.classification or "", "endpoint"
        )

        # Derive severity from classification
        classification = threat.classification or "Threat"
        if classification in CRITICAL_CLASSIFICATIONS:
            severity = "critical"
        elif classification in ("Malware", "Trojan", "Spyware"):
            severity = "high"
        elif classification in ("PUP", "Adware", "HackTool"):
            severity = "medium"
        else:
            severity = "medium"

        asset = threat.agent_name or "unknown-endpoint"

        description = (
            f"SentinelOne {classification} detected on {asset}. "
            f"Threat: {threat.threat_info.threat_name or 'Unknown'}. "
            f"Status: {threat.mitigated_status or 'active'}."
        )
        if threat.file_display_name:
            description += f" File: {threat.file_display_name}."

        # If mitigated, don't flag as actively exploited
        exploit_status = (
            None
            if threat.mitigated_status == "mitigated"
            else "active"
        )

        return URIPRiskRecord(
            finding=threat.threat_info.threat_name or f"{classification} Threat",
            description=description,
            source=self.NAME,
            domain=domain,
            cvss_score=0.0,  # SentinelOne threats don't carry CVSS natively
            severity=severity,
            asset=asset,
            owner_team="Endpoint Security",
            cve_id=None,
            exploit_status=exploit_status,
        )

    def _normalize_agent(self, data: dict[str, Any]) -> URIPRiskRecord:
        """Normalize an inactive-agent finding."""
        agent_name = data.get("agent_name", "unknown")
        agent_os = data.get("agent_os", "unknown")

        return URIPRiskRecord(
            finding=f"Inactive SentinelOne Agent: {agent_name}",
            description=(
                f"SentinelOne agent {agent_name} ({agent_os}) is inactive "
                f"or unresponsive. Endpoint may be unprotected."
            ),
            source=self.NAME,
            domain="endpoint",
            cvss_score=5.0,
            severity="medium",
            asset=agent_name,
            owner_team="Endpoint Security",
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
