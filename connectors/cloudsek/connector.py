"""
CloudSEK connector for URIP.

Implements the BaseConnector contract:
  authenticate   → validates API key + Org ID via /v1/health
  fetch_findings → pulls alerts from XVigil, BeVigil, SVigil (cursor pagination)
  normalize      → maps CloudSEK alert → URIPRiskRecord
  health_check   → returns operational status

Design decisions
----------------
- Three product lines (XVigil, BeVigil, SVigil) are fetched independently.
- Tenants scope which products to poll via 'enabled_products' credential key.
- The connector injects '_product' into raw_data so normalize() knows which
  product line produced the finding without relying on heuristic field sniffing.
- Rate limits are tenant-configurable; we default to CloudSEK's documented
  ceiling (200 req/hour) when no tenant override is provided.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

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
from connectors.cloudsek.api_client import CloudSEKAPIClient, DEFAULT_BASE_URL
from connectors.cloudsek.severity_map import CLOUDSEK_ALERT_TYPE_TO_URIP_SEVERITY

logger = logging.getLogger(__name__)

# Default products to poll when tenant does not specify 'enabled_products'
DEFAULT_ENABLED_PRODUCTS = ["xvigil", "bevigil", "svigil"]

# BeVigil platforms that map to the 'mobile' domain
MOBILE_PLATFORMS = {"android", "ios"}


@register_connector("cloudsek")
class CloudSekConnector(BaseConnector):
    """
    Live connector for CloudSEK (XVigil + BeVigil + SVigil).

    Data flow
    ---------
    1. Authenticate with API key + Org ID.
    2. For each enabled product, fetch alerts since `since` (cursor pagination).
    3. Normalize each alert to URIPRiskRecord.
    """

    NAME = "cloudsek"
    # CloudSEK ships XVigil (active dark-web threat alerts → ATTACK) and BeVigil
    # (mobile-app exposure → could be EXPOSURE).  Single Risk.source="cloudsek"
    # cannot distinguish the sub-product, so we route the connector as a whole
    # to "attack" because that is the dominant XVigil signal customers buy it
    # for.  Trade-off documented in risk_index_service.py.
    RISK_INDEX_DOMAIN = "attack"

    # ── Z3: Tool Catalog metadata ───────────────────────────────────────────
    DISPLAY_NAME = "CloudSEK XVigil / BeVigil / SVigil"
    CATEGORY = "EXTERNAL_THREAT"
    SHORT_DESCRIPTION = (
        "Brand impersonation, exposed credentials, mobile app & supply-chain risks from CloudSEK."
    )
    STATUS = "live"
    VENDOR_DOCS_URL = "https://docs.cloudsek.com/"
    SUPPORTED_PRODUCTS = ["XVigil", "BeVigil", "SVigil"]
    MODULE_CODE = "EXTERNAL_THREAT"
    CREDENTIAL_FIELDS = [
        CredentialFieldSpec(
            name="api_key", label="API Key", type="password",
            required=True, secret=True,
            help_text="Settings → API Access → Generate API Key.",
        ),
        CredentialFieldSpec(
            name="org_id", label="Organization ID", type="text", required=True,
            help_text="CloudSEK organization identifier from your tenant settings.",
        ),
        CredentialFieldSpec(
            name="api_base", label="API Base URL", type="url", required=False,
            default="https://api.cloudsek.com",
            placeholder="https://api.cloudsek.com",
            help_text="Override only for region-specific CloudSEK pods.",
            pattern=r"^https://[^\s]+$",
        ),
        CredentialFieldSpec(
            name="enabled_products", label="Enabled Products", type="text",
            required=False, default="xvigil,bevigil,svigil",
            help_text="Comma-separated subset of {xvigil, bevigil, svigil}.",
        ),
    ]

    # P33-Z3 (revised): inline onboarding content rendered in the Tool Catalog drawer.
    SETUP_GUIDE = SETUP_GUIDES["cloudsek"]

    def __init__(self) -> None:
        self._client: CloudSEKAPIClient | None = None
        self._last_run: datetime | None = None
        self._error_count: int = 0
        self._last_error: str | None = None
        self._products_enabled: list[str] = list(DEFAULT_ENABLED_PRODUCTS)

    # ─────────────────────────────────────────────────────────────────────────
    # authenticate
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, tenant_credentials: dict) -> ConnectorSession:
        """
        Validate CloudSEK API credentials.

        Required credential keys:
            - api_key  (or cloudsek_api_key)
            - org_id   (or cloudsek_org_id)
        Optional:
            - api_base                  (default https://api.cloudsek.com)
            - enabled_products          (list of str, default all three)
            - max_requests_per_minute   (int, converts to hourly for client)
            - tenant_id
        """
        api_key = (
            tenant_credentials.get("api_key")
            or tenant_credentials.get("cloudsek_api_key")
        )
        org_id = (
            tenant_credentials.get("org_id")
            or tenant_credentials.get("cloudsek_org_id")
        )

        if not api_key:
            raise ConnectorAuthError(
                "CloudSEK credentials must include 'api_key'"
            )
        if not org_id:
            raise ConnectorAuthError(
                "CloudSEK credentials must include 'org_id'"
            )

        base_url = tenant_credentials.get("api_base", DEFAULT_BASE_URL)
        max_rpm = tenant_credentials.get("max_requests_per_minute")

        client_kwargs: dict[str, Any] = {
            "api_key": str(api_key),
            "org_id": str(org_id),
            "base_url": str(base_url),
        }
        if max_rpm is not None:
            client_kwargs["max_requests_per_hour"] = int(max_rpm) * 60

        self._client = CloudSEKAPIClient(**client_kwargs)

        if not self._client.validate_auth():
            raise ConnectorAuthError(
                "CloudSEK authentication failed: invalid API key or Org ID"
            )

        # Track enabled products for health-check context
        enabled = tenant_credentials.get("enabled_products")
        if enabled is not None:
            self._products_enabled = [str(p).lower() for p in enabled]
        else:
            self._products_enabled = list(DEFAULT_ENABLED_PRODUCTS)

        return ConnectorSession(
            connector_name=self.NAME,
            tenant_id=tenant_credentials.get("tenant_id", "unknown"),
            token=f"cloudsek-{str(api_key)[:4]}****",
            expires_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # fetch_findings
    # ─────────────────────────────────────────────────────────────────────────

    def fetch_findings(self, since: datetime, **kwargs: Any) -> list[RawFinding]:
        """
        Pull new/updated findings from CloudSEK since `since`.

        Parameters
        ----------
        since : datetime
            Fetch only alerts created/updated after this timestamp.
        tenant_id : str, optional
            Scoped into RawFinding.tenant_id.
        """
        if self._client is None:
            raise ConnectorFetchError(
                "Connector not authenticated. Call authenticate() first."
            )

        tenant_id: str = kwargs.get("tenant_id", "unknown")
        since_iso: str | None = since.isoformat() if since else None
        findings: list[RawFinding] = []

        try:
            for product in self._products_enabled:
                if product == "xvigil":
                    findings.extend(
                        self._fetch_product(
                            product,
                            self._client.list_xvigil_alerts,
                            since_iso,
                            tenant_id,
                        )
                    )
                elif product == "bevigil":
                    findings.extend(
                        self._fetch_product(
                            product,
                            self._client.list_bevigil_findings,
                            since_iso,
                            tenant_id,
                        )
                    )
                elif product == "svigil":
                    findings.extend(
                        self._fetch_product(
                            product,
                            self._client.list_svigil_risks,
                            since_iso,
                            tenant_id,
                        )
                    )
                else:
                    logger.warning(
                        "CloudSEK: unknown product '%s' in enabled_products — skipping.",
                        product,
                    )

            logger.info(
                "CloudSEK: fetched %d findings from products %s for tenant %s",
                len(findings),
                self._products_enabled,
                tenant_id,
            )
            self._last_run = datetime.now(timezone.utc)
            return findings

        except Exception as exc:
            self._error_count += 1
            self._last_error = str(exc)
            logger.exception("CloudSEK fetch_findings failed")
            raise ConnectorFetchError(f"CloudSEK fetch failed: {exc}") from exc

    def _fetch_product(
        self,
        product: str,
        fetch_fn: Callable,
        since_iso: str | None,
        tenant_id: str,
    ) -> list[RawFinding]:
        """Cursor-pagination loop for a single CloudSEK product endpoint."""
        product_findings: list[RawFinding] = []
        cursor: str | None = None

        while True:
            resp = fetch_fn(since=since_iso, cursor=cursor)
            for item in resp.get("data", []):
                item["_product"] = product
                product_findings.append(
                    RawFinding(
                        id=item["id"],
                        source=self.NAME,
                        raw_data=item,
                        fetched_at=datetime.now(timezone.utc),
                        tenant_id=tenant_id,
                    )
                )

            next_cursor = resp.get("pagination", {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor

        return product_findings

    # ─────────────────────────────────────────────────────────────────────────
    # normalize
    # ─────────────────────────────────────────────────────────────────────────

    def normalize(self, raw: RawFinding) -> URIPRiskRecord:
        """
        Map a CloudSEK RawFinding to URIPRiskRecord.

        Mappings
        --------
        alert_type              → severity via CLOUDSEK_ALERT_TYPE_TO_URIP_SEVERITY
        _product + platform     → domain (external_threat | application | mobile | supply_chain)
        asset.*                 → asset string (domain, email, package_name, vendor_name)
        weaponized=True         → exploit_status = 'active'
        threat_actor            → appended to description (APT attribution)
        """
        data = raw.raw_data
        product = data.get("_product", "xvigil")
        alert_type = data.get("alert_type", "unknown")

        severity = CLOUDSEK_ALERT_TYPE_TO_URIP_SEVERITY.get(alert_type, "medium")

        # ── domain mapping ──────────────────────────────────────────────────
        if product == "xvigil":
            domain = "external_threat"
        elif product == "bevigil":
            platform = (data.get("asset") or {}).get("platform", "web")
            domain = "mobile" if platform in MOBILE_PLATFORMS else "application"
        elif product == "svigil":
            domain = "supply_chain"
        else:
            domain = "external_threat"

        # ── asset extraction ────────────────────────────────────────────────
        asset_info = data.get("asset") or {}
        if product == "xvigil":
            asset = asset_info.get("domain") or asset_info.get("email") or "unknown"
        elif product == "bevigil":
            asset = (
                asset_info.get("package_name")
                or asset_info.get("url")
                or "unknown"
            )
        else:  # svigil
            asset = asset_info.get("vendor_name") or "unknown"

        # ── exploit status ──────────────────────────────────────────────────
        exploit_status: str | None = None
        if data.get("weaponized") is True:
            exploit_status = "active"

        # ── CVSS (SVigil may carry vendor CVSS) ─────────────────────────────
        cvss = data.get("cvss_score") or 0.0

        # ── description with APT attribution ────────────────────────────────
        description = data.get("description") or data.get("title") or "CloudSEK alert"
        threat_actor = data.get("threat_actor")
        if threat_actor:
            description = f"{description} (Threat actor: {threat_actor})"

        return URIPRiskRecord(
            finding=data.get("title", "CloudSEK Alert"),
            description=description,
            source=self.NAME,
            domain=domain,
            cvss_score=cvss,
            severity=severity,
            asset=asset,
            owner_team="Threat Intelligence",
            cve_id=data.get("cve_id"),
            exploit_status=exploit_status,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # health_check
    # ─────────────────────────────────────────────────────────────────────────

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
