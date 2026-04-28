"""
Generic EASM (External Attack Surface Management) connector for URIP.

One connector class fronts THREE provider sub-adapters:

  - censys     → search.censys.io API v2     (Bearer token; certs/hosts/services)
  - shodan     → api.shodan.io               (API key in query string; ports/banners/vulns)
  - detectify  → api.detectify.com/rest/v3   (Bearer token; web vuln scan results)

Tenant credentials select EXACTLY ONE provider via
``credentials['easm_provider']``.  The connector also requires a SCOPE list
(``monitor_domains`` / ``monitor_ips`` / ``monitor_asns``) so we never pull
"the entire internet" — we only query the assets the customer told us to
watch.

Severity model
--------------
EASM findings rarely carry a CVSS, so we derive severity from semantic
signals:

  active exploit / confirmed exposure       → critical
  exposed admin interface (login/console)   → high
  exposed dev / staging asset               → medium
  exposed RFC1918 / internal-only port      → low

Per-provider native ``severity`` fields (e.g. Detectify's "critical") override
this when present and unambiguous.
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
from connectors.easm.api_client import (
    CENSYS_DEFAULT_BASE,
    DETECTIFY_DEFAULT_BASE,
    SHODAN_DEFAULT_BASE,
    CensysClient,
    DetectifyClient,
    ShodanClient,
)
from connectors.easm.schemas import (
    CensysSearchResponse,
    DetectifyFindingsResponse,
    ShodanHostResponse,
)

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("censys", "shodan", "detectify")

# Markers that suggest a host/service is publicly exposed for admin use
ADMIN_INTERFACE_HINTS = (
    "admin", "console", "login", "phpmyadmin", "kibana", "grafana",
    "jenkins", "wp-admin", "manage",
)

# Hostname/asset markers that suggest pre-prod (lower severity)
DEV_STAGING_HINTS = ("dev.", "staging.", "stg.", "test.", "qa.", "uat.")

# Internal/RFC1918 IP prefixes — exposure of an internal-only port is low
INTERNAL_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.",
                        "172.24.", "172.25.", "172.26.", "172.27.",
                        "172.28.", "172.29.", "172.30.", "172.31.",
                        "192.168.")


def _classify_severity(provider: str, data: dict[str, Any]) -> str:
    # 1. Confirmed exploit / active exposure → critical
    if data.get("active_exploit") is True:
        return "critical"
    if data.get("confirmed") is True and (data.get("severity") or "").lower() in {
        "critical", "high"
    }:
        return "critical"

    # 2. Native critical severity from provider
    sev = (data.get("severity") or "").lower()
    if sev in {"critical"}:
        return "critical"

    # Provider-specific signal extraction
    if provider == "censys":
        risk = (data.get("risk") or {}).get("severity", "").lower()
        services = data.get("services") or []
        for svc in services:
            ext = (svc.get("extended_service_name") or "")
            sname = (svc.get("service_name") or "")
            blob = f"{ext} {sname}".lower()
            if any(hint in blob for hint in ADMIN_INTERFACE_HINTS):
                return "high"
        host = (data.get("name") or "").lower()
        if any(h in host for h in DEV_STAGING_HINTS):
            return "medium"
        if risk in {"critical", "high"}:
            return risk
        if risk == "medium":
            return "medium"
        return "low"

    if provider == "shodan":
        ip = data.get("ip_str", "")
        if any(ip.startswith(pfx) for pfx in INTERNAL_IP_PREFIXES):
            return "low"
        for banner in data.get("data") or []:
            http = banner.get("http") or {}
            title = (http.get("title") or "").lower()
            product = (banner.get("product") or "").lower()
            blob = f"{title} {product}"
            if any(hint in blob for hint in ADMIN_INTERFACE_HINTS):
                return "high"
        if data.get("vulns"):
            return "high"
        return "low"

    if provider == "detectify":
        if sev in {"critical", "high", "medium", "low"}:
            return sev
        return "medium"

    return "medium"


def _extract_asset(provider: str, data: dict[str, Any]) -> str:
    if provider == "censys":
        return data.get("name") or data.get("ip") or "unknown"
    if provider == "shodan":
        return data.get("ip_str") or "unknown"
    if provider == "detectify":
        return data.get("url") or data.get("uuid") or "unknown"
    return "unknown"


def _build_censys_query(domain: str) -> str:
    """Censys host-search query for one monitored domain."""
    # Names index covers reverse DNS + cert SAN; this scopes results to the customer
    return f'name: "{domain}" or names: "{domain}"'


@register_connector("easm")
class EasmConnector(BaseConnector):
    """Generic EASM connector with Censys / Shodan / Detectify sub-adapters."""

    NAME = "easm"
    RISK_INDEX_DOMAIN = "exposure"

    DISPLAY_NAME = "External Attack Surface (EASM)"
    CATEGORY = "EASM"
    SHORT_DESCRIPTION = (
        "Discover and score externally exposed assets via Censys, Shodan, or Detectify."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://search.censys.io/api"
    SUPPORTED_PRODUCTS = list(SUPPORTED_PROVIDERS)
    MODULE_CODE = "VM"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="easm_provider", label="EASM Provider", type="select", required=True,
            help_text="Pick exactly one EASM provider per tenant.",
            options=[
                {"value": "censys",   "label": "Censys"},
                {"value": "shodan",   "label": "Shodan"},
                {"value": "detectify", "label": "Detectify"},
            ],
        ),
        CredentialFieldSpec(
            name="api_token", label="API Token (Censys / Detectify)", type="password",
            required=False, secret=True,
            help_text="Bearer token. Required for Censys and Detectify.",
        ),
        CredentialFieldSpec(
            name="api_key", label="API Key (Shodan)", type="password",
            required=False, secret=True,
            help_text="Shodan API key — sent as ?key= in the query string.",
        ),
        CredentialFieldSpec(
            name="monitor_domains", label="Monitored domains", type="text", required=False,
            placeholder="example.com,test.com",
            help_text="Comma-separated. Required for Censys + Detectify.",
        ),
        CredentialFieldSpec(
            name="monitor_ips", label="Monitored IPs", type="text", required=False,
            placeholder="1.2.3.4,5.6.7.8",
            help_text="Comma-separated. Required for Shodan.",
        ),
        CredentialFieldSpec(
            name="base_url", label="API Base URL (override)", type="url", required=False,
            help_text="Override the default base URL — only for region-specific deployments.",
            pattern=r"^https://[^\s]+$",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["easm"]

    # ── Construction ───────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._provider: Optional[str] = None
        self._client: Any = None  # CensysClient | ShodanClient | DetectifyClient
        self._scope_domains: list[str] = []
        self._scope_ips: list[str] = []
        self._last_run: Optional[datetime] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None

    # ── Authentication ─────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        provider = (tenant_credentials.get("easm_provider") or "").lower()
        if not provider:
            raise ConnectorAuthError(
                "EASM credentials must include 'easm_provider'"
            )
        if provider not in SUPPORTED_PROVIDERS:
            raise ConnectorAuthError(
                f"EASM provider '{provider}' not in {SUPPORTED_PROVIDERS}"
            )

        # Construct provider-specific client
        base_override = tenant_credentials.get("base_url")

        if provider == "censys":
            api_token = tenant_credentials.get("api_token")
            if not api_token:
                raise ConnectorAuthError("Censys requires 'api_token'")
            self._client = CensysClient(
                api_token=str(api_token),
                base_url=str(base_override or CENSYS_DEFAULT_BASE),
            )
        elif provider == "shodan":
            api_key = tenant_credentials.get("api_key") or tenant_credentials.get(
                "api_token"
            )
            if not api_key:
                raise ConnectorAuthError("Shodan requires 'api_key'")
            self._client = ShodanClient(
                api_key=str(api_key),
                base_url=str(base_override or SHODAN_DEFAULT_BASE),
            )
        else:  # detectify
            api_token = tenant_credentials.get("api_token")
            if not api_token:
                raise ConnectorAuthError("Detectify requires 'api_token'")
            self._client = DetectifyClient(
                api_token=str(api_token),
                base_url=str(base_override or DETECTIFY_DEFAULT_BASE),
            )

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                f"EASM ({provider}) authentication failed — check token / scope / region"
            )

        self._provider = provider
        self._scope_domains = self._normalize_list(
            tenant_credentials.get("monitor_domains")
        )
        self._scope_ips = self._normalize_list(tenant_credentials.get("monitor_ips"))

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"easm-{provider}-****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
            extra={"provider": provider},
        )

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    # ── Fetch ──────────────────────────────────────────────────────────────

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        if self._client is None or self._provider is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")

        try:
            if self._provider == "censys":
                out = self._fetch_censys(tenant_id)
            elif self._provider == "shodan":
                out = self._fetch_shodan(tenant_id)
            elif self._provider == "detectify":
                out = self._fetch_detectify(tenant_id)
            else:
                out = []
            self._last_run = datetime.now(timezone.utc)
            return out
        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("EASM fetch_findings failed")
            raise ConnectorFetchError(f"EASM fetch failed: {exc}") from exc

    def _fetch_censys(self, tenant_id: str) -> list[RawFinding]:
        out: list[RawFinding] = []
        # Use scope; if none configured, return empty (we never pull "the internet")
        for domain in self._scope_domains:
            cursor: Optional[str] = None
            while True:
                resp = self._client.search_hosts(
                    query=_build_censys_query(domain), cursor=cursor,
                )
                parsed = CensysSearchResponse.model_validate(resp)
                for hit in parsed.result.hits:
                    payload = hit.model_dump(mode="json")
                    payload["_provider"] = "censys"
                    out.append(
                        RawFinding(
                            id=f"censys:{payload.get('ip') or payload.get('name')}",
                            source="easm:censys",
                            raw_data=payload,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                cursor = parsed.result.links.next or None
                if not cursor:
                    break
        return out

    def _fetch_shodan(self, tenant_id: str) -> list[RawFinding]:
        out: list[RawFinding] = []
        for ip in self._scope_ips:
            resp = self._client.host_lookup(ip)
            parsed = ShodanHostResponse.model_validate(resp)
            payload = parsed.model_dump(mode="json")
            payload["_provider"] = "shodan"
            out.append(
                RawFinding(
                    id=f"shodan:{ip}",
                    source="easm:shodan",
                    raw_data=payload,
                    fetched_at=datetime.now(timezone.utc),
                    tenant_id=tenant_id,
                )
            )
        return out

    def _fetch_detectify(self, tenant_id: str) -> list[RawFinding]:
        out: list[RawFinding] = []
        for domain in self._scope_domains:
            cursor: Optional[str] = None
            while True:
                resp = self._client.list_findings(domain=domain, cursor=cursor)
                parsed = DetectifyFindingsResponse.model_validate(resp)
                for f in parsed.findings:
                    payload = f.model_dump(mode="json")
                    payload["_provider"] = "detectify"
                    out.append(
                        RawFinding(
                            id=f"detectify:{f.uuid}",
                            source="easm:detectify",
                            raw_data=payload,
                            fetched_at=datetime.now(timezone.utc),
                            tenant_id=tenant_id,
                        )
                    )
                cursor = parsed.next_cursor or None
                if not cursor:
                    break
        return out

    # ── Normalize ──────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        d = raw.raw_data
        provider = d.get("_provider") or (
            raw.source.split(":", 1)[1] if ":" in raw.source else "censys"
        )
        severity = _classify_severity(provider, d)
        asset = _extract_asset(provider, d)

        finding_label = d.get("title") or f"EASM {provider} finding: {asset}"
        description = (
            d.get("description")
            or f"{provider.title()} flagged exposure on {asset}."
        )

        return URIPRiskRecord(
            finding=finding_label,
            description=description,
            source=raw.source,
            domain="external_attack_surface",
            cvss_score=0.0,
            severity=severity,
            asset=asset,
            owner_team="External Attack Surface",
            exploit_status="active" if d.get("active_exploit") else None,
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
