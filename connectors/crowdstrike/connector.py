"""
CrowdStrike Falcon connector for URIP.

Implements the BaseConnector contract for three Falcon products:

  - falcon_spotlight  → Vulnerability Management (CVE + endpoint context)
  - falcon_easm       → External Attack Surface Management (Falcon Surface)
  - falcon_cnapp      → Cloud-Native Application Protection (CSPM/CWPP findings)

Tenants enable a subset via ``credentials['enabled_products']``.

Severity model (ExPRT)
----------------------
CrowdStrike scores every finding on a 0-100 ExPRT scale.  We map to URIP's
4-tier severity ladder as follows:

    >= 80   → critical
    60..79  → high
    30..59  → medium
    < 30    → low

Auth model
----------
OAuth2 client-credentials grant.  The bearer token is acquired up-front during
``authenticate()`` and cached inside ``CrowdStrikeAPIClient`` until it expires
or the API returns 401 (in which case we refresh once and retry).

Multi-region
------------
``base_url`` is configurable to support all four CrowdStrike clouds:
    api.crowdstrike.com          (US-1, default)
    api.us-2.crowdstrike.com     (US-2)
    api.eu-1.crowdstrike.com     (EU-1)
    api.laggar.gcw.crowdstrike.com (GovCloud)
"""

from __future__ import annotations

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
from connectors.crowdstrike.api_client import (
    DEFAULT_BASE_URL,
    VALID_BASE_URLS,
    CrowdStrikeAPIClient,
)
from connectors.crowdstrike.schemas import (
    CNAPPResponse,
    EASMResponse,
    SpotlightEntitiesResponse,
    SpotlightQueryResponse,
)

logger = logging.getLogger(__name__)


SUPPORTED_PRODUCTS_DEFAULT = ["falcon_spotlight", "falcon_easm", "falcon_cnapp"]
DEFAULT_PAGE_SIZE = 100


def exprt_to_severity(score: Optional[int]) -> str:
    """Map CrowdStrike ExPRT 0-100 to URIP severity ladder."""
    if score is None:
        return "medium"
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def asset_criticality_to_tier(tags: list[str]) -> Optional[int]:
    """Pull asset_tier (1–4) from CrowdStrike grouping tags if present."""
    crit_map = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
    for tag in tags or []:
        # Tag shape: "FalconGroupingTags/Criticality:Critical"
        if ":" in tag:
            key, _, val = tag.rpartition(":")
            val = val.strip()
            if val in crit_map:
                return crit_map[val]
    return None


@register_connector("crowdstrike")
class CrowdStrikeConnector(BaseConnector):
    """Live multi-product connector for the CrowdStrike Falcon platform."""

    NAME = "crowdstrike"
    RISK_INDEX_DOMAIN = "attack"

    # ── Tool Catalog metadata ──────────────────────────────────────────────
    DISPLAY_NAME = "CrowdStrike Falcon"
    CATEGORY = "EDR"
    SHORT_DESCRIPTION = (
        "VM (Spotlight), EASM (Surface) and Cloud (CNAPP) findings from CrowdStrike Falcon — "
        "ExPRT-prioritized with hostname/agent/cloud-resource context."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = (
        "https://falcon.us-2.crowdstrike.com/documentation/page/"
        "cb1eaaa1/falcon-platform-api-reference"
    )
    SUPPORTED_PRODUCTS = list(SUPPORTED_PRODUCTS_DEFAULT)
    MODULE_CODE = "EDR"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="client_id", label="API Client ID", type="text", required=True,
            help_text="CrowdStrike Falcon → Support → API Clients and Keys → Add new API client.",
        ),
        CredentialFieldSpec(
            name="client_secret", label="API Client Secret", type="password",
            required=True, secret=True,
            help_text="Shown ONCE on creation — store in vault.",
        ),
        CredentialFieldSpec(
            name="base_url", label="Falcon Cloud", type="select", required=True,
            default=DEFAULT_BASE_URL,
            help_text="Region of your Falcon tenant.",
            options=[
                {"value": "https://api.crowdstrike.com", "label": "US-1"},
                {"value": "https://api.us-2.crowdstrike.com", "label": "US-2"},
                {"value": "https://api.eu-1.crowdstrike.com", "label": "EU-1"},
                {"value": "https://api.laggar.gcw.crowdstrike.com", "label": "GovCloud"},
            ],
        ),
        CredentialFieldSpec(
            name="enabled_products", label="Enabled Products", type="text",
            required=False, default="falcon_spotlight,falcon_easm,falcon_cnapp",
            help_text="Comma-separated subset of {falcon_spotlight, falcon_easm, falcon_cnapp}.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["crowdstrike"]

    # ── Construction ───────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._client: Optional[CrowdStrikeAPIClient] = None
        self._last_run: Optional[datetime] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None
        self._enabled_products: list[str] = list(SUPPORTED_PRODUCTS_DEFAULT)

    # ── Authentication ─────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        client_id = tenant_credentials.get("client_id")
        client_secret = tenant_credentials.get("client_secret")
        base_url = tenant_credentials.get("base_url", DEFAULT_BASE_URL)

        if not client_id:
            raise ConnectorAuthError(
                "CrowdStrike credentials must include 'client_id'"
            )
        if not client_secret:
            raise ConnectorAuthError(
                "CrowdStrike credentials must include 'client_secret'"
            )

        # Best-effort warning for unknown base URLs (don't reject — partner clouds
        # can introduce new ones)
        if base_url not in VALID_BASE_URLS:
            logger.warning(
                "CrowdStrike base_url %s is not in known list %s — proceeding anyway",
                base_url, VALID_BASE_URLS,
            )

        self._client = CrowdStrikeAPIClient(
            client_id=str(client_id),
            client_secret=str(client_secret),
            base_url=str(base_url),
        )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "CrowdStrike OAuth failed — check client_id/client_secret/base_url"
            )

        # Track enabled products
        enabled = tenant_credentials.get("enabled_products")
        if enabled:
            if isinstance(enabled, str):
                enabled = [p.strip() for p in enabled.split(",") if p.strip()]
            self._enabled_products = [
                p for p in enabled if p in SUPPORTED_PRODUCTS_DEFAULT
            ] or list(SUPPORTED_PRODUCTS_DEFAULT)
        else:
            self._enabled_products = list(SUPPORTED_PRODUCTS_DEFAULT)

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"crowdstrike-{str(client_id)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"enabled_products": list(self._enabled_products)},
        )

    # ── Fetch ──────────────────────────────────────────────────────────────

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        findings: list[RawFinding] = []

        try:
            if "falcon_spotlight" in self._enabled_products:
                findings.extend(self._fetch_spotlight(since, tenant_id))
            if "falcon_easm" in self._enabled_products:
                findings.extend(self._fetch_easm(since, tenant_id))
            if "falcon_cnapp" in self._enabled_products:
                findings.extend(self._fetch_cnapp(since, tenant_id))

            self._last_run = datetime.now(timezone.utc)
            logger.info(
                "CrowdStrike: fetched %d findings (products=%s) for tenant %s",
                len(findings), self._enabled_products, tenant_id,
            )
            return findings
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("CrowdStrike fetch_findings failed")
            raise ConnectorFetchError(f"CrowdStrike fetch failed: {exc}") from exc

    def _fetch_spotlight(self, since: datetime, tenant_id: str) -> list[RawFinding]:
        assert self._client is not None
        offset = ""
        out: list[RawFinding] = []
        # Build a CQL-style filter for ``updated_timestamp:>'since'`` if API supports it.
        since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        filter_str = f"updated_timestamp:>'{since_iso}'"

        while True:
            q = self._client.query_spotlight_vulnerabilities(
                offset=offset, limit=DEFAULT_PAGE_SIZE, filter_str=filter_str,
            )
            parsed = SpotlightQueryResponse.model_validate(q)
            ids = parsed.resources

            if ids:
                detail = self._client.get_spotlight_vulnerability_details(ids)
                detail_parsed = SpotlightEntitiesResponse.model_validate(detail)
                for vuln in detail_parsed.resources:
                    out.append(
                        RawFinding(
                            id=vuln.id,
                            source=f"{self.NAME}:falcon_spotlight",
                            raw_data=vuln.model_dump(mode="json"),
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )

            offset = parsed.meta.pagination.offset or ""
            if not offset:
                break

        return out

    def _fetch_easm(self, since: datetime, tenant_id: str) -> list[RawFinding]:
        assert self._client is not None
        offset = ""
        out: list[RawFinding] = []
        while True:
            resp = self._client.query_external_assets(offset=offset, limit=DEFAULT_PAGE_SIZE)
            parsed = EASMResponse.model_validate(resp)
            for asset in parsed.resources:
                out.append(
                    RawFinding(
                        id=asset.id,
                        source=f"{self.NAME}:falcon_easm",
                        raw_data=asset.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )
            offset = parsed.meta.pagination.offset or ""
            if not offset:
                break
        return out

    def _fetch_cnapp(self, since: datetime, tenant_id: str) -> list[RawFinding]:
        assert self._client is not None
        offset = ""
        out: list[RawFinding] = []
        while True:
            resp = self._client.query_cnapp_findings(offset=offset, limit=DEFAULT_PAGE_SIZE)
            parsed = CNAPPResponse.model_validate(resp)
            for finding in parsed.resources:
                out.append(
                    RawFinding(
                        id=finding.id,
                        source=f"{self.NAME}:falcon_cnapp",
                        raw_data=finding.model_dump(mode="json"),
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )
            offset = parsed.meta.pagination.offset or ""
            if not offset:
                break
        return out

    # ── Normalize ──────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        # Choose path by source suffix the connector itself injected.
        if raw.source.endswith(":falcon_spotlight"):
            return self._normalize_spotlight(raw)
        if raw.source.endswith(":falcon_easm"):
            return self._normalize_easm(raw)
        if raw.source.endswith(":falcon_cnapp"):
            return self._normalize_cnapp(raw)
        # Unknown shape → still produce a valid record so the pipeline keeps moving
        return URIPRiskRecord(
            finding="CrowdStrike finding",
            description="Unknown CrowdStrike product shape",
            source=self.NAME,
            domain="endpoint",
            cvss_score=0.0,
            severity="medium",
            asset="unknown",
            owner_team="Endpoint Security",
        )

    def _normalize_spotlight(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        cve = d.get("cve") or {}
        host = d.get("host_info") or {}
        exprt = d.get("exprt_score")
        severity = exprt_to_severity(exprt)
        cve_id = cve.get("id")
        hostname = host.get("hostname") or "unknown-endpoint"
        ip = host.get("local_ip")
        agent_id = host.get("agent_id")
        asset_tier = asset_criticality_to_tier(host.get("tags") or [])

        asset = hostname
        if ip:
            asset = f"{hostname} ({ip})"

        description = cve.get("description") or f"{cve_id or 'Vulnerability'} on {hostname}"
        if agent_id:
            description += f" [agent={agent_id}]"

        return URIPRiskRecord(
            finding=cve_id or "CrowdStrike Spotlight Finding",
            description=description,
            source=raw.source,
            domain="endpoint",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="Vulnerability Management",
            cve_id=cve_id,
            asset_tier=asset_tier,
            exploit_status="active" if (cve.get("exploit_status") or 0) >= 60 else None,
        )

    def _normalize_easm(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        exprt = d.get("exprt_score")
        severity = exprt_to_severity(exprt)
        # EASM may also carry vendor risk_severity — treat as override hint
        risk_sev = (d.get("risk_severity") or "").lower()
        if risk_sev in {"critical", "high", "medium", "low"} and severity == "medium":
            severity = risk_sev

        asset_value = d.get("asset_value") or "unknown"
        exposure = d.get("exposure_type") or "external_exposure"
        return URIPRiskRecord(
            finding=f"External asset exposure: {asset_value}",
            description=f"CrowdStrike Surface flagged {asset_value} ({exposure}).",
            source=raw.source,
            domain="external_attack_surface",
            cvss_score=0.0,
            severity=severity,
            asset=asset_value,
            owner_team="External Attack Surface",
            exploit_status=None,
        )

    def _normalize_cnapp(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        exprt = d.get("exprt_score")
        severity = exprt_to_severity(exprt)
        sev_native = (d.get("severity") or "").lower()
        if sev_native in {"critical", "high", "medium", "low"} and severity == "medium":
            severity = sev_native

        resource = d.get("resource_id") or d.get("title") or "unknown-resource"
        return URIPRiskRecord(
            finding=d.get("title") or "CrowdStrike CNAPP finding",
            description=(
                d.get("description") or
                f"Cloud misconfiguration on {resource} (policy={d.get('policy_id') or 'n/a'})"
            ),
            source=raw.source,
            domain="cloud",
            cvss_score=0.0,
            severity=severity,
            asset=resource,
            owner_team="Cloud Security",
            exploit_status=None,
        )

    # ── Health ─────────────────────────────────────────────────────────────

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
